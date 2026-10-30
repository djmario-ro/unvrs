# UNVRS — Guesthouse Management

A single-tenant guesthouse application with a React frontend, FastAPI backend,
and PostgreSQL database.

## Application

- Staff login with admin and front-desk roles
- Room-status dashboard, reservation calendar, and booking wizard
- Guests, rooms and photos, repeat stays, and booking overlap checks
- Permanent room QR links, stay-specific PINs, and check-in on first door access
- Audit history and admin user management
- Optional WhatsApp/SMS PIN delivery (mocked until providers are configured)

Staff enter at `/login` and work under `/app`. Guests scan a room QR to open
`/door/<room-public-id>`. Existing `/admin` links redirect to the staff app.
Interactive API documentation is available at the backend's `/docs` endpoint.

## Kubernetes staging

Staging staff login: https://unvrs-staging.cloud.retreat480.com/login.
Staff use the application account configured in the backend Kubernetes Secret.
HTTP Basic authentication is disabled. Room QR pages and PIN validation are
public; opening a door still requires a PIN valid for that room's current stay.

The existing main-branch delivery system is retained: multi-architecture images
and digest-locked OCI charts in Harbor, explicitly promoted through Argo CD.
The three charts are `charts/db`, `charts/backend`, and `charts/frontend`.
The database chart manages a dedicated database/role on the shared CloudNativePG
cluster, rather than running a separate PostgreSQL instance.

See [deployment instructions](charts/README.md) for credentials, the one-time
v1 schema reset, automatic migration Jobs, promotion, and messaging deployment.
The friend's Coolify Compose deployment and separate CI workflow are not used.

## Local containers

```sh
cp .env.example .env
# Edit .env: set a strong SECRET_KEY and ADMIN_PASSWORD.
podman-compose up -d db
podman-compose run --rm backend alembic upgrade head
podman-compose up --build -d
```

Frontend: http://localhost:8080/login. API: http://localhost:8000/docs.
For Docker, use `docker compose -f podman-compose.yml` in place of
`podman-compose`. Apply migrations again after application schema updates.
An existing v1 local database also needs a deliberate reset before running the
initial Alembic migration; Kubernetes reset instructions target staging only.

## Development without containers

Start a disposable local PostgreSQL database, then:

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
# Set DATABASE_URL, SECRET_KEY, and ADMIN_PASSWORD in the environment.
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal, run `npm ci && npm run dev` from `frontend/`.
Set `FRONTEND_ORIGIN=http://localhost:5173` for this setup.

## Validation

```sh
# Backend: TEST_DATABASE_URL MUST point at a disposable database.
# The test fixture drops and recreates its public schema.
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5433/guesthouse_test python -m pytest -q

# Frontend (from frontend/)
npm ci
npm run lint
npm run build

# Charts (from repository root)
helm lint charts/db charts/backend charts/frontend
```

The backend tests build their schema from Alembic migrations and exercise staff
roles, bookings, door access, photos, validation, sessions, and rate limits.
