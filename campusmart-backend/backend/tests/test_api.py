from tests.conftest import admin_headers, item_payload, login, make_user, post_item, register

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


# ---------- auth ----------
def test_register_and_login(client):
    response = register(client, "a@student.ug")
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "a@student.ug"
    assert body["phone"] == "256771234567"  # 07... is converted to 256...
    assert "password_hash" not in body and "password" not in body

    headers, user = login(client, "a@student.ug")
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["user_id"] == user["user_id"]


def test_wrong_password_returns_401(client):
    register(client, "a@student.ug")
    response = client.post("/auth/login", json={"email": "a@student.ug", "password": "wrong-password"})
    assert response.status_code == 401


def test_duplicate_email_returns_400(client):
    assert register(client, "a@student.ug").status_code == 201
    assert register(client, "A@student.ug").status_code == 400


def test_invalid_input_returns_400(client):
    assert register(client, "b@student.ug", password="short").status_code == 400
    assert register(client, "not-an-email").status_code == 400
    assert register(client, "c@student.ug", phone="12345").status_code == 400


def test_protected_endpoints_need_a_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.post("/items", json=item_payload()).status_code == 401
    assert client.get("/orders/mine", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


# ---------- items ----------
def test_item_crud_and_ownership(client):
    seller, _ = make_user(client, "seller@student.ug")
    other, _ = make_user(client, "other@student.ug")

    item = post_item(client, seller)
    item_id = item["item_id"]
    assert item["status"] == "available" and item["category"]["name"] == "Books"

    assert client.get(f"/items/{item_id}").status_code == 200
    assert client.get("/items/99999").status_code == 404

    # someone else cannot change it
    assert client.put(f"/items/{item_id}", json=item_payload(), headers=other).status_code == 403
    assert client.delete(f"/items/{item_id}", headers=other).status_code == 403

    updated = client.put(f"/items/{item_id}", json=item_payload(price=20000), headers=seller)
    assert updated.status_code == 200 and updated.json()["price"] == 20000

    sold = client.patch(f"/items/{item_id}/status", json={"status": "sold"}, headers=seller)
    assert sold.json()["status"] == "sold"
    assert client.get("/items").json() == []  # sold items leave the public list

    assert client.delete(f"/items/{item_id}", headers=seller).status_code == 200
    assert client.get(f"/items/{item_id}").status_code == 404


def test_item_validation(client):
    seller, _ = make_user(client, "seller@student.ug")
    for bad in (
        item_payload(price=0),
        item_payload(title="ab"),
        item_payload(category_id=999),
        item_payload(item_condition="broken"),
        item_payload(description="x" * 501),
    ):
        assert client.post("/items", json=bad, headers=seller).status_code == 400


def test_search_filter_and_sort(client):
    seller, _ = make_user(client, "seller@student.ug", campus="Makerere University")
    post_item(client, seller, title="Calculus book", price=10000, category_id=1)
    post_item(client, seller, title="Samsung phone", price=300000, category_id=3, item_condition="like new")

    assert len(client.get("/items").json()) == 2
    assert [i["title"] for i in client.get("/items", params={"q": "samsung"}).json()] == ["Samsung phone"]
    assert len(client.get("/items", params={"category_id": 1}).json()) == 1
    assert len(client.get("/items", params={"min_price": 50000}).json()) == 1
    assert len(client.get("/items", params={"condition": "like new"}).json()) == 1
    assert len(client.get("/items", params={"campus": "makerere"}).json()) == 2
    assert client.get("/items", params={"campus": "Kyambogo"}).json() == []
    assert client.get("/items", params={"min_price": 9, "max_price": 1}).status_code == 400

    cheapest_first = client.get("/items", params={"sort": "price_asc"}).json()
    assert [i["price"] for i in cheapest_first] == [10000, 300000]
    assert client.get("/items", params={"sort": "nonsense"}).status_code == 400


def test_seller_phone_only_for_logged_in_users(client):
    seller, _ = make_user(client, "seller@student.ug")
    item_id = post_item(client, seller)["item_id"]

    assert client.get(f"/items/{item_id}").json()["seller"]["phone"] is None
    assert client.get("/items").json()[0]["seller"]["phone"] is None
    viewer, _ = make_user(client, "viewer@student.ug")
    assert client.get(f"/items/{item_id}", headers=viewer).json()["seller"]["phone"] == "256771234567"


def test_image_upload(client):
    seller, _ = make_user(client, "seller@student.ug")
    other, _ = make_user(client, "other@student.ug")
    item_id = post_item(client, seller)["item_id"]

    ok = client.post(f"/items/{item_id}/image", files={"file": ("book.png", PNG, "image/png")}, headers=seller)
    assert ok.status_code == 200
    url = ok.json()["image_url"]
    assert url.startswith("/uploads/") and client.get(url).status_code == 200

    fake = client.post(f"/items/{item_id}/image", files={"file": ("x.png", b"not an image", "image/png")}, headers=seller)
    assert fake.status_code == 400
    forbidden = client.post(f"/items/{item_id}/image", files={"file": ("book.png", PNG, "image/png")}, headers=other)
    assert forbidden.status_code == 403


# ---------- favourites ----------
def test_favorites(client):
    seller, _ = make_user(client, "seller@student.ug")
    buyer, _ = make_user(client, "buyer@student.ug")
    item_id = post_item(client, seller)["item_id"]

    assert client.post("/favorites", json={"item_id": item_id}, headers=buyer).status_code == 201
    assert client.post("/favorites", json={"item_id": item_id}, headers=buyer).status_code == 400
    assert client.post("/favorites", json={"item_id": 999}, headers=buyer).status_code == 404
    assert len(client.get("/favorites", headers=buyer).json()) == 1
    assert client.get("/favorites", headers=seller).json() == []  # each user sees only their own

    assert client.delete(f"/favorites/{item_id}", headers=buyer).status_code == 200
    assert client.delete(f"/favorites/{item_id}", headers=buyer).status_code == 404


# ---------- orders ----------
def test_order_flow(client):
    seller, _ = make_user(client, "seller@student.ug")
    buyer, _ = make_user(client, "buyer@student.ug", phone="0759999999")
    stranger, _ = make_user(client, "stranger@student.ug")
    item_id = post_item(client, seller)["item_id"]

    # rules for creating a request
    assert client.post("/orders", json={"item_id": item_id}, headers=seller).status_code == 400  # own item
    assert client.post("/orders", json={"item_id": 999}, headers=buyer).status_code == 404

    created = client.post("/orders", json={"item_id": item_id, "note": "Tomorrow at 2pm?"}, headers=buyer)
    assert created.status_code == 201
    order = created.json()
    order_id = order["order_id"]
    assert order["status"] == "pending" and order["price_at_order"] == 25000
    assert order["buyer"]["phone"] is None  # hidden until accepted
    assert client.post("/orders", json={"item_id": item_id}, headers=buyer).status_code == 400  # duplicate

    # each side sees the right lists
    assert len(client.get("/orders/mine", headers=buyer).json()) == 1
    assert len(client.get("/orders/received", headers=seller).json()) == 1
    assert client.get("/orders/received", headers=buyer).json() == []
    assert client.get("/orders/mine", headers=stranger).json() == []

    # only the two people involved can change it
    assert client.patch(f"/orders/{order_id}/status", json={"status": "accepted"}, headers=stranger).status_code == 403
    assert client.patch(f"/orders/{order_id}/status", json={"status": "accepted"}, headers=buyer).status_code == 400
    assert client.patch(f"/orders/{order_id}/status", json={"status": "completed"}, headers=seller).status_code == 400

    accepted = client.patch(f"/orders/{order_id}/status", json={"status": "accepted"}, headers=seller)
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    assert accepted.json()["buyer"]["phone"] == "256759999999"  # shared after acceptance
    assert client.get(f"/items/{item_id}").json()["status"] == "reserved"

    completed = client.patch(f"/orders/{order_id}/status", json={"status": "completed"}, headers=seller)
    assert completed.json()["status"] == "completed"
    assert client.get(f"/items/{item_id}").json()["status"] == "sold"
    assert client.post("/orders", json={"item_id": item_id}, headers=stranger).status_code == 400  # sold


def test_buyer_cancels_and_seller_rejects(client):
    seller, _ = make_user(client, "seller@student.ug")
    buyer, _ = make_user(client, "buyer@student.ug")
    item_id = post_item(client, seller)["item_id"]

    first = client.post("/orders", json={"item_id": item_id}, headers=buyer).json()["order_id"]
    cancelled = client.patch(f"/orders/{first}/status", json={"status": "cancelled"}, headers=buyer)
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/items/{item_id}").json()["status"] == "available"

    second = client.post("/orders", json={"item_id": item_id}, headers=buyer).json()["order_id"]
    client.patch(f"/orders/{second}/status", json={"status": "accepted"}, headers=seller)
    assert client.get(f"/items/{item_id}").json()["status"] == "reserved"
    rejected = client.patch(f"/orders/{second}/status", json={"status": "rejected"}, headers=seller)
    assert rejected.json()["status"] == "rejected"
    assert client.get(f"/items/{item_id}").json()["status"] == "available"  # back on the market


# ---------- messages ----------
def test_messages(client):
    seller, seller_user = make_user(client, "seller@student.ug", name="Seller One")
    buyer, buyer_user = make_user(client, "buyer@student.ug", name="Buyer Two")
    item_id = post_item(client, seller)["item_id"]

    send = client.post(
        "/messages",
        json={"receiver_id": seller_user["user_id"], "item_id": item_id, "body": "Is it still available?"},
        headers=buyer,
    )
    assert send.status_code == 201
    assert client.post("/messages", json={"receiver_id": buyer_user["user_id"], "body": "hi"}, headers=buyer).status_code == 400
    assert client.post("/messages", json={"receiver_id": 999, "body": "hi"}, headers=buyer).status_code == 404

    inbox = client.get("/messages/conversations", headers=seller).json()
    assert len(inbox) == 1
    assert inbox[0]["other_user_name"] == "Buyer Two" and inbox[0]["unread_count"] == 1
    assert inbox[0]["item_title"] == "Engineering Mathematics textbook"

    thread = client.get("/messages/thread", params={"with_user": buyer_user["user_id"], "item_id": item_id}, headers=seller)
    assert [m["body"] for m in thread.json()] == ["Is it still available?"]
    assert client.get("/messages/conversations", headers=seller).json()[0]["unread_count"] == 0  # opened = read


# ---------- categories and admin ----------
def test_categories(client):
    student, _ = make_user(client, "student@student.ug")
    assert len(client.get("/categories").json()) >= 9

    assert client.post("/categories", json={"name": "Sports"}, headers=student).status_code == 403
    admin = admin_headers(client)
    created = client.post("/categories", json={"name": "Sports", "icon": "S"}, headers=admin)
    assert created.status_code == 201
    category_id = created.json()["category_id"]
    assert client.post("/categories", json={"name": "sports"}, headers=admin).status_code == 400
    assert client.put(f"/categories/{category_id}", json={"name": "Sports gear"}, headers=admin).status_code == 200

    post_item(client, student, category_id=category_id)
    assert client.delete(f"/categories/{category_id}", headers=admin).status_code == 400  # still in use
    assert client.delete("/categories/999", headers=admin).status_code == 404


def test_admin_can_remove_any_item(client):
    seller, _ = make_user(client, "seller@student.ug")
    item_id = post_item(client, seller)["item_id"]
    assert client.delete(f"/items/{item_id}", headers=admin_headers(client)).status_code == 200


# ---------- profile ----------
def test_update_and_delete_account(client):
    headers, user = make_user(client, "me@student.ug")
    updated = client.put(
        "/users/me",
        json={"full_name": "New Name", "phone": "256700111222", "campus": "Kyambogo"},
        headers=headers,
    )
    assert updated.status_code == 200 and updated.json()["campus"] == "Kyambogo"

    item_id = post_item(client, headers)["item_id"]
    assert len(client.get("/users/me/items", headers=headers).json()) == 1

    assert client.delete("/users/me", headers=headers).status_code == 200
    assert client.get(f"/items/{item_id}").status_code == 404  # listings go with the account
    assert client.get("/auth/me", headers=headers).status_code == 401  # the token no longer works
    assert client.post("/auth/login", json={"email": "me@student.ug", "password": "password123"}).status_code == 401
