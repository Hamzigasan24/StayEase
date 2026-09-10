# StayEase
Hotel Reservation & Management System

## Project Description

StayEase is a hotel reservation and management backend system built with FastAPI. It provides authentication, hotel and room management, reservation processing, simulated payments, check-in/check-out, administrative reporting, advanced search, and flexible MongoDB-based features such as reviews, notifications, activity logs, and search history.

> **School project note:** payments are **simulated** for academic/demo purposes — no real gateway, no card numbers/CVV/OTPs are ever collected, stored, or processed.

## Features

- **Authentication** — register/login, Argon2id password hashing, JWT (30-min expiry), admin + guest roles
- **Hotel management** — full CRUD, search, city filter, sorting, pagination, per-hotel room counts
- **Room management** — CRUD, status/floor/number filters, enriched date-aware availability search
- **Reservations** — booking with overlap protection, server-side pricing, update/cancel, lifecycle
- **Payments** — simulated create/process/refund, no-overpayment rule, balance history
- **Check-in/check-out** — admin-only, payment + date gates, room occupancy updates
- **Reviews** — ratings 1–5, one per stay, ownership enforced (MongoDB)
- **Notifications** — booking/payment/stay events, per-user isolation (MongoDB)
- **Activity logs** — append-only backend audit trail, admin-only reads (MongoDB)
- **Search history** — per-user searches, ownership enforced (MongoDB)
- **Dashboard** — admin-only live stats: users, rooms, reservations, revenue, occupancy, monthly revenue, recents, activity
- **Advanced search** — filtering, whitelisted sorting, `page`/`page_size` pagination on every list endpoint
- **Validation & errors** — Pydantic validation, standard error envelope, global handlers, safe logging

## Technologies

Python · FastAPI · Pydantic (v2 + pydantic-settings) · PostgreSQL · SQLAlchemy · psycopg · MongoDB · PyMongo · JWT (python-jose) · Argon2id (pwdlib) · pytest (+ pytest-cov) · Docker

## Architecture

MVC-inspired separation:

```text
app/
├── config.py            # centralized pydantic-settings (single source of truth)
├── main.py              # app factory wiring: routers, CORS, handlers, lifespan
├── models/              # SQLAlchemy tables (postgres) + Mongo document builders
├── schemas/             # Pydantic request/response validation
├── controllers/         # business logic + database operations (routes stay thin)
├── routes/              # FastAPI APIRouter endpoints (HTTP concerns only)
├── database/            # postgres.py (engine/session/Base/get_db),
│                        # mongodb.py (client/indexes), init_db.py (DDL helper)
└── utils/               # auth (JWT deps), security (hashing), errors (envelope),
                         # query_helpers (paging/sort), mongo_helpers (ObjectId),
                         # logging via stdlib
tests/                   # pytest suite, isolated test databases
scripts/create_admin.py  # secure first-admin creation
```

## Database Design

**PostgreSQL** — structured transactional data (source of truth):

```text
users 1──1 guests
hotels 1──* rooms *──1 room_types
guests/hotels/rooms 1──* reservations 1──* payments
```

Tables: `users` (unique email, `password_hash`, role `guest|admin`), `hotels`, `room_types` (`Numeric` price, capacity), `rooms` (unique number per hotel, status), `guests` (unique `user_id`), `reservations` (dates, `Numeric` total, lifecycle status + UTC timestamps), `payments` (`Numeric` amount, method, status, unique-style `STAY-…` reference, UTC `paid_at`). All timestamps are `TIMESTAMPTZ`; money is always `Numeric`/`Decimal`, never float.

**MongoDB** — flexible secondary data (references PG rows by integer id only): `reviews`, `notifications`, `activity_logs` (backend-written, append-only), `search_history`. A MongoDB outage never breaks primary PostgreSQL flows (secondary writes are best-effort).

## Installation

```bash
git clone <repository-url>
cd StayEase
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` (see Environment Variables). Start PostgreSQL + MongoDB locally, e.g. on Fedora:

```bash
sudo dnf install -y postgresql postgresql-server
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql
sudo -i -u postgres psql -c "CREATE USER stayease WITH PASSWORD 'choose-a-strong-password';"
sudo -i -u postgres psql -c "CREATE DATABASE stayease_db OWNER stayease;"
# MongoDB: install from docs.mongodb.com, then: sudo systemctl enable --now mongod
```

Create tables (idempotent, never drops data):

```bash
python -m app.database.init_db
```

Create the first admin (public registration only makes guests):

```bash
python scripts/create_admin.py --name "Ada Admin" --email ada@example.com
```

## Running

```bash
uvicorn app.main:app --reload
```

API: <http://127.0.0.1:8000/> · Health: `/health`, `/health/ready`

## Swagger

Interactive docs: <http://127.0.0.1:8000/docs> (Authorize button takes the JWT from `POST /auth/login`), alternative: `/redoc`, raw spec: `/openapi.json`. Tags: Auth, Hotels, Room Types, Rooms, Guests, Reservations, Payments, Reviews, Notifications, Search History, Activity Logs, Admin Dashboard, Health, MongoDB.

## Testing

```bash
pytest -v                          # full suite (121 tests, isolated DBs)
pytest tests/test_auth.py -v       # one file
pytest --cov=app --cov-report=term-missing   # coverage (90% total)
```

Tests use dedicated `stayease_test_db` / `stayease_test` databases (auto-created, cleaned per test) — production/dev data is never touched.

Typical guest flow under test: register → login → search hotels/rooms → availability → reservation (server-priced) → payment → process → confirmed → check-in (occupied) → check-out (available); plus cancel, review, notifications, and all 401/403/404/409/422 paths.

