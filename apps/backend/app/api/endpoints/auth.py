import os
from datetime import datetime, timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.organization import Organization
from app.models.organization_member import MemberRole, OrganizationMember
from app.models.user import User
from app.models.consent import ConsentRecord, ConsentScope
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserUpdate,
)
from app.schemas.token import Token
from app.schemas.user import (
    EmailVerificationRequest,
    ResendVerificationRequest,
    UserCreate,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

AUTH_COOKIE_NAME = "lilian_auth_token"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24  # 24h, aligned with ACCESS_TOKEN_EXPIRE_MINUTES


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set the auth cookie on the response with secure flags.

    - ``HttpOnly`` blocks JS access (XSS-resistant).
    - ``SameSite=Lax`` blocks cross-origin POSTs while allowing top-level GETs.
    - ``Secure`` is gated on ``APP_ENV=production`` so dev (http://localhost)
      still works.
    """
    is_production = settings.APP_ENV.lower() == "production"
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=is_production,
        samesite="lax",
        path="/",
    )


def _generate_verification_token() -> str:
    """URL-safe token of ~32 bytes of entropy.

    The token is opaque (not derivable from the user id) so it cannot be
    guessed. ``token_urlsafe(32)`` produces 43 base64-url chars which
    comfortably fits the 128-char column.
    """
    return token_urlsafe(32)


def _send_verification_email(user: User, frontend_base_url: str | None = None) -> None:
    """Render + dispatch (or stub-log) the verification email.

    The endpoint layer is responsible for the user lookup and token
    issuance; this helper only formats the email and hands it off to
    ``send_email``. Failures are swallowed with a log line so the
    /register endpoint never bubbles a 500 because of an upstream
    email provider being unavailable — the user can always use the
    resend endpoint.
    """
    import logging

    logger = logging.getLogger("lilian.auth")

    base = frontend_base_url or os.environ.get(
        "FRONTEND_BASE_URL",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app",
    )
    verify_url = f"{base.rstrip('/')}/auth/verify-email?token={user.verification_token}"

    try:
        from app.services.email import send_email

        send_email(
            to=user.email,
            template="email_verification",
            data={"full_name": user.full_name, "verify_url": verify_url},
        )
        user.verification_sent_at = datetime.utcnow()
    except Exception as exc:  # pragma: no cover - never block signup
        logger.warning("verification email send failed for user_id=%s: %s", user.id, exc)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # S1-05: prevent mass account creation
def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """Registra un nuevo usuario y crea su organización personal.

    Verifica que el email no esté ya registrado, hashea la contraseña,
    crea el usuario (con ``email_verified=False`` y un ``verification_token``
    nuevo), le asocia una ``Organization`` tipo ``individual`` y un
    ``OrganizationMember`` con rol ``OWNER``, y por último envía el
    email de verificación (con fallback a log-stub si Resend no está
    configurado).

    Args:
        request: Request de FastAPI (requerido por ``limiter.limit``).
        user_data: Payload validado (``UserCreate``) con ``email``,
            ``password`` y ``full_name``.
        db: Sesión de SQLAlchemy inyectada por dependencia.

    Returns:
        ``UserResponse`` con los datos públicos del usuario creado.

    Raises:
        HTTPException: 400 si el email ya está registrado.
        HTTPException: 422 si el consentimiento explícito no fue otorgado.
    """
    # Ley 21.719 — consentimiento explícito obligatorio. Sin esto no
    # podemos crear la cuenta; es un requisito legal, no una nice-to-have.
    if not (user_data.terms_accepted and user_data.privacy_accepted):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Debes aceptar los Términos de Uso y la Política de Privacidad "
                "para crear tu cuenta (Ley 21.719)."
            ),
        )
    if not user_data.terms_version or not user_data.privacy_version:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Falta la versión de los documentos legales aceptados. "
                "Recarga la página para obtener la versión vigente."
            ),
        )

    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )

    now = datetime.utcnow()
    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        email_verified=False,
        verification_token=_generate_verification_token(),
        verification_sent_at=now,
        # Ley 21.719 — denormalised consent fields for the fast auth path.
        consent_given_at=now,
        terms_version=user_data.terms_version,
        privacy_version=user_data.privacy_version,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Persist one ConsentRecord per scope. We store the IP/UA from the
    # request so we have a verifiable trail ("user X consented to
    # version Y from IP Z at timestamp T") for years to come.
    ip = (request.client.host if request.client else None) or None
    ua = (request.headers.get("user-agent") or "")[:512] or None
    for scope, version in (
        (ConsentScope.TERMS, user_data.terms_version),
        (ConsentScope.PRIVACY, user_data.privacy_version),
    ):
        db.add(ConsentRecord(
            user_id=user.id,
            scope=scope,
            version=version,
            granted_at=now,
            ip_address=ip,
            user_agent=ua,
        ))
    db.commit()

    org = Organization(
        name=f"Organización de {user_data.full_name}",
        type="individual"
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=MemberRole.OWNER
    )
    db.add(membership)
    db.commit()

    _send_verification_email(user)

    return user


@router.post("/verify-email", response_model=UserResponse)
def verify_email(
    payload: EmailVerificationRequest,
    db: Session = Depends(get_db),
):
    """S1.1 — confirma un ``verification_token`` y activa la cuenta.

    Devuelve el ``UserResponse`` para que el frontend pueda mostrar un
    mensaje y redirigir a ``/auth/login``.

    Returns:
        ``UserResponse`` con ``email_verified=True``.

    Raises:
        HTTPException 400 si el token no existe o ya fue consumido.
    """
    user = db.query(User).filter(
        User.verification_token == payload.token,
    ).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificación no es válido o ya fue usado",
        )

    user.email_verified = True
    user.verification_token = None  # one-shot: prevents replay
    db.commit()
    db.refresh(user)
    return user


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(
    payload: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    """S1.1 — regenera y reenvía el ``verification_token``.

    Siempre responde 202 aunque el email no esté registrado: este
    endpoint no debe usarse para enumerar cuentas.

    Si la cuenta ya está verificada, respondemos 202 igual sin hacer
    nada — la idempotencia es importante para tolerar dobles clics en
    el botón "Reenviar" del frontend.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if user is not None and not user.email_verified:
        user.verification_token = _generate_verification_token()
        user.verification_sent_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        _send_verification_email(user)
    return {"status": "queued"}


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")  # S1-05: prevent brute-force attacks
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Autentica al usuario y emite un token JWT de acceso.

    Verifica credenciales contra ``User.password_hash`` (bcrypt),
    rechaza el login si el email no está verificado, actualiza
    ``last_login_at``, genera el JWT con ``create_access_token`` y lo
    deposita en la cookie ``lilian_auth_token`` para uso por el
    frontend.
    """
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # S1.1: block login until the user has confirmed ownership of
    # the email address. ``get_current_user`` would happily hand out
    # a JWT for an unverified account otherwise — that's the bug
    # S1.1 is here to fix.
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu correo antes de iniciar sesión. Revisa tu bandeja de entrada o reenvía la verificación desde la pantalla de registro.",
        )

    user.last_login_at = datetime.utcnow()
    db.commit()

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    _set_auth_cookie(response, access_token)

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    credentials_exception: HTTPException = Depends(lambda: HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )),
):
    """Clear the auth cookie AND blacklist the current JWT (S1-16).

    Idempotent — safe to call when no token is present (the cookie is
    cleared unconditionally). When a token is supplied we add it to the
    Redis blacklist with a TTL aligned to the token's remaining lifetime
    so subsequent requests carrying the same token are rejected.
    """
    from app.core.security import decode_access_token
    from app.core.token_blacklist import revoke_token, ttl_for_token

    authorization = request.headers.get("authorization", "")
    token: str | None = None
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    else:
        # Cookies aren't readable from headers here, but the cookie value
        # was set by this same endpoint on login. Best-effort fallback:
        cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
        if cookie_token:
            token = cookie_token

    if token:
        payload = decode_access_token(token)
        ttl = ttl_for_token(payload.get("exp") if payload else None)
        revoke_token(token, ttl)

    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Return the authenticated user plus their role list.

    S4.6: the dashboard sidebar uses ``roles`` to gate the Admin
    section. We pull every membership the user has across all
    organizations and surface the role names so the frontend can
    decide which links to render.
    """
    from app.models.organization_member import OrganizationMember

    memberships = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == current_user.id)
        .all()
    )
    roles = sorted({m.role.value for m in memberships if m.role})

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        status=current_user.status,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
        email_verified=current_user.email_verified,
        roles=roles,
    )


