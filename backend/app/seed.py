"""Default data created on startup: the categories and one admin account."""
from sqlalchemy.orm import Session

from .config import ADMIN_EMAIL, ADMIN_PASSWORD
from .models import Category, User
from .security import hash_password

CATEGORIES = [
    ("Books", "📚"),
    ("Electronics", "💻"),
    ("Phones", "📱"),
    ("Clothes and Shoes", "👕"),
    ("Hostel and Furniture", "🛏"),
    ("Stationery", "✏"),
    ("Food and Snacks", "🍞"),
    ("Services", "🛠"),
    ("Other", "📦"),
]


def seed(db: Session) -> None:
    if db.query(Category).count() == 0:
        db.add_all(Category(name=name, icon=icon) for name, icon in CATEGORIES)

    if db.query(User).filter(User.email == ADMIN_EMAIL.lower()).first() is None:
        db.add(
            User(
                full_name="CampusMart Admin",
                email=ADMIN_EMAIL.lower(),
                password_hash=hash_password(ADMIN_PASSWORD),
                phone="256700000000",
                campus="Admin",
                role="admin",
            )
        )
    db.commit()
