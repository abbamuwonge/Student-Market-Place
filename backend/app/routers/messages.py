from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Item, Message, User
from ..schemas import ConversationOut, MessageCreate, MessageOut
from ..security import get_current_user

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("", response_model=MessageOut, status_code=201)
def send_message(data: MessageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.receiver_id == user.user_id:
        raise HTTPException(status_code=400, detail="You cannot message yourself")
    if db.get(User, data.receiver_id) is None:
        raise HTTPException(status_code=404, detail="Receiver not found")
    if data.item_id is not None and db.get(Item, data.item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found")
    message = Message(
        sender_id=user.user_id, receiver_id=data.receiver_id, item_id=data.item_id, body=data.body
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/conversations", response_model=list[ConversationOut])
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The inbox: one entry per (other person, item), newest first."""
    messages = (
        db.query(Message)
        .filter(or_(Message.sender_id == user.user_id, Message.receiver_id == user.user_id))
        .order_by(Message.sent_at.desc(), Message.message_id.desc())
        .all()
    )
    found: dict[tuple, dict] = {}
    for m in messages:
        other_id = m.receiver_id if m.sender_id == user.user_id else m.sender_id
        entry = found.get((other_id, m.item_id))
        if entry is None:
            entry = {
                "other_user_id": other_id,
                "item_id": m.item_id,
                "last_message": m.body,
                "last_sender_id": m.sender_id,
                "last_sent_at": m.sent_at,
                "unread_count": 0,
            }
            found[(other_id, m.item_id)] = entry
        if m.receiver_id == user.user_id and not m.is_read:
            entry["unread_count"] += 1

    other_ids = {e["other_user_id"] for e in found.values()}
    item_ids = {e["item_id"] for e in found.values() if e["item_id"] is not None}
    names = {}
    if other_ids:
        names = {u.user_id: u.full_name for u in db.query(User).filter(User.user_id.in_(other_ids))}
    titles = {}
    if item_ids:
        titles = {i.item_id: i.title for i in db.query(Item).filter(Item.item_id.in_(item_ids))}

    return [
        ConversationOut(
            other_user_name=names.get(e["other_user_id"], "Unknown"),
            item_title=titles.get(e["item_id"]),
            **e,
        )
        for e in found.values()
    ]


@router.get("/thread", response_model=list[MessageOut])
def thread(
    with_user: int = Query(..., description="The other person"),
    item_id: Optional[int] = Query(None, description="The item being discussed (leave out for chats without an item)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Message).filter(
        or_(
            (Message.sender_id == user.user_id) & (Message.receiver_id == with_user),
            (Message.sender_id == with_user) & (Message.receiver_id == user.user_id),
        )
    )
    query = query.filter(Message.item_id == item_id) if item_id is not None else query.filter(Message.item_id.is_(None))
    messages = query.order_by(Message.sent_at.asc(), Message.message_id.asc()).all()

    # opening the chat marks what the other person sent as read
    changed = False
    for m in messages:
        if m.receiver_id == user.user_id and not m.is_read:
            m.is_read = True
            changed = True
    if changed:
        db.commit()
    return messages
