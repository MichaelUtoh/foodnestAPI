from typing import Dict, List, Optional
from bson import ObjectId
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl


from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    WHOLESALER = "wholesaler"
    RETAILER = "retailer"
    DISPATCH = "dispatch"


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserRegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str]
    middle_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    role: UserRole = UserRole.RETAILER
    is_active: bool = True
    is_admin: bool = False

    mfa_secret: Optional[str] = None
    mfa_enabled: bool = False

    def __str__(self):
        return self.email


class UserUpdateRoleSchema(BaseModel):
    role: UserRole = UserRole.RETAILER


class UserUpdateSchema(BaseModel):
    first_name: Optional[str]
    middle_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    role: Optional[UserRole] = None


class UserLoginResponseSchema(BaseModel):
    id: str
    email: EmailStr
    access_token: str
    refresh_token: str


class UserInfoResponseSchema(BaseModel):
    id: str
    email: EmailStr
    first_name: Optional[str]
    middle_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    is_active: bool
    role: UserRole
    created_at: datetime
    image_url: Optional[str] = None
    mfa_enabled: bool = False

    class Config:
        from_attributes = True


class UserInfoPaginatedResponseSchema(BaseModel):
    items: List[UserInfoResponseSchema]
    meta: Dict


class MFARequest(BaseModel):
    otp_code: str
