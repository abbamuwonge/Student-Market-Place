from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..files import delete_upload
from ..models import Item, Message, User
from ..schemas import ItemOut, UserOut, UserUpdate
from ..security import get_current_user
from ..serializers import item_out

router = APIRouter(prefix="/users", tags=["Users"])


@router.put("/me", response_model=UserOut)
def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = data.full_name
    user.phone = data.phone
    user.campus = data.campus
    db.commit()
    db.refresh(user)
    return user


@router.delete("/me")
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Deletes the account with its items, favourites, orders and messages."""
    image_urls = [item.image_url for item in user.items]
    db.query(Message).filter(
        or_(Message.sender_id == user.user_id, Message.receiver_id == user.user_id)
    ).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    for url in image_urls:
        delete_upload(url)
    return {"message": "Account deleted"}


@router.get("/me/items", response_model=list[ItemOut])
def my_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (
        db.query(Item)
        .options(joinedload(Item.seller), joinedload(Item.category))
        .filter(Item.seller_id == user.user_id)
        .order_by(Item.created_at.desc(), Item.item_id.desc())
        .all()
    )
    return [item_out(i, include_phone=True) for i in items]
