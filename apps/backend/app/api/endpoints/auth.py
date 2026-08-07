from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
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
def register(user_data: UserCreate, db: Session = Depends(get_db)):
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
def login(
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
def logout(response: Response):
    """Clear the auth cookie. Idempotent — safe to call when no cookie exists."""
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
