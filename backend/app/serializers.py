"""Turn database rows into response models, hiding phone numbers unless allowed."""
from .models import Item, Order
from .schemas import ItemOut, OrderOut


def item_out(item: Item, include_phone: bool = False) -> ItemOut:
    out = ItemOut.model_validate(item)
    if not include_phone:
        out.seller.phone = None
    return out


def order_out(order: Order) -> OrderOut:
    """Buyer and seller see each other's phone only once the request is accepted or completed."""
    out = OrderOut.model_validate(order)
    if order.status not in ("accepted", "completed"):
        out.buyer.phone = None
        out.seller.phone = None
    return out