## Docker

```bash
docker compose up --build       # foreground
docker compose up -d --build    # background
docker compose down             # stop (pgdata/mongodata volumes keep data)
```

The image is non-root, has no `--reload`, and never contains `.env`. Inside compose the API reaches databases at hostnames `postgres`/`mongodb`. Production must export a real `SECRET_KEY`, `POSTGRES_PASSWORD`, and `CORS_ORIGINS` (compose values are dev placeholders).

## Environment Variables

| Variable | Purpose | Example |
|---|---|---|
| `APP_NAME/VERSION/ENV` | identity (`development\|production\|testing`) | `StayEase Hotel Reservation API` |
| `DEBUG` | dev diagnostics (keep `false` in prod) | `true` |
| `HOST`/`PORT` | bind address | `0.0.0.0` / `8000` |
| `DATABASE_URL` | PostgreSQL (psycopg) | `postgresql+psycopg://USER:PASS@localhost:5432/stayease_db` |
| `MONGODB_URL`/`MONGODB_DATABASE` | MongoDB | `mongodb://localhost:27017` / `stayease_db` |
| `SECRET_KEY` | JWT signing (≥32 random chars, required) | generate via `secrets.token_urlsafe(48)` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | token lifetime | `30` |
| `CORS_ORIGINS` | allowed browser origins (comma-separated) | `http://localhost:3000` |
| `TEST_DATABASE_URL`/`TEST_MONGO_DATABASE` | pytest databases only | `…/stayease_test_db` / `stayease_test` |

## API Routes (72 operations)

AUTH — `POST /auth/register` (201, always guest) · `POST /auth/login` (JWT) · `GET /auth/me`
HOTELS — `POST/GET /hotels` (search/city/sort/page) · `GET/PUT/DELETE /hotels/{id}`
ROOM TYPES — `POST/GET /room-types` (search/price/capacity/sort/page) · `GET/PUT/DELETE /room-types/{id}`
ROOMS — `POST/GET /rooms` (hotel/type/status/floor/number/sort/page) · `GET /rooms/available` (dates/guests/price + enriched hits) · `GET/PUT/DELETE /rooms/{id}`
GUESTS (admin) — `POST/GET /guests` (search/page) · `GET/PUT/DELETE /guests/{id}`
RESERVATIONS — `POST/GET /reservations` (filters/date ranges/sort/page, own-scoped) · `GET /reservations/available` · `GET /reservations/today` (admin) · `GET /reservations/{id}` · `GET /reservations/{id}/payments` · `PUT /reservations/{id}` · `POST /reservations/{id}/cancel|check-in|check-out` · `DELETE /reservations/{id}` (admin)
PAYMENTS (simulated) — `POST/GET /payments` (filters/sort/page, own-scoped) · `GET /payments/{id}` · `POST /payments/{id}/process|refund` (refund = admin)
REVIEWS — `POST/GET /reviews` · `GET/PUT/DELETE /reviews/{id}` (own or admin)
NOTIFICATIONS — `POST/GET /notifications` · `GET /notifications/{id}` · `PUT /notifications/{id}/read` · `DELETE /notifications/{id}` (own or admin)
ACTIVITY LOGS (admin) — `POST/GET /activity-logs` · `GET /activity-logs/{id}`
SEARCH HISTORY — `POST/GET /search-history` · `GET/DELETE /search-history/{id}` (own or admin)
ADMIN DASHBOARD (admin) — `GET /admin/dashboard|/reservations|/rooms|/revenue|/occupancy|/recent-reservations|/recent-payments|/monthly-revenue|/hotels|/activity`
SYSTEM — `GET /` · `GET /database/test` · `GET /mongodb/test` · `GET /health` · `GET /health/ready`

List endpoints return `{"items": [...], "pagination": {...}}`. Errors return `{"success": false, "error": {"code", "message", "details"}}` with 400/401/403/404/409/422/500/503 as appropriate.

## Security

- JWT Bearer auth; `require_admin` (403) vs `get_current_user` (401); ownership enforced per-resource (cross-user access → 403); role comes from JWT/DB, never the body
- Argon2id password hashing; hashes never serialized, logged, or stored in plaintext
- Secrets only via environment (central `app/config.py`); `.env` git-ignored; `.env.example` has placeholders; weak/missing `SECRET_KEY` refuses to boot
- Whitelisted sorting (no SQL interpolation), Pydantic validation + `extra="forbid"` on updates, mass-assignment blocked (status/totals/timestamps backend-only)
- Generic error responses (no traces/SQL/paths/secrets); `get_db` rolls back failures; security headers middleware; CORS explicit origins only

## Database

PostgreSQL (users → guests → reservations → payments; hotels/rooms/types) is transactional truth with FKs, unique constraints, and date/status/FK indexes. MongoDB (reviews, notifications, activity_logs, search_history) is flexible secondary storage keyed by integer PG ids with ObjectIds serialized as hex strings. Health: `/health/ready` reports both.

## Project Structure

```text
StayEase/
├── app/
│   ├── config.py
│   ├── main.py
│   ├── models/              # 7 SQLAlchemy tables + 4 Mongo document builders
│   ├── controllers/         # 13 business-logic modules
│   ├── routes/              # 17 routers (72 operations)
│   ├── schemas/             # 16 Pydantic modules
│   ├── database/            # postgres.py, mongodb.py, init_db.py
│   └── utils/               # auth, security, errors, query/mongo helpers
├── tests/                   # 17 files, 121 tests, isolated DBs
├── scripts/create_admin.py
├── .env                     # local only, NEVER committed
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```
