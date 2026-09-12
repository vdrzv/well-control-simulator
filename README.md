# Well Control Simulator

A web-based well control training simulator. Users select a training scenario and operate the choke, pump, and drilling fluid controls while monitoring pressure and fluid distribution in the well. The application stores simulation runs, monitors pressure limits, and provides a final analysis for each completed scenario.

## Features

- Local user registration and sign-in;
- Optional sign-in with Google, LinkedIn, and Facebook;
- Training scenarios with individual well parameters;
- Interactive control of the choke, pump speed, and heavy drilling fluid supply;
- Pause, fast-forward, and manual simulation completion;
- Maximum wellhead, bottomhole, and pump pressure monitoring;
- Run history and result analysis;
- An administrator panel for creating, editing, and copying scenarios;
- Redis-backed sessions and run state, with an automatic in-memory fallback when Redis is unavailable.

## Technology and project structure

- **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL, Jinja2, WebSocket.
- **Frontend:** Vue 3, TypeScript, Vite, Bootstrap.
- **State storage:** Redis (optional).
- **Tests:** pytest, Vitest, and Playwright.

Main files and directories:

```text
main.py                 FastAPI application, database models, routes, and WebSocket
sim_utils.py            Simulation calculations
run_limits.py           Pressure limit checks
src/                    Vue/TypeScript simulator interface
templates/              Jinja2 sign-in, scenario, and admin pages
tests/                  Python tests
e2e/                    Playwright tests
.env.example            OAuth and cookie environment variable template
start_servers.bat       Local Windows launcher for backend and frontend
JSON_PAYLOAD_SPEC.md    Frontend/backend payload specification
OAUTH_SETUP.md          Social authentication provider setup
```

## System requirements

Install the following software before setting up the project:

- Python 3.10 or newer;
- Node.js `20.19+` or `22.12+`, and npm;
- PostgreSQL;
- Redis (optional).

Run the commands below from the repository root.

## Installation

### 1. Prepare PostgreSQL

The connection string is currently defined directly in `main.py`:

```text
postgresql+psycopg2://postgres:1@localhost:5432/fastapi_auth
```

Create the `fastapi_auth` database and make sure the local `postgres` user has the password `1`:

```sql
CREATE DATABASE fastapi_auth;
```

To use a different user, password, host, or database name, change `DATABASE_URL` in `main.py`. On the first launch, SQLAlchemy creates the tables and adds the initial scenarios and users.

### 2. Install the backend

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install fastapi "uvicorn[standard]" sqlalchemy psycopg2-binary passlib bcrypt python-multipart jinja2 redis pytest
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install fastapi "uvicorn[standard]" sqlalchemy psycopg2-binary passlib bcrypt python-multipart jinja2 redis pytest
```

You may omit `redis` if external session storage is not required: the application will continue to work using in-process memory. PostgreSQL requires either `psycopg2-binary` or a compatible installation of `psycopg2`.

### 3. Install the frontend

```bash
npm install
```

## Development setup

Make sure PostgreSQL is running and the database is accessible. Then open two terminals.

Start the backend in the first terminal.

Linux/macOS:

```bash
source .venv/bin/activate
FRONTEND_DEV_MODE=true VITE_DEV_SERVER_URL=http://localhost:5173 \
  python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
$env:FRONTEND_DEV_MODE = "true"
$env:VITE_DEV_SERVER_URL = "http://localhost:5173"
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

Start Vite in the second terminal:

```bash
npm run dev
```

Open <http://127.0.0.1:8001>. Vite runs at <http://localhost:5173>, but FastAPI remains the main application entry point.

### Quick start on Windows

After manually installing the Python dependencies, run:

```bat
start_servers.bat
```

The script creates `.venv` if it does not exist and runs `npm install` when `node_modules` is missing. It does not install Python packages, so the backend installation step is still required.

## Default accounts

Two local accounts are created automatically on the first launch:

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `1234` |
| User | `user` | `1` |

These credentials are intended for local development only. Replace the initial user creation mechanism and passwords before deploying the application publicly.

## Environment variables

Available settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `FRONTEND_DEV_MODE` | disabled* | Forces the application to use the Vite development server |
| `VITE_DEV_SERVER_URL` | `http://localhost:5173` | Vite development server URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `SESSION_TTL_SECONDS` | `86400` | Session lifetime in seconds |
| `PUBLIC_BASE_URL` | inferred from request | Public origin used for OAuth callback URLs |
| `COOKIE_SECURE` | `false` | Sends the session cookie over HTTPS only |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | empty | Google OAuth credentials |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` | empty | LinkedIn OAuth credentials |
| `FACEBOOK_CLIENT_ID`, `FACEBOOK_CLIENT_SECRET` | empty | Facebook OAuth credentials |

\* The application also uses the development server automatically when the built Vite manifest is missing.

The `.env.example` file is a template, but the application **does not load `.env` automatically**. Pass values to the process through environment variables, a service manager, Docker/Compose, or load them into the current shell before starting the application. See [OAUTH_SETUP.md](OAUTH_SETUP.md) for provider-specific configuration and exact callback URLs.

## Redis

Redis is optional when running a single local process. If the Redis package or server is unavailable, sessions and active simulation state are stored in FastAPI process memory and are lost when the process restarts. For multiple backend processes and persistent sessions, run Redis and set `REDIS_URL`.

Example local URL:

```bash
export REDIS_URL=redis://localhost:6379/0
```

## Frontend build

Build the Vue application for a production-like setup:

```bash
npm run build
```

Vite creates the `dist/` directory and its manifest. The backend can then serve the built assets without a separate Vite process:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

For production, also enable HTTPS, set `PUBLIC_BASE_URL`, set `COOKIE_SECURE=true`, replace the test passwords, and do not expose PostgreSQL or Redis directly to the internet.

## Checks and tests

Python tests:

```bash
python -m pytest
```

Frontend unit tests:

```bash
npm run test:unit -- --run
```

Type checking and production build:

```bash
npm run build
```

End-to-end tests (install the Playwright browsers before the first run):

```bash
npx playwright install
npm run test:e2e
```

Linting:

```bash
npm run lint
```

The lint command runs in auto-fix mode and may modify source files.

## Troubleshooting

### The backend exits while importing `main.py`

PostgreSQL is usually not running, the `fastapi_auth` database has not been created, or the credentials do not match `DATABASE_URL`. The application connects to the database and creates its tables during import.

### The page opens without the interface or Vite assets are unavailable

In development mode, FastAPI must be running on port `8001` while Vite runs on port `5173`. To start the application without Vite, run `npm run build` first and make sure that `dist/.vite/manifest.json` exists.

### Redis unavailable / falling back to in-memory sessions

This warning does not prevent local development. Start Redis or keep using the fallback, bearing in mind that all in-memory state disappears when the backend restarts.

### Form error: `python-multipart` is required

Install the package in the active virtual environment:

```bash
python -m pip install python-multipart
```

### OAuth configuration error

Check the client ID and secret, `PUBLIC_BASE_URL`, and the exact callback URL registered with the provider. See [OAUTH_SETUP.md](OAUTH_SETUP.md).
