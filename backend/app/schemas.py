"""Request and response shapes (validation happens here)."""
import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ItemCondition = Literal["new", "like new", "used good", "used fair"]
ItemStatus = Literal["available", "reserved", "sold"]


def normalise_phone(value: str) -> str:
    """Accepts 07XXXXXXXX or 2567XXXXXXXX (spaces, + and dashes allowed) and returns 256XXXXXXXXX."""
    digits = re.sub(r"[\s\-+()]", "", value)
    if digits.startswith("0") and len(digits) == 10:
        digits = "256" + digits[1:]
    if not re.fullmatch(r"256\d{9}", digits):
        raise ValueError("Phone must look like 2567XXXXXXXX or 07XXXXXXXX")
    return digits


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- users and auth ----------
class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str
    campus: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=72)  # bcrypt only reads the first 72 bytes

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalise_phone(v)

    @field_validator("full_name", "campus")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Must be at least 2 characters")
        return v


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    phone: str
    campus: str = Field(min_length=2, max_length=80)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalise_phone(v)

    @field_validator("full_name", "campus")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Must be at least 2 characters")
        return v


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    user_id: int
    full_name: str
    email: str
    phone: str
    campus: str
    role: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SellerOut(ORMModel):
    """Public view of a user. The phone number is filled in only when the viewer is allowed to see it."""
    user_id: int
    full_name: str
    campus: str
    phone: Optional[str] = None


# ---------- categories ----------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    icon: Optional[str] = Field(default=None, max_length=10)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v


class CategoryOut(ORMModel):
    category_id: int
    name: str
    icon: Optional[str] = None


# ---------- items ----------
class ItemCreate(BaseModel):
    category_id: int
    title: str = Field(min_length=3, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    price: int = Field(gt=0, le=999_999_999_999)  # UGX
    item_condition: ItemCondition
    pickup_location: Optional[str] = Field(default=None, max_length=100)

    @field_validator("title", "description")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Cannot be empty")
        return v


class ItemStatusUpdate(BaseModel):
    status: ItemStatus


class ItemBrief(ORMModel):
    item_id: int
    title: str
    price: int
    image_url: Optional[str] = None
    status: str


class ItemOut(ORMModel):
    item_id: int
    title: str
    description: str
    price: int
    item_condition: str
    pickup_location: Optional[str] = None
    image_url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: CategoryOut
    seller: SellerOut


# ---------- orders ----------
class OrderCreate(BaseModel):
    item_id: int
    note: Optional[str] = Field(default=None, max_length=200)


class OrderStatusUpdate(BaseModel):
    status: Literal["accepted", "rejected", "cancelled", "completed"]


class OrderOut(ORMModel):
    order_id: int
    price_at_order: int
    note: Optional[str] = None
    status: str
    created_at: datetime
    item: ItemBrief
    buyer: SellerOut
    seller: SellerOut


# ---------- favorites ----------
class FavoriteCreate(BaseModel):
    item_id: int


# ---------- messages ----------
class MessageCreate(BaseModel):
    receiver_id: int
    item_id: Optional[int] = None
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v


class MessageOut(ORMModel):
    message_id: int
    sender_id: int
    receiver_id: int
    item_id: Optional[int] = None
    body: str
    sent_at: datetime
    is_read: bool


class ConversationOut(BaseModel):
    other_user_id: int
    other_user_name: str
    item_id: Optional[int] = None
    item_title: Optional[str] = None
    last_message: str
    last_sender_id: int
    last_sent_at: datetime
    unread_count: int
