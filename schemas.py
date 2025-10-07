from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import re

# --- Role Enum ---
class Role(str, Enum):
    super_admin = "super_admin"
    admin = "admin"

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[Role] = None


# --- Tenant Schemas ---
class TenantBase(BaseModel):
    name: str

class TenantCreate(TenantBase):
    pass

class Tenant(TenantBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

# --- User Schemas ---
class UserBase(BaseModel):
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str
    tenant_id: int
    role: Role = Role.admin
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserSignUp(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=20,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Username must be 3-20 characters long and contain only letters, numbers, and underscores."
    )
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters long."
    )
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[\d\s\-\(\)]{7,20}$",
        description="Optional valid phone number."
    )

    @validator('password')
    def password_complexity(cls, v):
        if not re.search(r'\d', v): # Must contain a digit
            raise ValueError('Password must contain at least one digit.')
        if not re.search(r'[a-zA-Z]', v): # Must contain a letter
            raise ValueError('Password must contain at least one letter.')
        return v

class User(UserBase):
    id: int
    is_active: bool
    tenant_id: int
    role: Role
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None

    class Config:
        orm_mode = True

class SignUpResponse(BaseModel):
    user: User
    tenant: Tenant

class UserUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[Role] = None


# --- Vendor Schemas ---
class VendorBase(BaseModel):
    name: str

class VendorCreate(VendorBase):
    pass

class Vendor(VendorBase):
    id: int

    class Config:
        orm_mode = True

# --- OID Schemas ---
class OIDBase(BaseModel):
    oid: str
    fungsi: str
    type: str
    model: Optional[str] = None

class OIDCreate(OIDBase):
    vendor_id: int

class OID(OIDBase):
    id: int
    vendor_id: int

    class Config:
        orm_mode = True

class OIDUpdate(OIDBase):
    oid: Optional[str] = None
    fungsi: Optional[str] = None
    type: Optional[str] = None
    model: Optional[str] = None
    vendor_id: Optional[int] = None

# --- OLT Schemas ---
class OLTBase(BaseModel):
    name: str
    ip: str
    username: str
    olt_type: Optional[str] = None
    ssh_port: Optional[int] = 22
    telnet_port: Optional[int] = 23
    snmp_port: Optional[int] = 161
    community: Optional[str] = "public"
    ssh_delay: Optional[int] = 10
    ssh_timeout: Optional[int] = 10

class OLTCreate(OLTBase):
    password: str
    vendor_id: int

class OLT(OLTBase):
    id: int
    vendor_id: int
    tenant_id: int
    status: str
    last_checked: Optional[datetime] = None

    class Config:
        orm_mode = True

class OLTUpdate(OLTBase):
    password: Optional[str] = None
    vendor_id: Optional[int] = None
    community: Optional[str] = None

# --- ONU Schemas ---
class OnuBase(BaseModel):
    identifier: str
    pon_interface: str
    vendor_name: str
    last_seen: datetime
    details: Optional[Dict[str, Any]] = None
    details_snmp: Optional[Dict[str, Any]] = None

class Onu(OnuBase):
    id: int
    olt_id: int

    class Config:
        orm_mode = True

class OnuListResponse(BaseModel):
    total: int
    onus: List[Onu]


# --- SNMP ONU Schemas ---
class OnuSnmp(BaseModel):
    name: str
    status: int
    tx_power: str
    rx_power: str
    mac_address: str

# --- Subscription Schemas ---
class Subscription(BaseModel):
    id: int
    plan_name: str
    status: str
    current_period_end: datetime
    max_olts: int
    max_onus: int

    class Config:
        orm_mode = True

class SubscriptionUpdate(BaseModel):
    plan_name: str = Field(..., description="Name of the plan, e.g., 'free', 'pro'")
    duration_days: int = Field(..., gt=0, description="Duration of the subscription in days from now.")

class SubscriptionQuota(BaseModel):
    olts_used: int
    olts_limit: int
    onus_used: int
    onus_limit: int
