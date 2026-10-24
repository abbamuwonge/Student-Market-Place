"""Database tables. They match the ERD and data dictionary in the design document."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

ITEM_CONDITIONS = ("new", "like new", "used good", "used fair")
ITEM_STATUSES = ("available", "reserved", "sold")
ORDER_STATUSES = ("pending", "accepted", "rejected", "cancelled", "completed")
ROLES = ("student", "admin")


def _in(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(_in("role", ROLES), name="ck_users_role"),)

    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    campus: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="student")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    items: Mapped[list["Item"]] = relationship(back_populates="seller", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(back_populates="buyer", cascade="all, delete-orphan")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    category_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    items: Mapped[list["Item"]] = relationship(back_populates="category")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_items_price"),
        CheckConstraint(_in("item_condition", ITEM_CONDITIONS), name="ck_items_condition"),
        CheckConstraint(_in("status", ITEM_STATUSES), name="ck_items_status"),
        Index("ix_items_status_created", "status", "created_at"),
    )

    item_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 0, asdecimal=False), nullable=False)
    item_condition: Mapped[str] = mapped_column(String(20), nullable=False)
    pickup_location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    seller: Mapped["User"] = relationship(back_populates="items")
    category: Mapped["Category"] = relationship(back_populates="items")
    orders: Mapped[list["Order"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    # messages keep existing when an item is deleted: the database sets item_id to NULL
    messages: Mapped[list["Message"]] = relationship(back_populates="item", passive_deletes=True)


class Order(Base):
    """A purchase request from a buyer for an item. The seller is reached through the item."""
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint(_in("status", ORDER_STATUSES), name="ck_orders_status"),)

    order_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.item_id", ondelete="CASCADE"), nullable=False, index=True
    )
    price_at_order: Mapped[float] = mapped_column(Numeric(12, 0, asdecimal=False), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    buyer: Mapped["User"] = relationship(back_populates="orders")
    item: Mapped["Item"] = relationship(back_populates="orders")

    @property
    def seller(self) -> "User":
        return self.item.seller


class Favorite(Base):
    """Junction table: users <-> items (many-to-many)."""
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.item_id", ondelete="CASCADE"), primary_key=True
    )
    saved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="favorites")
    item: Mapped["Item"] = relationship(back_populates="favorites")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_pair", "sender_id", "receiver_id"),)

    message_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("items.item_id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    item: Mapped[Optional["Item"]] = relationship(back_populates="messages")
