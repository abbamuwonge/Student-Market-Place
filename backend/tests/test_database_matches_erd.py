"""Runs the same database check as `python check_database.py`, so `pytest` also protects the ERD."""
from app.database import engine
from check_database import normalise_type, run_checks
from tests.conftest import make_user, post_item


def _assert_clean(report):
    assert report.failures == [], "\n".join(report.failures)


def test_empty_database_matches_the_erd(client):
    _assert_clean(run_checks(engine))


def test_database_still_clean_after_normal_use(client):
    seller, seller_user = make_user(client, "seller@student.ug")
    buyer, buyer_user = make_user(client, "buyer@student.ug")
    item_id = post_item(client, seller)["item_id"]

    client.post("/favorites", json={"item_id": item_id}, headers=buyer)
    order_id = client.post("/orders", json={"item_id": item_id}, headers=buyer).json()["order_id"]
    client.patch(f"/orders/{order_id}/status", json={"status": "accepted"}, headers=seller)
    client.post(
        "/messages",
        json={"receiver_id": seller_user["user_id"], "item_id": item_id, "body": "See you at the gate"},
        headers=buyer,
    )

    report = run_checks(engine)
    _assert_clean(report)
    assert report.warnings == []  # the reserved item has its accepted order


def test_type_names_are_comparable():
    assert normalise_type("INT") == normalise_type("INTEGER")
    assert normalise_type("NUMERIC(12, 0)") == normalise_type("DECIMAL(12,0)")
    assert normalise_type("TIMESTAMP") == normalise_type("DATETIME")
