from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Item
from ..schemas import CategoryCreate, CategoryOut
from ..security import require_admin

router = APIRouter(prefix="/categories", tags=["Categories"])


def _get_or_404(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def _name_taken(db: Session, name: str, ignore_id: int | None = None) -> bool:
    query = db.query(Category).filter(Category.name.ilike(name))
    if ignore_id is not None:
        query = query.filter(Category.category_id != ignore_id)
    return query.first() is not None


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.category_id).all()


@router.post("", response_model=CategoryOut, status_code=201, dependencies=[Depends(require_admin)])
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    if _name_taken(db, data.name):
        raise HTTPException(status_code=400, detail="A category with this name already exists")
    category = Category(name=data.name, icon=data.icon)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_admin)])
def update_category(category_id: int, data: CategoryCreate, db: Session = Depends(get_db)):
    category = _get_or_404(db, category_id)
    if _name_taken(db, data.name, ignore_id=category_id):
        raise HTTPException(status_code=400, detail="A category with this name already exists")
    category.name = data.name
    category.icon = data.icon
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", dependencies=[Depends(require_admin)])
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = _get_or_404(db, category_id)
    if db.query(Item).filter(Item.category_id == category_id).count() > 0:
        raise HTTPException(status_code=400, detail="Cannot delete a category that still has items")
    db.delete(category)
    db.commit()
    return {"message": "Category deleted"}
