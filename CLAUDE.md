# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Single-tenant guesthouse management system (branded "Retreat 480" in the UI). One React SPA with two surfaces:
- **Staff app** (`/app/*`, login at `/login`) — dashboard (floor-plan room status), calendar, bookings, guests, rooms, WhatsApp pairing, audit log, user management.
- **Door client** (`/door/:roomHash`) — public PIN keypad reached via a per-room QR code. `roomHash` is the room's `public_id`, **not** its numeric `id`.

Stack: FastAPI (async) + PostgreSQL via SQLAlchemy 2.0 async + Alembic; React 18 + Vite + TanStack Query + Tailwind; a Node/Baileys WhatsApp sidecar in `whatsapp/`.

## Commands

Local full stack uses **`podman-compose.yml`** (reads `.env`; copy from `.env.example`):
```bash
podman-compose up --build
```
Frontend on `8080`, backend on `8000`. `docker-compose.yaml` is the **production compose for Coolify** (no published ports, requires `SECRET_KEY` and `ADMIN_PASSWORD`). `docker-compose.override.yml` is gitignored and local-only. The README's port 80 / `/admin` URLs are out of date.

Backend dev (needs a running postgres):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://guesthouse:guesthouse@localhost:5432/guesthouse DEBUG=true
alembic upgrade head
uvicorn app.main:app --reload
```
`DEBUG=true` is needed locally: with `DEBUG=false` startup refuses to boot while `SECRET_KEY` or `ADMIN_PASSWORD` are at their defaults. API docs at `/docs` and `/redoc`.

New migration after a model change (models must be imported in `app/models/__init__.py` for autogenerate to see them):
```bash
alembic revision --autogenerate -m "describe change"
```

Frontend dev (Vite proxies `/api` → `localhost:8000`):
```bash
cd frontend
npm install
npm run dev        # :5173
npm run build      # tsc typecheck + vite build (the real correctness check)
```
`npm run lint` runs eslint (flat config in `eslint.config.js`: typescript-eslint + react-hooks). CI runs it on every push.

Backend tests (`backend/tests/`, pytest + a disposable Postgres; the schema is rebuilt from migrations at session start, so never point it at a real DB):
```bash
docker run -d --name unvrs-test-pg -e POSTGRES_USER=guesthouse -e POSTGRES_PASSWORD=guesthouse \
  -e POSTGRES_DB=guesthouse_test -p 5433:5432 postgres:16-alpine
