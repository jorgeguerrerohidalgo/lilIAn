from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember, MemberRole
from app.schemas.user import UserCreate, UserResponse, UserLogin
from app.schemas.token import Token
from app.api.deps.auth import get_current_user

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


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # S1-05: prevent mass account creation
def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )

    user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

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

    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")  # S1-05: prevent brute-force attacks
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
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
    from app.core.token_blacklist import revoke_token, ttl_for_token
    from app.core.security import decode_access_token

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
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
