import os
import tempfile

# Point the app at a throw-away database and upload folder BEFORE importing it.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

ADMIN = {"email": "admin@campusmart.ug", "password": "Admin12345"}


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)  # every test starts with empty tables
    with TestClient(app) as test_client:  # starting the client creates tables and seeds data
        yield test_client


def register(client, email, campus="Makerere", phone="0771234567", password="password123", name="Test Student"):
    return client.post(
        "/auth/register",
        json={"full_name": name, "email": email, "phone": phone, "campus": campus, "password": password},
    )


def login(client, email, password="password123"):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]


def make_user(client, email, **kwargs):
    assert register(client, email, **kwargs).status_code == 201
    return login(client, email)


def admin_headers(client):
    headers, _ = login(client, ADMIN["email"], ADMIN["password"])
    return headers


def item_payload(**overrides):
    data = {
        "category_id": 1,
        "title": "Engineering Mathematics textbook",
        "description": "Barely used, no missing pages.",
        "price": 25000,
        "item_condition": "used good",
        "pickup_location": "Main Gate",
    }
    data.update(overrides)
    return data


def post_item(client, headers, **overrides):
    response = client.post("/items", json=item_payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()
