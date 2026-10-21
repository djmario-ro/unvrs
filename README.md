# Guesthouse Management System

A single-tenant internal management system for a guesthouse.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Podman / Docker                                         │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐   ┌────────────┐  │
│  │  Frontend    │───▶│   Backend    │──▶│ PostgreSQL │  │
│  │  React/Nginx │    │   FastAPI    │   │  (port 5432│  │
│  │  (port 80)   │    │  (port 8000) │   └────────────┘  │
│  └──────────────┘    └──────────────┘                    │
└──────────────────────────────────────────────────────────┘
```

## Features

### Admin panel (`/admin`)
- **Guests** – full CRUD (name, email, phone, address, notes)
- **Rooms** – full CRUD + QR code generation per room
- **Assignments** – link guests to rooms; PIN is auto-generated on assignment
  - Each guest/room pair gets a unique 6-digit PIN
  - PINs can be regenerated at any time
  - Optional check-in / check-out date windows
- **Audit log** – every create/update/delete/door-access is recorded

### Door client (`/door/:roomId`)
- Opened by scanning the QR code posted at the room door
- Displays a numeric keypad; guest enters their 6-digit PIN
- FastAPI validates the PIN and issues an **httponly session cookie**
- On success shows "Door is open" with the guest name
- Auto-resets after 10 seconds

## Data model

```
guests
  id · firstname · lastname · email · phone · address · notes

rooms
  id · name · description

guest_rooms            ← one row per guest↔room link
  id · guest_id · room_id · pin · check_in · check_out

tokens                 ← door session tokens
  id · assignment_id · token · valid_until · revoked_at

audit
  id · operation · message · created_at
```

## Quick start

```bash
# 1. Clone
git clone <repo-url> && cd unvrs

# 2. Copy env and tweak secrets
cp .env .env.local   # edit .env, keep .env out of git

# 3. Start everything
podman-compose up --build

# OR with docker-compose:
docker compose up --build
```

- Admin panel → http://localhost/admin
- API docs    → http://localhost:8000/docs
- Door client → http://localhost/door/<room_id>  (or scan the QR)

## Development (no containers)

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Start a local postgres first, then:
DATABASE_URL=postgresql+asyncpg://... uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev        # proxies /api → localhost:8000
```

## API overview

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/v1/guests` | List / create guests |
| GET/PATCH/DELETE | `/api/v1/guests/{id}` | Read / update / delete |
| GET/POST | `/api/v1/rooms` | List / create rooms |
| GET | `/api/v1/rooms/{id}/qr` | Download QR PNG |
| GET/POST | `/api/v1/assignments` | List / create assignments |
| POST | `/api/v1/assignments/{id}/regenerate-pin` | New PIN |
| POST | `/api/v1/door/validate-pin` | Validate PIN, set cookie |
| POST | `/api/v1/door/logout` | Clear cookie |
| GET | `/api/v1/audit` | Audit log |

Full interactive docs at `/docs` (Swagger UI) or `/redoc`.

## Kubernetes staging

The Helm deployment uses three independent charts in `charts/db`,
`charts/backend`, and `charts/frontend`. See [deployment instructions](charts/README.md)
for image distribution, required secrets, storage, and repeat deployments.

Staging: https://unvrs-staging.cloud.retreat480.com/admin (HTTP Basic login required).
