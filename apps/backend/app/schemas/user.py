from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    phone: Optional[str] = None
    status: str
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserInDB(UserBase):
    id: int
    password_hash: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
