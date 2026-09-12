import csv
import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, create_engine, func, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from passlib.context import CryptContext
import secrets
from fastapi.middleware.cors import CORSMiddleware
import random
import sim_utils as s
import importlib
from pydantic import BaseModel
from run_limits import pressure_limit_breaches

try:
    import redis
except ImportError:
    redis = None

importlib.reload(s)

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "dist"
DIST_ASSETS_DIR = DIST_DIR / "assets"
VITE_MANIFEST_PATH = DIST_DIR / ".vite" / "manifest.json"
VITE_DEV_SERVER_URL = os.getenv("VITE_DEV_SERVER_URL", "http://localhost:5173")
FRONTEND_DEV_MODE = os.getenv("FRONTEND_DEV_MODE", "").lower() in {"1", "true", "yes"}
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
ANNULUS_M_DEBUG_CSV_TEMPLATE = "debug_annulus_m_run_{run_id}.csv"


app = FastAPI()
app.mount("/assets", StaticFiles(directory=DIST_ASSETS_DIR, check_dir=False), name="vite-assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # для разработки
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def write_annulus_m_debug_csv(run_id: int, case_id: int, M: list, total_strokes: float):
    path = BASE_DIR / ANNULUS_M_DEBUG_CSV_TEMPLATE.format(run_id=run_id)
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "case_id",
            "run_id",
            "total_strokes",
            "row_index",
            "m_light",
            "m_gas",
            "m_heavy",
            "v_gas",
        ])
        for index, row in enumerate(M):
            writer.writerow([
                case_id,
                run_id,
                total_strokes,
                index,
                row[0] if len(row) > 0 else "",
                row[1] if len(row) > 1 else "",
                row[2] if len(row) > 2 else "",
                row[3] if len(row) > 3 else "",
            ])


templates = Jinja2Templates(directory="templates")


def get_vite_context():
    manifest_exists = VITE_MANIFEST_PATH.exists()
    use_dev_server = FRONTEND_DEV_MODE or not manifest_exists

    if use_dev_server:
        return {
            "vite_dev_mode": True,
            "vite_dev_server_url": VITE_DEV_SERVER_URL.rstrip("/"),
            "vite_css_files": [],
            "vite_js_file": None,
        }

    manifest = json.loads(VITE_MANIFEST_PATH.read_text(encoding="utf-8"))
    entry = manifest.get("index.html") or manifest.get("src/main.ts")
    if not entry:
        raise RuntimeError("Vite manifest entry was not found for index.html or src/main.ts")

    return {
        "vite_dev_mode": False,
        "vite_dev_server_url": None,
        "vite_css_files": entry.get("css", []),
        "vite_js_file": entry["file"],
    }

# ---- DB ----
DATABASE_URL = "postgresql+psycopg2://postgres:1@localhost:5432/fastapi_auth"


engine = create_engine(DATABASE_URL)
print("Connecting to database...")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password_hash = Column(String)
    email = Column(String, index=True)
    auth_provider = Column(String)
    provider_subject = Column(String)


class Case(Base):
    __tablename__ = "case"
    id = Column(Integer, primary_key=True)
    name = Column(String)


class CaseUser(Base):
    __tablename__ = "case_user"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    case_id = Column(Integer, ForeignKey("case.id"), primary_key=True)


class CaseRun(Base):
    __tablename__ = "case_run"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("case.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())
    status = Column(String, nullable=False, default="A", server_default="A", index=True)
    state = Column(String, nullable=False, default="active", server_default="active", index=True)
    result_message = Column(String)
    result_data = Column(String)


class CaseDetails(Base):
    __tablename__ = "case_details"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("case.id"), unique=True)
    v_num = Column(Integer)
    well_l = Column(Float)
    v_delta = Column(Float)
    vpm = Column(Float)
    dppm = Column(Float)
    m3_per_stroke = Column(Float)
    gaz_v = Column(Float)
    ro = Column(Float)
    pu = Column(Float)
    ro_heavy = Column(Float)
    V_real = Column(Float)
    A = Column(Float)
    iters = Column(Integer)
    Pu_delta = Column(Float)
    choke_regulator_1 = Column(Float)
    choke_regulator_2 = Column(Float)
    pump_low = Column(Float)
    lowpumprate = Column(Float, nullable=False, default=20.0, server_default="20")
    dt = Column(Float)
    speed_1 = Column(Float)
    speed_2 = Column(Float)
    suspension_param = Column(Float)
    conductor_depth = Column(Float)
    conductor_frac_pressure = Column(Float)
    max_wellhead_pressure = Column(Float)
    max_bottomhole_pressure = Column(Float)
    max_pump_pressure = Column(Float)


Base.metadata.create_all(bind=engine)
with engine.begin() as connection:
    connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR"))
    connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR"))
    connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_subject VARCHAR"))
    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS users_oauth_identity_idx "
        "ON users (auth_provider, provider_subject)"
    ))
    connection.execute(text(
        "ALTER TABLE case_run "
        "ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'A'"
    ))
    connection.execute(text(
        "ALTER TABLE case_run "
        "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()"
    ))
    connection.execute(text(
        "ALTER TABLE case_run "
        "ADD COLUMN IF NOT EXISTS state VARCHAR DEFAULT 'active'"
    ))
    connection.execute(text("ALTER TABLE case_run ADD COLUMN IF NOT EXISTS result_message VARCHAR"))
    connection.execute(text("ALTER TABLE case_run ADD COLUMN IF NOT EXISTS result_data TEXT"))
    connection.execute(text("UPDATE case_run SET status = 'A' WHERE status IS NULL"))
    connection.execute(text("UPDATE case_run SET updated_at = created_at WHERE updated_at IS NULL"))
    connection.execute(text("UPDATE case_run SET state = 'active' WHERE state IS NULL"))
    connection.execute(text("ALTER TABLE case_run ALTER COLUMN status SET NOT NULL"))
    connection.execute(text("ALTER TABLE case_run ALTER COLUMN updated_at SET NOT NULL"))
    connection.execute(text("ALTER TABLE case_run ALTER COLUMN state SET NOT NULL"))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS lowpumprate DOUBLE PRECISION DEFAULT 20 NOT NULL"
    ))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS speed_1 DOUBLE PRECISION DEFAULT 0.5"
    ))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS speed_2 DOUBLE PRECISION DEFAULT 0.1"
    ))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS suspension_param DOUBLE PRECISION DEFAULT 0.3"
    ))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS conductor_depth DOUBLE PRECISION DEFAULT 400"
    ))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS conductor_frac_pressure DOUBLE PRECISION DEFAULT 0"
    ))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS max_wellhead_pressure DOUBLE PRECISION DEFAULT 30000000"
    ))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS max_bottomhole_pressure DOUBLE PRECISION DEFAULT 60000000"
    ))
    connection.execute(text(
        "ALTER TABLE case_details "
        "ADD COLUMN IF NOT EXISTS max_pump_pressure DOUBLE PRECISION DEFAULT 30000000"
    ))

