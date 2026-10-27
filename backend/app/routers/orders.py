from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Item, Order, User
from ..schemas import OrderCreate, OrderOut, OrderStatusUpdate
from ..security import get_current_user
from ..serializers import order_out

router = APIRouter(prefix="/orders", tags=["Orders"])

# what the seller may do with a request: (current status, new status)
SELLER_MOVES = {
    ("pending", "accepted"),
    ("pending", "rejected"),
    ("accepted", "rejected"),   # the meet-up fell through, the item becomes available again
    ("accepted", "completed"),  # handed over at the meet-up
}


@router.post("", response_model=OrderOut, status_code=201)
def create_order(data: OrderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Item, data.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.seller_id == user.user_id:
        raise HTTPException(status_code=400, detail="You cannot send a request for your own item")
    if item.status != "available":
        raise HTTPException(status_code=400, detail="This item is no longer available")
    already = (
        db.query(Order)
        .filter(
            Order.buyer_id == user.user_id,
            Order.item_id == item.item_id,
            Order.status.in_(("pending", "accepted")),
        )
        .first()
    )
    if already is not None:
        raise HTTPException(status_code=400, detail="You already have an open request for this item")

    note = data.note.strip() if data.note and data.note.strip() else None
    order = Order(buyer_id=user.user_id, item_id=item.item_id, price_at_order=item.price, note=note)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order_out(order)


@router.get("/mine", response_model=list[OrderOut])
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .filter(Order.buyer_id == user.user_id)
        .order_by(Order.created_at.desc(), Order.order_id.desc())
        .all()
    )
    return [order_out(o) for o in orders]


@router.get("/received", response_model=list[OrderOut])
def received_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .join(Item, Order.item_id == Item.item_id)
        .filter(Item.seller_id == user.user_id)
        .order_by(Order.created_at.desc(), Order.order_id.desc())
        .all()
    )
    return [order_out(o) for o in orders]


@router.patch("/{order_id}/status", response_model=OrderOut)
def change_status(
    order_id: int,
    data: OrderStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    item = order.item
    new_status = data.status

    if order.buyer_id == user.user_id:
        # the buyer can only cancel a request that is still pending
        if not (order.status == "pending" and new_status == "cancelled"):
            raise HTTPException(status_code=400, detail="Buyers can only cancel a pending request")
    elif item.seller_id == user.user_id:
        if (order.status, new_status) not in SELLER_MOVES:
            raise HTTPException(
                status_code=400, detail=f"Cannot change an order from {order.status} to {new_status}"
            )
    else:
        raise HTTPException(status_code=403, detail="This order is not yours")

    if new_status == "accepted":
        if item.status != "available":
            raise HTTPException(status_code=400, detail="This item is no longer available")
        item.status = "reserved"
    elif new_status in ("rejected", "cancelled"):
        if order.status == "accepted" and item.status == "reserved":
            item.status = "available"
    elif new_status == "completed":
        item.status = "sold"
        # nobody else can buy it now, so close the other open requests
        for other in item.orders:
            if other.order_id != order.order_id and other.status == "pending":
                other.status = "rejected"

    order.status = new_status
    db.commit()
    db.refresh(order)
    return order_out(order)
