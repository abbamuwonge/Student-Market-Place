from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Favorite, Item, User
from ..schemas import FavoriteCreate, ItemOut
from ..security import get_current_user
from ..serializers import item_out

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.get("", response_model=list[ItemOut])
def my_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (
        db.query(Item)
        .options(joinedload(Item.seller), joinedload(Item.category))
        .join(Favorite, Favorite.item_id == Item.item_id)
        .filter(Favorite.user_id == user.user_id)
        .order_by(Favorite.saved_at.desc())
        .all()
    )
    return [item_out(i) for i in items]


@router.post("", response_model=ItemOut, status_code=201)
def add_favorite(data: FavoriteCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Item, data.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if db.get(Favorite, (user.user_id, item.item_id)) is not None:
        raise HTTPException(status_code=400, detail="Item is already in your favourites")
    db.add(Favorite(user_id=user.user_id, item_id=item.item_id))
    db.commit()
    return item_out(item)


@router.delete("/{item_id}")
def remove_favorite(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    favorite = db.get(Favorite, (user.user_id, item_id))
    if favorite is None:
        raise HTTPException(status_code=404, detail="Item is not in your favourites")
    db.delete(favorite)
    db.commit()
    return {"message": "Removed from favourites"}
