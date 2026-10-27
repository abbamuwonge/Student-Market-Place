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

## Testing (analyst role)

Three checks, from fastest to most complete.

### 1. Database check: does the real database match the ERD?

```bash
python check_database.py          # PASS or FAIL for every table
python check_database.py --show   # also prints each real table column by column, for the demo
```

Start the API once first so the database exists. The script compares `campusmart.db` with the ERD and
data dictionary in the design document: tables, columns, types, NOT NULL, primary keys, foreign keys and
unique fields. It also checks the data: no orphan rows, passwords stored as bcrypt hashes, no duplicate
emails, no order for the buyer's own item, no message to oneself, no item price of 0 or less.
It exits with code 1 when something does not match, so it also works in a script.

If the ERD changes, update `SPEC` at the top of `check_database.py` together with `app/models.py`.

### 2. Automated tests (pytest)

```bash
pytest
```

The tests use a temporary database, so your real data is not touched. They cover login rules, 400 and 401
responses, ownership (403), search and filters, favourites, the order life cycle, messages, admin rules
and account deletion, and they run the database check as well.

### 3. Postman collection: the whole API

File: `postman/CampusMart.postman_collection.json` (79 requests, positive and negative cases, each with tests).

1. Start the API (`uvicorn app.main:app --reload`).
2. In Postman choose **Import** and pick the file.
3. Open the collection, check the variables `baseUrl`, `adminEmail` and `adminPassword`.
4. Click **Run** (Collection Runner) and run all requests in order. It registers two fresh users, saves their
   tokens and ids in variables, runs every endpoint, and deletes the test users at the end.
5. Expected result: every test passes. The only request that needs you is
   **Upload photo**: pick a real JPG or PNG in its Body tab. Without a file it correctly returns 400, and the
   collection accepts that.

Command line (needs Node.js): `npx newman run postman/CampusMart.postman_collection.json`

Each request's description names the requirement it checks (FR1, NFR5, and so on) so the results can be
copied into the testing part of the report.

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
  tests/             pytest tests (including the database check)
  postman/           Postman collection for the whole API
  check_database.py  compares the real database with the ERD
  uploads/           saved photos (not committed)
  requirements.txt
```