def _send_password_reset_email(user: User, frontend_base_url: str | None = None) -> None:
    """Render + dispatch (or stub-log) the password-reset email.

    Mirrors ``_send_verification_email``: the endpoint layer owns the
    token issuance, this helper only formats the email and hands it off
    to ``send_email``. Failures are swallowed with a log line so the
    /auth/forgot-password endpoint never bubbles a 500 because of an
    upstream email provider being unavailable — the user simply won't
    get an email, which matches the always-202 contract on that endpoint.
    """
    import logging

    logger = logging.getLogger("lilian.auth")

    base = frontend_base_url or os.environ.get(
        "FRONTEND_BASE_URL",
        "https://lil-i-5tz56uhov-jorgeguerrerohidalgo710.vercel.app",
    )
    reset_url = f"{base.rstrip('/')}/auth/reset-password?token={user.password_reset_token}"

    try:
        from app.services.email import send_email

        send_email(
            to=user.email,
            template="password_reset",
            data={"full_name": user.full_name, "reset_url": reset_url},
        )
    except Exception as exc:  # pragma: no cover - never block forgot-password
        logger.warning("password reset email send failed for user_id=%s: %s", user.id, exc)


def _revoke_active_session_for_user(user: User, request: Request) -> None:
    """Best-effort JWT blacklist for the request that triggered the reset.

    The user just rotated their credentials, so the JWT they currently
    hold should no longer be valid: an attacker who previously captured
    it would otherwise remain authenticated for up to ``ACCESS_TOKEN_EXPIRE_MINUTES``.

    We do NOT fail the request if this step errors: the password has
    already been rotated, which is the security-relevant event.
    """
    try:
        from app.core.security import decode_access_token
        from app.core.token_blacklist import revoke_token, ttl_for_token

        authorization = request.headers.get("authorization", "")
        token: str | None = None
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        else:
            cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
            if cookie_token:
                token = cookie_token

        if not token:
            return

        payload = decode_access_token(token)
        ttl = ttl_for_token(payload.get("exp") if payload else None)
        revoke_token(token, ttl)
    except Exception:  # pragma: no cover - defensive, never block reset
        pass


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Phase 1b — editar el perfil del usuario autenticado.

    Solo actualiza los campos provistos (``full_name``, ``phone``).
    El email está excluido a propósito: cambiar el email requiere
    re-verificación, fuera del scope de esta fase.

    Devuelve el ``UserResponse`` (igual que ``GET /me``) para que el
    frontend pueda refrescar su estado local con la respuesta.
    """
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)

    # Re-pull memberships so the response carries the role list (mirrors
    # GET /me exactly).
    memberships = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == current_user.id)
        .all()
    )
    roles = sorted({m.role.value for m in memberships if m.role})

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        status=current_user.status,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
        email_verified=current_user.email_verified,
        roles=roles,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")  # S1-05 parity with /login
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Phase 1b — cambiar la contraseña del usuario autenticado.

    Verifica la contraseña actual (``HTTPException 400`` si no
    coincide), valida la nueva con la misma política de fortaleza que
    usa ``/register``, hashea con ``get_password_hash`` y persiste.
    """
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta",
        )

    current_user.password_hash = get_password_hash(payload.new_password)
    db.commit()

    # Rotate out any active JWT the user might be holding. Defensive
    # best-effort — the password is already rotated, so the request
    # must not 500 on this step.
    _revoke_active_session_for_user(current_user, request)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")  # stricter than /change-password — abuse vector
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Phase 1b — solicitar reset de contraseña por email.

    Genera un ``password_reset_token`` opaco (1 h de TTL), lo persiste
    en el ``User`` y dispara el email con el template ``password_reset``.
    **Siempre responde 202**, exista o no el email: este endpoint no
    debe usarse para enumerar cuentas.

    Si la cuenta está ``SUSPENDED``, igual generamos el token (no
    queremos filtrar el estado de la cuenta via response shape).
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if user is not None:
        user.password_reset_token = token_urlsafe(32)
        user.password_reset_expires_at = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        db.refresh(user)
        _send_password_reset_email(user)

    return {"status": "queued"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> Response:
    """Phase 1b — completar un reset de contraseña con un token.

    Busca el ``User`` por ``password_reset_token``; si no existe o el
    token expiró, devuelve 400 con mensaje neutro (no revelamos si el
    token es inválido o expirado por separado). Hashea la nueva
    contraseña, limpia el token, y revoca el JWT activo si está
    presente en el request.
    """
    now = datetime.utcnow()
    user = db.query(User).filter(User.password_reset_token == payload.token).first()
    if user is None or user.password_reset_expires_at is None or user.password_reset_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    user.password_hash = get_password_hash(payload.new_password)
    # One-shot: clear the token immediately so a leaked token cannot
    # be replayed even within the 1h window.
    user.password_reset_token = None
    user.password_reset_expires_at = None
    db.commit()

    _revoke_active_session_for_user(user, request)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