cd backend && pip install -r requirements-dev.txt
python -m pytest -q                       # TEST_DATABASE_URL overrides the default :5433 URL
python -m pytest -q tests/test_door.py -k rate_limit   # one file / one test
```
Fixtures in `tests/conftest.py` give you `anon`, `admin`, `frontdesk` clients and `guest`/`room`/`book()` helpers. The frontend has no unit tests; `npm run lint` (eslint) and `npm run build` (tsc) are its gates. CI (`.github/workflows/ci.yml`) runs pytest, pip-audit, the frontend lint+build and npm audit on every push.

## Backend architecture (`backend/app/`)

- **Layered by kind**: `models/`, `schemas/`, `routers/`, `utils/`, one file per domain in each layer. All routers are mounted under `/api/v1` in `main.py`, and each declares its own sub-prefix.
- **Authorization is applied at mount time in `main.py`**, not per endpoint: `auth` and `door` are public, `dashboard/guests/assignments/rooms` get `get_current_user` (any staff), and `audit/messaging` get `require_admin`. `users` enforces admin inside its own router. When adding a router, choose the right group there. Roles are `admin` and `frontdesk` (`models/user.py`).
- **Staff auth**: an HS256 JWT in the httponly `gh_session` cookie (`dependencies.py`, `utils/auth.py`). The token carries `tv` (the user's `token_version`); changing a password bumps `token_version`, so a password change signs that user's existing sessions out (`get_current_user` rejects an older `tv` with 401). Logout only clears the cookie on the current device. On every startup, `_ensure_admin()` creates or **resets** the master admin from `ADMIN_USERNAME`/`ADMIN_PASSWORD` (bumping `token_version` if the password changed), so in-app password changes to that account don't survive a restart.
- **DB session lifecycle** (`get_db` in `database.py`) commits on a clean request and rolls back on exception. Routers use `db.add`/`db.delete`/`await db.flush()` and must **not call `db.commit()`**.
- **Schema is managed by Alembic** (`backend/alembic/versions/`). The backend container runs `alembic upgrade head` before uvicorn (see `backend/Dockerfile`). There is no `create_all`, so every model change needs a migration.
- **Audit logging**: mutating operations call `await audit_log.log(db, "<domain>.<action>", message)` (`utils/audit.py`), which adds a row to the same session (e.g. `assignment.pin_regenerated`, `door.access`, `door.checkin`). Rows capture the acting user (contextvar set in `get_current_user`) and client IP (request middleware) automatically. For events on an error path that rolls the request back — failed login, rejected door PIN — use `audit_log.log_detached(...)`, which commits in its own session. Reference guests/rooms by id, not name, so a deleted record's PII doesn't linger.
- **Door flow** (`routers/door.py`): `validate-pin` is rate-limited in memory (`utils/ratelimit.py`, per room and per IP, single-instance only). The client IP is found by walking `X-Forwarded-For` from the right and skipping addresses in `TRUSTED_PROXIES` (groups `private` and `cloudflare`, or CIDRs), because every proxy *appends* and the left-most entries are client-controlled. Production sits behind Cloudflare → Traefik → nginx. The lookup matches `GuestRoom` by room `public_id` + 6-digit PIN **and** the `check_in`/`check_out` window in one query; every failure is the same 401 so the response can't reveal that a PIN belongs to a past or future stay. On the first success it sets `checked_in_at`, which moves a room from booked to checked-in. It is a one-shot check: no cookie or session is issued, and the `tokens` table is currently unused.
- **A guest can have several stays in the same room** (no unique constraint on `(guest_id, room_id)` since migration `a7c1d2e3f4b5`); the only booking rule is no overlapping dates per room, checked in `routers/assignments.py`. PINs are unique per room (`uq_guest_rooms_room_pin`); `_unique_pin()` draws one that doesn't collide within the room.
- **Room status** (`available | booked | checked_in | checked_out`) is computed in `routers/dashboard.py::_room_status` from events (`checked_in_at`, `check_out`, `rooms.cleaned_at` set by `POST /rooms/{id}/cleaned`), not from the clock alone. A reservation that lapses with no PIN entry counts as a no-show.
- **Messaging** (`utils/messaging.py`, `POST /assignments/{id}/send-pin`): sends the PIN over the requested channels concurrently (DB writes happen after the network I/O, not during it) — the door link/QR go via the WhatsApp sidecar (`WHATSAPP_SERVICE_URL`, Bearer `WHATSAPP_API_TOKEN` — the sidecar refuses to start without the token, and both compose files require it) or the sms-gate.app gateway. If a provider URL is empty, nothing is delivered: the send is logged at INFO (recipient and length only, never the body) and recorded with `status="mocked"` so the UI can say so; real deliveries are `sent`, provider errors `failed`. Phone numbers are normalized using `DEFAULT_COUNTRY_CODE`. Sends are recorded in `message_log`.
- **Room images** are stored as blobs in Postgres (`room_image`) and served through `/rooms/{id}/images/{image_id}`. nginx caps uploads at 6 MB, and the backend enforces 5 MB. `RoomImage.content` is **deferred**: listing rooms/bookings never loads the bytes; load them explicitly with `undefer(RoomImage.content)` when serving. Cascading relationships use `passive_deletes=True` and rely on the FKs' `ON DELETE CASCADE`.
- **Users**: the env master admin (`ADMIN_USERNAME`) cannot be edited or deleted in-app, an admin cannot change their own role, and the last admin cannot be demoted or deleted (`routers/users.py`).
- **Times**: stored in UTC. `TIMEZONE` (default `Europe/Bucharest`) is only used to format dates in guest messages.
- **Config** is pydantic-settings (`config.py`). `FRONTEND_ORIGIN` is both the single CORS origin and the base URL of door/QR links. `DEBUG` only relaxes the startup secrets check; SQL statement logging is the separate `SQL_ECHO` (statements contain PINs).
- **Input validation**: Pydantic schemas carry `max_length` matching the `String(n)` columns and list endpoints bound `skip`/`limit` with `Query(ge=…, le=500)`, so bad input is a 422. Unique/FK violations that still reach the DB become a 409 via the `IntegrityError` handler in `main.py` (add new constraint names to `_UNIQUE_MESSAGES` there). The frontend interceptor flattens 422 `detail` lists into `field: message` strings.

## Frontend architecture (`frontend/src/`)

- `api/` has one module per backend resource plus shared DTOs in `types.ts`. `client.ts` is an axios instance (`baseURL: "/api/v1"`, `withCredentials`) that turns FastAPI's `detail` into `Error.message` and redirects to `/login` on a 401 under `/app`.
- Routing is in `App.tsx`. Admin-only pages sit under the `<RequireAdmin>` layout route (a UI guard only; the backend enforces access). `useMe()` provides the current user and role.
- `lib/roomStatus.ts` is the **single source of truth for room-status labels and colours**, shared by the dashboard blueprint and the calendar. Change colours there, not in individual pages.
- Server state is TanStack Query; toasts via `react-hot-toast`. After a mutation, invalidate through the helpers in `lib/queries.ts` (`invalidateBookingViews`, `invalidateRoomViews`, `invalidateGuestViews`) — bookings feed the dashboard and room views too, so a bare `["assignments"]` invalidation leaves them stale. Shared UI lives in `components/` (`Modal`, `ConfirmDialog` with `confirmLabel`, `Spinner`, `ErrorState`, `ViewToggle`). List pages branch on `isError` → `ErrorState` before `isLoading`, so a failed fetch never looks like an empty list; destructive actions go through `ConfirmDialog`.
- In production, nginx (`frontend/nginx.conf`) serves the SPA and proxies `/api/` → `backend:8000`.

## Other references

- `CODEBASE_AUDIT.md` (gitignored, local only) is a full audit dated 2026-10-28 with the status of every finding. If present, check the code before acting on an item; fixes may have landed since.
- Production runs on Coolify (`docker-compose.yaml`, domain configured there). Don't deploy or touch it unless explicitly asked.
