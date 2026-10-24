from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..config import MAX_UPLOAD_BYTES, PAGE_SIZE
from ..database import get_db
from ..files import delete_upload, save_image
from ..models import Category, Item, User, utcnow
from ..schemas import ItemCondition, ItemCreate, ItemOut, ItemStatusUpdate
from ..security import get_current_user, get_optional_user
from ..serializers import item_out

router = APIRouter(prefix="/items", tags=["Items"])

SORTS = {
    "newest": (Item.created_at.desc(), Item.item_id.desc()),
    "price_asc": (Item.price.asc(), Item.item_id.desc()),
    "price_desc": (Item.price.desc(), Item.item_id.desc()),
}


def _get_or_404(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _get_own_item(db: Session, item_id: int, user: User) -> Item:
    item = _get_or_404(db, item_id)
    if item.seller_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only change your own items")
    return item


@router.get("", response_model=list[ItemOut])
def list_items(
    q: Optional[str] = Query(None, description="Search in title and description"),
    category_id: Optional[int] = None,
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    condition: Optional[ItemCondition] = None,
    campus: Optional[str] = Query(None, description="Seller's campus"),
    sort: Literal["newest", "price_asc", "price_desc"] = "newest",
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=400, detail="min_price cannot be higher than max_price")

    query = (
        db.query(Item)
        .options(joinedload(Item.seller), joinedload(Item.category))
        .filter(Item.status == "available")
    )
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Item.title.ilike(like), Item.description.ilike(like)))
    if category_id is not None:
        query = query.filter(Item.category_id == category_id)
    if min_price is not None:
        query = query.filter(Item.price >= min_price)
    if max_price is not None:
        query = query.filter(Item.price <= max_price)
    if condition is not None:
        query = query.filter(Item.item_condition == condition)
    if campus and campus.strip():
        query = query.join(User, Item.seller_id == User.user_id).filter(
            User.campus.ilike(f"%{campus.strip()}%")
        )

    items = query.order_by(*SORTS[sort]).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return [item_out(i) for i in items]


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db), viewer: Optional[User] = Depends(get_optional_user)):
    item = _get_or_404(db, item_id)
    # the seller's phone number is shown only to logged-in users
    return item_out(item, include_phone=viewer is not None)


@router.post("", response_model=ItemOut, status_code=201)
def create_item(data: ItemCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.get(Category, data.category_id) is None:
        raise HTTPException(status_code=400, detail="Category does not exist")
    item = Item(seller_id=user.user_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item_out(item, include_phone=True)


@router.put("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int, data: ItemCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    item = _get_own_item(db, item_id, user)
    if db.get(Category, data.category_id) is None:
        raise HTTPException(status_code=400, detail="Category does not exist")
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    return item_out(item, include_phone=True)


@router.patch("/{item_id}/status", response_model=ItemOut)
def update_status(
    item_id: int, data: ItemStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    item = _get_own_item(db, item_id, user)
    item.status = data.status
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    return item_out(item, include_phone=True)


@router.delete("/{item_id}")
def delete_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get_or_404(db, item_id)
    if item.seller_id != user.user_id and user.role != "admin":
        raise HTTPException(status_code=403, detail="You can only delete your own items")
    image_url = item.image_url
    db.delete(item)
    db.commit()
    delete_upload(image_url)
    return {"message": "Item deleted"}


@router.post("/{item_id}/image", response_model=ItemOut)
async def upload_image(
    item_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_own_item(db, item_id, user)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    new_url = save_image(data)  # raises 400 for empty, too big or non-image files
    old_url = item.image_url
    item.image_url = new_url
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    delete_upload(old_url)
    return item_out(item, include_phone=True)