# ---- Security ----
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
sessions = {}  # session_id -> username
run_states = {}  # run_id -> frontend init state
run_runtime_states = {}  # run_id -> runtime values from frontend
redis_client = None


def init_redis():
    global redis_client

    if redis is None:
        print("Redis client library is not installed. Falling back to in-memory sessions.")
        redis_client = None
        return

    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        redis_client = client
        print(f"Connected to Redis at {REDIS_URL}")
    except Exception as exc:
        redis_client = None
        print(f"Redis is unavailable ({exc}). Falling back to in-memory sessions.")


def get_session_key(session_id: str) -> str:
    return f"session:{session_id}"


def get_run_state_key(run_id: int) -> str:
    return f"run:{run_id}:frontend_init"


def get_run_runtime_key(run_id: int) -> str:
    return f"run:{run_id}:runtime"


def clear_run_states():
    run_states.clear()
    run_runtime_states.clear()
    if redis_client is not None:
        for key in redis_client.scan_iter("run:*"):
            redis_client.delete(key)


def clear_run_state(run_id: int):
    run_states.pop(run_id, None)
    run_runtime_states.pop(run_id, None)
    if redis_client is not None:
        redis_client.delete(get_run_state_key(run_id), get_run_runtime_key(run_id))


def set_session_user(session_id: str, username: str):
    sessions[session_id] = username
    if redis_client is not None:
        redis_client.setex(get_session_key(session_id), SESSION_TTL_SECONDS, username)


def get_session_user(session_id: Optional[str]) -> Optional[str]:
    if not session_id:
        return None

    if redis_client is not None:
        username = redis_client.get(get_session_key(session_id))
        if username:
            return username

    return sessions.get(session_id)


def delete_session_user(session_id: Optional[str]):
    if not session_id:
        return

    sessions.pop(session_id, None)
    if redis_client is not None:
        redis_client.delete(get_session_key(session_id))


def set_run_state(run_id: int, frontend_init_data: dict):
    run_states[run_id] = frontend_init_data
    if redis_client is not None:
        redis_client.set(get_run_state_key(run_id), json.dumps(frontend_init_data))


def get_run_state(run_id: int, case_id: int) -> dict:
    if redis_client is not None:
        payload = redis_client.get(get_run_state_key(run_id))
        if payload:
            return json.loads(payload)

    frontend_init_data = run_states.get(run_id)
    if frontend_init_data is not None:
        return frontend_init_data

    case_data, _ = get_case_init_data(case_id)
    v_num = case_data["v_num"]
    well_l = case_data["well_l"]
    vpm = case_data["vpm"]
    dppm = case_data["dppm"]
    gaz_v = case_data["gaz_v"]
    ro = case_data["ro"]
    pu = case_data["pu"]
    pump_low = case_data["pump_low"]

    M_init, ppl, _ = s.get_init(v_num, well_l, vpm, gaz_v, ro, pu, pump_low)
    DP_init, sidpp_pump_off = s.get_init_dp(v_num, well_l, dppm, ro, ppl)
    write_annulus_m_debug_csv(run_id, case_id, M_init, 0.0)

    frontend_init_data = {
        "choke_speed": float(0.5),
        "choke_regulator_1": float(case_data["choke_regulator_1"]),
        "choke_regulator_2": float(case_data["choke_regulator_2"]),
        "casing_p": int(pu),
        "drillpipe_p": int(sidpp_pump_off),
        "Ppl": int(ppl),
        "pzab": int(ppl),
        "heavy_mud_pos": 0.0,
        "pump_speed_init": 0,
        "mud_switch": 0,
        "choke_position_init": 0,
        "total_strokes": 0,
        "annulus_content": M_init,
        "drillpipe_content": DP_init,
        "pzab_history": [float(ppl)],
    }
    set_run_state(run_id, frontend_init_data)
    set_run_runtime_state(run_id, {
        "pump_speed": 0.0,
        "choke_position": 0.0,
        "mud_switch": 0,
    })
    return frontend_init_data


def set_run_runtime_state(run_id: int, runtime_state: dict):
    run_runtime_states[run_id] = runtime_state
    if redis_client is not None:
        redis_client.set(get_run_runtime_key(run_id), json.dumps(runtime_state))


def get_run_runtime_state(run_id: int) -> Optional[dict]:
    if redis_client is not None:
        payload = redis_client.get(get_run_runtime_key(run_id))
        if payload:
            return json.loads(payload)

    return run_runtime_states.get(run_id)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hash: str):
    return pwd_context.verify(password, hash)


OAUTH_PROVIDERS = {
    "google": {
        "label": "Google",
        "client_id_env": "GOOGLE_CLIENT_ID",
        "client_secret_env": "GOOGLE_CLIENT_SECRET",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    },
    "linkedin": {
        "label": "LinkedIn",
        "client_id_env": "LINKEDIN_CLIENT_ID",
        "client_secret_env": "LINKEDIN_CLIENT_SECRET",
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "userinfo_url": "https://api.linkedin.com/v2/userinfo",
        "scope": "openid profile email",
    },
    "facebook": {
        "label": "Facebook",
        "client_id_env": "FACEBOOK_CLIENT_ID",
        "client_secret_env": "FACEBOOK_CLIENT_SECRET",
        "authorize_url": "https://www.facebook.com/v25.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v25.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/v25.0/me?fields=id,name,email",
        "scope": "email,public_profile",
    },
}


