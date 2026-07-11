from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.organization_member import OrganizationMember
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: int = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_user_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Optional[OrganizationMember]:
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).first()

    if not membership:
        return None

    return membership


def require_organization(
    membership: Optional[OrganizationMember] = Depends(get_current_user_organization)
) -> OrganizationMember:
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no pertenece a ninguna organización"
        )
    return membership
