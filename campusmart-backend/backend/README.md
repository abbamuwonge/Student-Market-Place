# CampusMart backend (FastAPI)

REST API for the CampusMart student marketplace. It returns JSON over HTTP, stores data in SQLite
(SQLAlchemy) and protects its endpoints with bcrypt-hashed passwords and JWT tokens.

## Run it

You need Python 3.10 or newer.

```bash
cd backend
python -m venv venv

# Windows (PowerShell)
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Interactive API docs (Swagger): http://127.0.0.1:8000/docs
- The database file `campusmart.db` and the tables are created automatically on the first start.
- The 9 categories and one admin account are created automatically:
  `admin@campusmart.ug` / `Admin12345`. Change them with the environment variables
  `ADMIN_EMAIL` and `ADMIN_PASSWORD` before the first start.

### Calling the API from the Flutter app

| Where the app runs | Base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator or Flutter web | `http://127.0.0.1:8000` |
| Real phone on the same Wi-Fi | `http://<your laptop IP>:8000` (start uvicorn with `--host 0.0.0.0`) |

Photos are served from `/uploads/<file>`, so the full photo address is `<base URL>` + `image_url`.

### Using the Swagger page

1. Open `POST /auth/register`, click **Try it out** and register a user.
2. Open `POST /auth/login`, log in and copy the `access_token`.
3. Click **Authorize** at the top and paste the token. Protected endpoints now work.

## Settings (environment variables, all optional)

| Variable | Default | Meaning |
|---|---|---|
| `SECRET_KEY` | a development value | Key that signs the JWT tokens. Set your own for anything real |
| `DATABASE_URL` | `sqlite:///./campusmart.db` | Use a PostgreSQL URL to switch database |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token lifetime (24 hours) |
| `UPLOAD_DIR` | `./uploads` | Where photos are saved |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | see above | The seeded admin account |

## Endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | /auth/register | Public | Create account (201) |
| POST | /auth/login | Public | Log in, returns `access_token` |
| GET | /auth/me | Token | Current user |
| PUT | /users/me | Token | Edit profile |
| DELETE | /users/me | Token | Delete account with its data |
| GET | /users/me/items | Token | My listings |
| GET | /categories | Public | List categories |
| POST, PUT, DELETE | /categories, /categories/{id} | Admin | Manage categories |
| GET | /items | Public | Search, filter, sort, page (`q`, `category_id`, `min_price`, `max_price`, `condition`, `campus`, `sort`, `page`) |
| GET | /items/{id} | Public | Item details (seller phone only when logged in) |
| POST | /items | Token | Post an item |
| PUT | /items/{id} | Owner | Edit |
| PATCH | /items/{id}/status | Owner | available, reserved or sold |
| DELETE | /items/{id} | Owner or admin | Delete |
| POST | /items/{id}/image | Owner | Upload a JPG, PNG or WEBP photo (max 5 MB) |
| GET, POST | /favorites | Token | List or add favourites |
| DELETE | /favorites/{item_id} | Token | Remove a favourite |
| POST | /orders | Token | Send a purchase request |
| GET | /orders/mine | Token | Requests I sent |
| GET | /orders/received | Token | Requests for my items |
| PATCH | /orders/{id}/status | Buyer or seller | Buyer: cancel. Seller: accept, reject, complete |
| POST | /messages | Token | Send a message |
| GET | /messages/conversations | Token | Inbox |
| GET | /messages/thread?with_user=&item_id= | Token | Chat about an item (leave out `item_id` for chats without an item) |

Status codes: 200 OK, 201 Created, **400** invalid input (the app's validation errors come back as
`{"detail": "Validation failed", "errors": [{"field", "message"}]}`), 401 missing or invalid token,
403 not allowed, 404 not found.

### Rules built into the API

- Passwords are stored only as bcrypt hashes, and the API never returns them.
- A buyer cannot send a request for their own item, nor a second open request for the same item.
- Accepting a request sets the item to `reserved`. Completing it sets the item to `sold` and rejects the
  other pending requests. Rejecting an accepted request or cancelling a pending one makes the item
  available again.
- Buyer and seller see each other's phone number only after the request is accepted.
- Every user sees only their own favourites, orders and messages.

## Run the tests

```bash
pytest
```

The tests use a temporary database, so your real data is not touched.

## Project layout

```
backend/
  app/
    main.py          app, CORS, 400 error handler, routers
    config.py        settings
    database.py      engine and session
    models.py        the 6 tables (users, categories, items, orders, favorites, messages)
    schemas.py       request and response validation
    security.py      bcrypt, JWT, login dependencies
    serializers.py   hides phone numbers when not allowed
    files.py         photo saving and deleting
    seed.py          categories and admin account
    routers/         auth, users, categories, items, favorites, orders, messages
  tests/             pytest tests
  uploads/           saved photos (not committed)
  requirements.txt
```