def oauth_redirect_uri(request: Request, provider: str) -> str:
    public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if public_base_url:
        return f"{public_base_url}/auth/{provider}/callback"
    return str(request.url_for("oauth_callback", provider=provider))


def oauth_credentials(provider: str) -> tuple[str, str]:
    config = OAUTH_PROVIDERS[provider]
    return (
        os.getenv(config["client_id_env"], "").strip(),
        os.getenv(config["client_secret_env"], "").strip(),
    )


def oauth_http_json(url: str, data: Optional[dict] = None, access_token: Optional[str] = None) -> dict:
    encoded_data = urllib.parse.urlencode(data).encode() if data is not None else None
    headers = {"Accept": "application/json", "User-Agent": "WellControlSimulator/1.0"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = urllib.request.Request(url, data=encoded_data, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def unique_social_username(db: Session, provider: str, subject: str, email: Optional[str]) -> str:
    base = (email or f"{provider}_{subject}").strip().lower()
    if not db.query(User).filter(User.username == base).first():
        return base
    suffix = 1
    while db.query(User).filter(User.username == f"{base}_{suffix}").first():
        suffix += 1
    return f"{base}_{suffix}"


def finish_login(username: str) -> RedirectResponse:
    session_id = secrets.token_hex(16)
    set_session_user(session_id, username)
    destination = "/admin/cases" if username == "admin" else "/cases"
    response = RedirectResponse(destination, status_code=302)
    public_base_url = os.getenv("PUBLIC_BASE_URL", "").lower()
    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        secure=(
            public_base_url.startswith("https://")
            or os.getenv("COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
        ),
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return response


class NumberUpdatePayload(BaseModel):
    choke_position: float = 0
    pump_speed: float = 0
    mud_switch: int = 0


RUN_STATES = {"active", "paused", "failed", "fast_forward", "completed"}
FAST_FORWARD_STEPS = 5


class RunStateUpdatePayload(BaseModel):
    state: str


def mark_run_failed(run_id: int, breaches: list[dict], result_data: dict) -> None:
    db = SessionLocal()
    try:
        case_run = db.query(CaseRun).filter(
            CaseRun.id == run_id,
            CaseRun.status != "D",
        ).first()
        if case_run and case_run.state != "completed":
            case_run.state = "failed"
            case_run.result_message = "; ".join(breach["message"] for breach in breaches)
            case_run.result_data = json.dumps(result_data)
            case_run.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
    finally:
        db.close()


CASE_FIELD_DEFINITIONS = [
    {"name": "v_num", "label": "Calculation cells", "type": "int", "step": "1", "group": "Well geometry"},
    {"name": "well_l", "label": "Well length", "type": "float", "step": "any", "group": "Well geometry"},
    {"name": "v_delta", "label": "Cell length", "type": "float", "step": "any", "group": "Well geometry"},
    {"name": "vpm", "label": "Annulus volume per meter", "type": "float", "step": "any", "group": "Well geometry"},
    {"name": "dppm", "label": "Drillpipe volume per meter", "type": "float", "step": "any", "group": "Well geometry"},
    {"name": "A", "label": "Annulus area", "type": "float", "step": "any", "group": "Well geometry"},
    {"name": "conductor_depth", "label": "Conductor depth", "type": "float", "step": "any", "group": "Well geometry"},
    {"name": "conductor_frac_pressure", "label": "P_cs limit (Pa)", "type": "float", "step": "any", "group": "Pressure limits"},
    {"name": "max_wellhead_pressure", "label": "Maximum wellhead pressure", "type": "float", "step": "any", "group": "Pressure limits"},
    {"name": "max_bottomhole_pressure", "label": "Maximum bottomhole pressure", "type": "float", "step": "any", "group": "Pressure limits"},
    {"name": "max_pump_pressure", "label": "Maximum pump pressure", "type": "float", "step": "any", "group": "Pressure limits"},
    {"name": "ro", "label": "Mud density", "type": "float", "step": "any", "group": "Fluids and influx"},
    {"name": "ro_heavy", "label": "Heavy mud density", "type": "float", "step": "any", "group": "Fluids and influx"},
    {"name": "gaz_v", "label": "Gas influx volume", "type": "float", "step": "any", "group": "Fluids and influx"},
    {"name": "pu", "label": "Initial surface pressure", "type": "float", "step": "any", "group": "Fluids and influx"},
    {"name": "V_real", "label": "Well volume", "type": "float", "step": "any", "group": "Fluids and influx"},
    {"name": "m3_per_stroke", "label": "Volume per stroke", "type": "float", "step": "any", "group": "Pump and choke"},
    {"name": "pump_low", "label": "Low-rate pump pressure", "type": "float", "step": "any", "group": "Pump and choke"},
    {"name": "lowpumprate", "label": "Low pump rate", "type": "float", "step": "any", "group": "Pump and choke"},
    {"name": "choke_regulator_1", "label": "Choke regulator 1", "type": "float", "step": "any", "group": "Pump and choke"},
    {"name": "choke_regulator_2", "label": "Choke regulator 2", "type": "float", "step": "any", "group": "Pump and choke"},
    {"name": "speed_1", "label": "Gas migration speed 1", "type": "float", "step": "any", "group": "Simulation"},
    {"name": "speed_2", "label": "Gas migration speed 2", "type": "float", "step": "any", "group": "Simulation"},
    {"name": "suspension_param", "label": "Suspension threshold", "type": "float", "step": "any", "group": "Simulation"},
    {"name": "iters", "label": "Solver iterations", "type": "int", "step": "1", "group": "Simulation"},
    {"name": "Pu_delta", "label": "Pressure iteration step", "type": "float", "step": "any", "group": "Simulation"},
    {"name": "dt", "label": "Simulation time step", "type": "float", "step": "any", "group": "Simulation"},
]


def case_form_values(details_data: dict) -> dict:
    return {
        field["name"]: details_data.get(field["name"], "")
        for field in CASE_FIELD_DEFINITIONS
    }


def parse_case_form(form) -> tuple[str, dict, list[str]]:
    name = str(form.get("name", "")).strip()
    errors = []
    values = {}
    if not name:
        errors.append("Case name is required.")

    for field in CASE_FIELD_DEFINITIONS:
        field_name = field["name"]
        raw_value = str(form.get(field_name, "")).strip()
        if not raw_value:
            errors.append(f"{field['label']} is required.")
            continue
        try:
            values[field_name] = int(raw_value) if field["type"] == "int" else float(raw_value)
        except ValueError:
            errors.append(f"{field['label']} must be a number.")

    return name, values, errors

# ---- Create test user (один раз) ----
@app.on_event("startup")
def create_user():
    init_redis()
    db = SessionLocal()
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin_user = User(username="admin", password_hash=hash_password("1234"))
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

    regular_user = db.query(User).filter(User.username == "user").first()
    if not regular_user:
        regular_user = User(username="user", password_hash=hash_password("1"))
        db.add(regular_user)
        db.commit()
        db.refresh(regular_user)

    for user in (admin_user, regular_user):
        seed_case(db, user.id, 1, "Case 1", get_default_case_init_data())
        seed_case(db, user.id, 2, "deep", get_deep_case_init_data())
    db.close()

# ---- Routes ----
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    oauth_errors = {
        "cancelled": "Authentication was cancelled.",
        "config": "This sign-in method has not been configured yet.",
        "invalid_state": "The authentication session has expired. Please try again.",
        "provider": "The provider could not verify your account. Please try again.",
        "email": "The provider did not return the profile data required for registration.",
    }
    error_code = request.query_params.get("oauth_error")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"message": oauth_errors.get(error_code)},
    )

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"message": "Invalid username or password."},
        )

    return finish_login(username)


@app.get("/auth/{provider}")
async def oauth_start(request: Request, provider: str):
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown OAuth provider")

    client_id, client_secret = oauth_credentials(provider)
    if not client_id or not client_secret:
        return RedirectResponse("/?oauth_error=config#access", status_code=302)

    state = secrets.token_urlsafe(32)
    config = OAUTH_PROVIDERS[provider]
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": oauth_redirect_uri(request, provider),
        "scope": config["scope"],
        "state": state,
    }
    if provider == "google":
        params["prompt"] = "select_account"

    response = RedirectResponse(
        f"{config['authorize_url']}?{urllib.parse.urlencode(params)}",
        status_code=302,
    )
    response.set_cookie(
        "oauth_state",
        f"{provider}:{state}",
        max_age=600,
        httponly=True,
        secure=request.url.scheme == "https" or os.getenv("COOKIE_SECURE", "").lower() in {"1", "true", "yes"},
        samesite="lax",
        path="/auth",
    )
    return response


@app.get("/auth/{provider}/callback", name="oauth_callback")
async def oauth_callback(request: Request, provider: str, db: Session = Depends(get_db)):
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown OAuth provider")

    if request.query_params.get("error"):
        response = RedirectResponse("/?oauth_error=cancelled#access", status_code=302)
        response.delete_cookie("oauth_state", path="/auth")
        return response

    state = request.query_params.get("state", "")
    expected_state = request.cookies.get("oauth_state", "")
    if not state or not secrets.compare_digest(expected_state, f"{provider}:{state}"):
        response = RedirectResponse("/?oauth_error=invalid_state#access", status_code=302)
        response.delete_cookie("oauth_state", path="/auth")
        return response

    code = request.query_params.get("code", "")
    client_id, client_secret = oauth_credentials(provider)
    if not code or not client_id or not client_secret:
        response = RedirectResponse("/?oauth_error=config#access", status_code=302)
        response.delete_cookie("oauth_state", path="/auth")
        return response

    config = OAUTH_PROVIDERS[provider]
    try:
        token_data = await asyncio.to_thread(
            oauth_http_json,
            config["token_url"],
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": oauth_redirect_uri(request, provider),
            },
        )
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("OAuth provider did not return an access token")
        profile = await asyncio.to_thread(
            oauth_http_json,
            config["userinfo_url"],
            None,
            access_token,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        response = RedirectResponse("/?oauth_error=provider#access", status_code=302)
        response.delete_cookie("oauth_state", path="/auth")
        return response

    subject = str(profile.get("sub") or profile.get("id") or "").strip()
    email = str(profile.get("email") or "").strip().lower() or None
    if not subject:
        response = RedirectResponse("/?oauth_error=email#access", status_code=302)
        response.delete_cookie("oauth_state", path="/auth")
        return response

    user = db.query(User).filter(
        User.auth_provider == provider,
        User.provider_subject == subject,
    ).first()
    if not user:
        user = User(
            username=unique_social_username(db, provider, subject, email),
            password_hash=None,
            email=email,
            auth_provider=provider,
            provider_subject=subject,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        seed_case(db, user.id, 1, "Case 1", get_default_case_init_data())
        seed_case(db, user.id, 2, "deep", get_deep_case_init_data())

    response = finish_login(user.username)
    response.delete_cookie("oauth_state", path="/auth")
    return response

def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    return get_session_user(session_id)


def get_authorized_run(db: Session, run_id: int, username: str) -> Optional[CaseRun]:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    query = db.query(CaseRun).filter(
        CaseRun.id == run_id,
        CaseRun.status != "D",
    )
    if username != "admin":
        query = query.filter(CaseRun.user_id == user.id)
    return query.first()


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={"user": user},
    )

@app.get("/cases", response_class=HTMLResponse)
async def cases_page(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return RedirectResponse("/", status_code=302)

    cases = (
        db.query(Case.id, Case.name)
        .join(CaseUser, CaseUser.case_id == Case.id)
        .filter(CaseUser.user_id == user.id)
        .order_by(Case.id)
        .all()
    )
    runs = (
        db.query(
            CaseRun.id,
            CaseRun.case_id,
            CaseRun.created_at,
            CaseRun.updated_at,
            CaseRun.status,
            CaseRun.state,
            CaseRun.result_message,
            Case.name.label("case_name"),
        )
        .join(Case, Case.id == CaseRun.case_id)
        .filter(
            CaseRun.user_id == user.id,
            CaseRun.status != "D",
        )
        .order_by(CaseRun.created_at.desc(), CaseRun.id.desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="cases.html",
        context={
            "user": username,
            "cases": cases,
            "runs": runs,
            "is_admin": username == "admin",
        },
    )


@app.post("/cases/{case_id}/runs")
async def create_case_run(request: Request, case_id: int, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)

    user = db.query(User).filter(User.username == username).first()
    case = db.query(Case).filter(Case.id == case_id).first()
    if not user or not case:
        return RedirectResponse("/cases", status_code=302)

    if username != "admin":
        assignment = db.query(CaseUser).filter(
            CaseUser.user_id == user.id,
            CaseUser.case_id == case_id,
        ).first()
        if not assignment:
            return RedirectResponse("/cases", status_code=302)

    case_run = CaseRun(case_id=case_id, user_id=user.id, state="active")
    db.add(case_run)
    db.commit()
    db.refresh(case_run)
    return RedirectResponse(f"/run/{case_run.id}", status_code=303)


@app.post("/runs/{run_id}/delete")
async def delete_case_run(request: Request, run_id: int, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return RedirectResponse("/", status_code=302)

    case_run = db.query(CaseRun).filter(
        CaseRun.id == run_id,
        CaseRun.user_id == user.id,
        CaseRun.status != "D",
    ).first()
    if not case_run:
        return RedirectResponse("/cases?missing_run=1", status_code=303)

    case_run.status = "D"
    case_run.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    clear_run_state(run_id)
    return RedirectResponse("/cases?deleted=1", status_code=303)


@app.get("/admin/cases", response_class=HTMLResponse)
async def admin_cases_page(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)
    if username != "admin":
        return RedirectResponse("/cases", status_code=302)

    cases = (
        db.query(Case.id, Case.name)
        .order_by(Case.id)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="admin_cases.html",
        context={"user": username, "cases": cases},
    )


@app.get("/admin/cases/new", response_class=HTMLResponse)
async def admin_case_create_page(request: Request):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)
    if username != "admin":
        return RedirectResponse("/cases", status_code=302)

    values = case_form_values(get_default_case_init_data())
    values["name"] = ""
    return templates.TemplateResponse(
        request=request,
        name="admin_case_form.html",
        context={
            "mode": "create",
            "case": None,
            "values": values,
            "field_definitions": CASE_FIELD_DEFINITIONS,
            "errors": [],
        },
    )


@app.post("/admin/cases/new", response_class=HTMLResponse)
async def admin_case_create(request: Request, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)
    if username != "admin":
        return RedirectResponse("/cases", status_code=302)

    form = await request.form()
    name, details_data, errors = parse_case_form(form)
    if errors:
        values = {field["name"]: form.get(field["name"], "") for field in CASE_FIELD_DEFINITIONS}
        values["name"] = name
        return templates.TemplateResponse(
            request=request,
            name="admin_case_form.html",
            context={
                "mode": "create",
                "case": None,
                "values": values,
                "field_definitions": CASE_FIELD_DEFINITIONS,
                "errors": errors,
            },
            status_code=422,
        )

    admin_user = db.query(User).filter(User.username == username).first()
    next_case_id = (db.query(func.max(Case.id)).scalar() or 0) + 1
    new_case = Case(id=next_case_id, name=name)
    db.add(new_case)
    db.add(CaseDetails(case_id=next_case_id, **details_data))
    db.add(CaseUser(user_id=admin_user.id, case_id=next_case_id))
    db.commit()
    return RedirectResponse(f"/admin/cases/{next_case_id}/edit?saved=created", status_code=303)


@app.get("/admin/cases/{case_id}/edit", response_class=HTMLResponse)
async def admin_case_edit_page(request: Request, case_id: int, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)
    if username != "admin":
        return RedirectResponse("/cases", status_code=302)

    case = db.query(Case).filter(Case.id == case_id).first()
    details = db.query(CaseDetails).filter(CaseDetails.case_id == case_id).first()
    if not case or not details:
        return RedirectResponse("/admin/cases?missing=1", status_code=302)

    values = case_form_values({field["name"]: getattr(details, field["name"]) for field in CASE_FIELD_DEFINITIONS})
    values["name"] = case.name
    return templates.TemplateResponse(
        request=request,
        name="admin_case_form.html",
        context={
            "mode": "edit",
            "case": case,
            "values": values,
            "field_definitions": CASE_FIELD_DEFINITIONS,
            "errors": [],
            "saved": request.query_params.get("saved"),
        },
    )


@app.post("/admin/cases/{case_id}/edit", response_class=HTMLResponse)
async def admin_case_edit(request: Request, case_id: int, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)
    if username != "admin":
        return RedirectResponse("/cases", status_code=302)

    case = db.query(Case).filter(Case.id == case_id).first()
    details = db.query(CaseDetails).filter(CaseDetails.case_id == case_id).first()
    if not case or not details:
        return RedirectResponse("/admin/cases?missing=1", status_code=302)

    form = await request.form()
    name, details_data, errors = parse_case_form(form)
    if errors:
        values = {field["name"]: form.get(field["name"], "") for field in CASE_FIELD_DEFINITIONS}
        values["name"] = name
        return templates.TemplateResponse(
            request=request,
            name="admin_case_form.html",
            context={
                "mode": "edit",
                "case": case,
                "values": values,
                "field_definitions": CASE_FIELD_DEFINITIONS,
                "errors": errors,
            },
            status_code=422,
        )

    case.name = name
    for field_name, value in details_data.items():
        setattr(details, field_name, value)
    db.commit()
    run_ids = db.query(CaseRun.id).filter(CaseRun.case_id == case_id).all()
    for (run_id,) in run_ids:
        clear_run_state(run_id)
    return RedirectResponse(f"/admin/cases/{case_id}/edit?saved=updated", status_code=303)


@app.post("/admin/cases/{case_id}/copy", response_class=HTMLResponse)
async def admin_case_copy(
    request: Request,
    case_id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)
    if username != "admin":
        return RedirectResponse("/cases", status_code=302)

    source_case = db.query(Case).filter(Case.id == case_id).first()
    source_details = db.query(CaseDetails).filter(CaseDetails.case_id == case_id).first()
    admin_user = db.query(User).filter(User.username == username).first()
    copy_name = name.strip()
    if not source_case or not source_details:
        return RedirectResponse("/admin/cases?missing=1", status_code=303)
    if not admin_user or not copy_name:
        return RedirectResponse(f"/admin/cases?copy_error={case_id}", status_code=303)

    next_case_id = (db.query(func.max(Case.id)).scalar() or 0) + 1
    details_data = {
        field["name"]: getattr(source_details, field["name"])
        for field in CASE_FIELD_DEFINITIONS
    }
    db.add(Case(id=next_case_id, name=copy_name))
    db.add(CaseDetails(case_id=next_case_id, **details_data))
    db.add(CaseUser(user_id=admin_user.id, case_id=next_case_id))
    db.commit()
    return RedirectResponse(f"/admin/cases/{next_case_id}/edit?saved=copied", status_code=303)


@app.get("/run/{run_id}", response_class=HTMLResponse)
async def run_case(request: Request, run_id: int, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    username = get_session_user(session_id)
    if not session_id or not username:
        return RedirectResponse("/", status_code=302)

    case_run = get_authorized_run(db, run_id, username)
    if not case_run:
        return RedirectResponse("/cases", status_code=302)

    case_id = case_run.case_id
    case_data, _ = get_case_init_data(case_id)
    ro = case_data['ro']
    ro_heavy = case_data['ro_heavy']
    frontend_init_data = get_run_state(run_id, case_id)

    runtime_state = get_run_runtime_state(run_id) or {}
    page_frontend_init_data = dict(frontend_init_data)
    page_frontend_init_data["pump_speed_init"] = float(
        runtime_state.get("pump_speed", page_frontend_init_data.get("pump_speed_init", 0))
    )
    page_frontend_init_data["choke_position_init"] = float(
        runtime_state.get("choke_position", page_frontend_init_data.get("choke_position_init", 0))
    )
    page_frontend_init_data["mud_switch"] = 1 if runtime_state.get(
        "mud_switch",
        page_frontend_init_data.get("mud_switch", 0),
    ) == 1 else 0
    page_frontend_init_data["annulus_content"] = s.svg_preconstruct(
        frontend_init_data["annulus_content"],
        ro,
        ro_heavy,
    )
    page_frontend_init_data["drillpipe_content"] = s.svg_preconstruct(
        frontend_init_data["drillpipe_content"],
        ro,
        ro_heavy,
    )

    return templates.TemplateResponse(
        request=request,
        name="run.html",
        context={
            "session_id": session_id,
            "user": username,
            "run_id": run_id,
            "run_state": case_run.state,
            "result_message": case_run.result_message,
            "case_id": case_id,
            "case_data": case_data,
            "m_init": frontend_init_data["annulus_content"],
            "frontend_init_data": page_frontend_init_data,
            **get_vite_context(),
        },
    )


@app.get("/runs/{run_id}/analysis", response_class=HTMLResponse)
async def run_analysis(request: Request, run_id: int, db: Session = Depends(get_db)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/", status_code=302)

    case_run = get_authorized_run(db, run_id, username)
    if not case_run:
        return RedirectResponse("/cases?missing_run=1", status_code=302)
    if case_run.state not in {"failed", "completed"}:
        return RedirectResponse(f"/run/{run_id}", status_code=302)

    case = db.query(Case).filter(Case.id == case_run.case_id).first()
    case_data, _ = get_case_init_data(case_run.case_id)
    stored_result = json.loads(case_run.result_data) if case_run.result_data else {}
    frontend_state = get_run_state(run_id, case_run.case_id)
    pressures = stored_result.get("pressures", {
        "conductor": frontend_state.get("conductor_pressure"),
        "wellhead": frontend_state.get("casing_p"),
        "pump": frontend_state.get("drillpipe_p"),
        "bottomhole": frontend_state.get("pzab"),
    })
    limits = stored_result.get("limits", {
        "conductor": case_data.get("conductor_frac_pressure"),
        "wellhead": case_data.get("max_wellhead_pressure"),
        "pump": case_data.get("max_pump_pressure"),
    })
    return templates.TemplateResponse(
        request=request,
        name="run_analysis.html",
        context={
            "user": username,
            "run": case_run,
            "case": case,
            "message": case_run.result_message,
            "pressures": pressures,
            "limits": limits,
            "breaches": stored_result.get("breaches", []),
            "total_strokes": stored_result.get("total_strokes", frontend_state.get("total_strokes", 0)),
        },
    )

@app.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    delete_session_user(session_id)
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("session_id")
    return response



def build_run_response(frontend_init_data: dict, case_data: dict, run_state: str) -> dict:
    response_frontend_init_data = dict(frontend_init_data)
    response_frontend_init_data["annulus_content"] = s.svg_preconstruct(
        frontend_init_data["annulus_content"],
        case_data["ro"],
        case_data["ro_heavy"],
    )
    response_frontend_init_data["drillpipe_content"] = s.svg_preconstruct(
        frontend_init_data["drillpipe_content"],
        case_data["ro"],
        case_data["ro_heavy"],
    )
    response_frontend_init_data.pop("pump_speed_init", None)
    response_frontend_init_data.pop("choke_position_init", None)
    response = {
        "frontend_init_data": response_frontend_init_data,
        "run_state": run_state,
    }
    if run_state in {"failed", "completed"}:
        response["analysis_url"] = None
    return response


def advance_run_step(run_id: int, case_id: int, payload: NumberUpdatePayload, run_state: str):
    case_data, field_names = get_case_init_data(case_id)
    frontend_init_data = get_run_state(run_id, case_id)

    runtime_state = {
        "pump_speed": float(payload.pump_speed),
        "choke_position": float(payload.choke_position),
        "mud_switch": 1 if payload.mud_switch == 1 else 0,
    }
    set_run_runtime_state(run_id, runtime_state)

    params = SimpleNamespace()
    for field_name in field_names:
        setattr(params, field_name, case_data[field_name])

    for attribute_name, state_key in {
        "M_init": "annulus_content",
        "DP_init": "drillpipe_content",
    }.items():
        setattr(params, attribute_name, frontend_init_data[state_key])

    strokes_delta = runtime_state["pump_speed"] * params.dt / 60
    q = strokes_delta * params.m3_per_stroke  # TODO: refine pump flow correction.
    q_heavy = q * runtime_state['mud_switch']
    q_light = q * (1 - runtime_state['mud_switch'])
    frontend_init_data['total_strokes'] += strokes_delta
    params.DP_init, v_light, v_heavy = s.dp_state(
        params.DP_init,
        params.dt,
        q_light,
        q_heavy,
        params.ro,
        params.ro_heavy,
    )

    pos = runtime_state["choke_position"] / 100
    k = 1
    Pu_updated, Pzab, dP, P_cs = s.s_solver(
        params.A,
        params.Pu_delta,
        params.iters,
        params.M_init,
        params.ro,
        params.ro_heavy,
        frontend_init_data["casing_p"],
        params.V_real,
        params.conductor_depth * params.vpm
    )
    drillpipe_p = s.dp_surf_press(
        params.DP_init,
        params.pump_low,
        runtime_state["pump_speed"],
        Pzab,
        params.dppm,
        params.lowpumprate,
    )
    params.M_init = s.stolb_up_updater(
        params.M_init,
        Pu_updated,
        pos,
        params.dt,
        params.ro,
        params.ro_heavy,
    )
    params.M_init = s.stolb_down_updater(
        params.M_init,
        params.ro_heavy,
        params.ro,
        v_heavy * params.ro_heavy / params.dt,
        v_light * params.ro / params.dt,
        Pzab,
        Pu_updated,
        frontend_init_data["Ppl"],
        pos,
        k,
        params.dt,
    )
    s.m_reconstruct(params.M_init, params.ro, params.ro_heavy, Pu_updated, params.A,)
    s.gas_migrate(
        params.M_init,
        params.ro,
        params.ro_heavy,
        params.v_delta,
        params.vpm,
        params.dt,
        params.speed_1,
        params.speed_2,
        params.suspension_param,
    )
    #write_annulus_m_debug_csv(run_id, case_id, params.M_init, frontend_init_data["total_strokes"])
    frontend_init_data["casing_p"] = Pu_updated
    frontend_init_data["drillpipe_p"] = drillpipe_p
    frontend_init_data["pzab"] = Pzab
    frontend_init_data["annulus_content"] = params.M_init
    frontend_init_data["drillpipe_content"] = params.DP_init
    frontend_init_data["mud_switch"] = runtime_state['mud_switch']
    frontend_init_data["conductor_pressure"] = P_cs
    pzab_history = frontend_init_data.setdefault("pzab_history", [])
    pzab_history.append(float(Pzab))
    set_run_state(run_id, frontend_init_data)

    breaches = pressure_limit_breaches(P_cs, Pu_updated, drillpipe_p, case_data)
    next_state = "failed" if breaches else run_state
    response = build_run_response(frontend_init_data, case_data, next_state)
    if breaches:
        result_data = {
            "pressures": {
                "conductor": float(P_cs),
                "wellhead": float(Pu_updated),
                "pump": float(drillpipe_p),
                "bottomhole": float(Pzab),
            },
            "limits": {
                "conductor": float(case_data["conductor_frac_pressure"]),
                "wellhead": float(case_data["max_wellhead_pressure"]),
                "pump": float(case_data["max_pump_pressure"]),
            },
            "breaches": breaches,
            "total_strokes": float(frontend_init_data["total_strokes"]),
        }
        mark_run_failed(run_id, breaches, result_data)
        response["failure_message"] = "; ".join(breach["message"] for breach in breaches)
        response["limit_breaches"] = breaches
        response["analysis_url"] = f"/runs/{run_id}/analysis"
    return response


def advance_run(run_id: int, case_id: int, payload: NumberUpdatePayload, run_state: str):
    case_data, _ = get_case_init_data(case_id)
    if run_state in {"paused", "failed", "completed"}:
        return build_run_response(get_run_state(run_id, case_id), case_data, run_state)

    response = None
    step_count = FAST_FORWARD_STEPS if run_state == "fast_forward" else 1
    for _ in range(step_count):
        response = advance_run_step(run_id, case_id, payload, run_state)
        if response["run_state"] == "failed":
            break
    return response


@app.post("/runs/{run_id}/state")
def update_run_state(
    request: Request,
    run_id: int,
    payload: RunStateUpdatePayload,
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    case_run = get_authorized_run(db, run_id, username)
    if not case_run:
        raise HTTPException(status_code=404, detail="Run not found")
    if payload.state not in RUN_STATES:
        raise HTTPException(status_code=422, detail="Invalid run state")

    if payload.state == "completed":
        frontend_state = get_run_state(run_id, case_run.case_id)
        case_data, _ = get_case_init_data(case_run.case_id)
        breaches = pressure_limit_breaches(
            frontend_state.get("conductor_pressure"),
            frontend_state.get("casing_p"),
            frontend_state.get("drillpipe_p"),
            case_data,
        )
        case_run.state = "failed" if breaches else "completed"
        result_data = {
            "pressures": {
                "conductor": frontend_state.get("conductor_pressure"),
                "wellhead": frontend_state.get("casing_p"),
                "pump": frontend_state.get("drillpipe_p"),
                "bottomhole": frontend_state.get("pzab"),
            },
            "limits": {
                "conductor": case_data.get("conductor_frac_pressure"),
                "wellhead": case_data.get("max_wellhead_pressure"),
                "pump": case_data.get("max_pump_pressure"),
            },
            "breaches": breaches,
            "total_strokes": float(frontend_state.get("total_strokes", 0)),
        }
        case_run.result_message = (
            "; ".join(breach["message"] for breach in breaches)
            if breaches
            else "The case was finished by the operator."
        )
        case_run.result_data = json.dumps(result_data)
        response = {
            "run_state": case_run.state,
            "result_message": case_run.result_message,
            "analysis_url": f"/runs/{run_id}/analysis",
        }
        if breaches:
            response["failure_message"] = case_run.result_message
            response["limit_breaches"] = breaches
    else:
        case_run.state = payload.state
        response = {"run_state": case_run.state}
    case_run.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return response


@app.post("/number/{run_id}")
def get_number(
    request: Request,
    run_id: int,
    payload: NumberUpdatePayload,
    db: Session = Depends(get_db),
):
    username = get_current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized")
    case_run = get_authorized_run(db, run_id, username)
    if not case_run:
        raise HTTPException(status_code=404, detail="Run not found")
    return advance_run(run_id, case_run.case_id, payload, case_run.state)


@app.websocket("/ws/number/{run_id}")
async def number_socket(websocket: WebSocket, run_id: int):
    username = get_session_user(websocket.cookies.get("session_id"))
    db = SessionLocal()
    try:
        case_run = get_authorized_run(db, run_id, username) if username else None
        case_id = case_run.case_id if case_run else None
    finally:
        db.close()

    if case_id is None:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    try:
        while True:
            payload_data = await websocket.receive_json()
            payload = NumberUpdatePayload(**payload_data)
            db = SessionLocal()
            try:
                current_run = db.query(CaseRun).filter(CaseRun.id == run_id).first()
                run_state = current_run.state if current_run else "failed"
            finally:
                db.close()
            await websocket.send_json(advance_run(run_id, case_id, payload, run_state))
    except WebSocketDisconnect:
        return


def seed_case(db: Session, user_id: int, case_id: int, name: str, details_data: dict):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        case = Case(id=case_id, name=name)
        db.add(case)

    case_details = db.query(CaseDetails).filter(CaseDetails.case_id == case_id).first()
    if not case_details:
        db.add(CaseDetails(case_id=case_id, **details_data))

    case_user = db.query(CaseUser).filter(
        CaseUser.user_id == user_id,
        CaseUser.case_id == case_id,
    ).first()
    if not case_user:
        db.add(CaseUser(user_id=user_id, case_id=case_id))

    db.commit()


def get_default_case_init_data():
    return {
    'v_num' :50,
    'well_l' : 500,
    'v_delta' : 500 / 50,
    'vpm' :  0.024,
    'dppm' : 0.008,
    'm3_per_stroke' : 0.008,
    'gaz_v' : 1,
    'ro' : 1200,
    'pu' : 10*10**5,
    'ro_heavy' : 1400,
    'V_real' : 500*0.024,
    'A' : 0.024,
    'iters' : 2,
    'Pu_delta' : 10000,
    'choke_regulator_1': 2,
    'choke_regulator_2': 3,
    'pump_low' : 200000,
    'lowpumprate': 20.0,
    'speed_1': 0.02,
    'speed_2': 0.02,
    'suspension_param': 0.5,
    'conductor_depth': 400.0,
    'conductor_frac_pressure': 0.0,
    'max_wellhead_pressure': 30_000_000.0,
    'max_bottomhole_pressure': 60_000_000.0,
    'max_pump_pressure': 30_000_000.0,
    'dt' : 1}


def get_deep_case_init_data():
    return {
    'v_num' :50,
    'well_l' : 1500,
    'v_delta' : 1500 / 50,
    'vpm' :  0.024,
    'dppm' : 0.008,
    'm3_per_stroke' : 0.008,
    'gaz_v' : 3,
    'ro' : 1200,
    'pu' : 10*10**5,
    'ro_heavy' : 1400,
    'V_real' : 1500*0.024,
    'A' : 0.024,
    'iters' : 2,
    'Pu_delta' : 10000,
    'choke_regulator_1': 2,
    'choke_regulator_2': 3,
    'pump_low' : 100000,
    'lowpumprate': 20.0,
    'speed_1': 1.5,
    'speed_2': 0.1,
    'suspension_param': 0.5,
    'conductor_depth': 400.0,
    'conductor_frac_pressure': 0.0,
    'max_wellhead_pressure': 30_000_000.0,
    'max_bottomhole_pressure': 60_000_000.0,
    'max_pump_pressure': 30_000_000.0,
    'dt' : 1}


def get_case_init_data(case_id) -> tuple[dict, list[str]]:
    db = SessionLocal()
    try:
        details = db.query(CaseDetails).filter(CaseDetails.case_id == case_id).first()
        if not details:
            case_data = get_default_case_init_data()
        else:
            case_data = {
                'v_num': details.v_num,
                'well_l': details.well_l,
                'v_delta': details.v_delta,
                'vpm': details.vpm,
                'dppm': details.dppm,
                'm3_per_stroke': details.m3_per_stroke,
                'gaz_v': details.gaz_v,
                'ro': details.ro,
                'pu': details.pu,
                'ro_heavy': details.ro_heavy,
                'V_real': details.V_real,
                'A': details.A,
                'iters': details.iters,
                'Pu_delta': details.Pu_delta,
                'choke_regulator_1': details.choke_regulator_1,
                'choke_regulator_2': details.choke_regulator_2,
                'pump_low': details.pump_low,
                'lowpumprate': details.lowpumprate,
                'speed_1': details.speed_1,
                'speed_2': details.speed_2,
                'suspension_param': details.suspension_param,
                'conductor_depth': details.conductor_depth if details.conductor_depth is not None else 400.0,
                'conductor_frac_pressure': details.conductor_frac_pressure if details.conductor_frac_pressure is not None else 0.0,
                'max_wellhead_pressure': details.max_wellhead_pressure if details.max_wellhead_pressure is not None else 30_000_000.0,
                'max_bottomhole_pressure': details.max_bottomhole_pressure if details.max_bottomhole_pressure is not None else 60_000_000.0,
                'max_pump_pressure': details.max_pump_pressure if details.max_pump_pressure is not None else 30_000_000.0,
                'dt': details.dt,
            }

        return case_data, list(case_data)
    finally:
        db.close()

#M_init,pzab,v_delta =  s.get_init(v_num, well_l, vpm, gaz_v, ro, pu)
