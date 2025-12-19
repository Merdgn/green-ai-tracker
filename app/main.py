from datetime import datetime

from fastapi import (
    FastAPI,
    Request,
    Depends,
    Form,
    HTTPException,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import engine, get_db
from app import models
from app.routes import auth_routes, user_routes, devices, runs, metrics, emissions, dashboard
from app.routes import monitor  # sistem canlı izleme

from app.utils.auth import (
    verify_api_key,
    create_access_token,
    decode_access_token,
    hash_api_key,
)

# ============================
# Template klasörü
# ============================
templates = Jinja2Templates(directory="app/templates")

# ============================
# FastAPI App
# ============================
app = FastAPI(title="Green AI Tracker")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ============================
# Swagger Bearer Auth
# ============================
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Green AI Tracker",
        version="1.0.0",
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# ============================
# Router'lar
# ============================
app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(devices.router)
app.include_router(runs.router)
app.include_router(metrics.router)
app.include_router(emissions.router)
app.include_router(dashboard.router)
app.include_router(monitor.router)

# ============================
# DB tablolarını oluştur
# ============================
models.Base.metadata.create_all(bind=engine)

# ============================
# Yardımcı: Cookie'den kullanıcıyı çöz
# ============================
def get_current_user_from_cookie(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User:
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user

# ============================
# MIDDLEWARE: request.state.current_user
# ============================
@app.middleware("http")
async def add_current_user(request: Request, call_next):
    """
    Tüm isteklerde cookie'deki token'i çöz ve
    request.state.current_user içine kullanıcıyı koy.
    (Login olmayanlarda None olur.)
    """
    request.state.current_user = None

    token = request.cookies.get("session_token")
    if token:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")
            db_gen = get_db()
            db = next(db_gen)
            try:
                user = db.query(models.User).filter(models.User.id == int(user_id)).first()
                request.state.current_user = user
            finally:
                db.close()

    response = await call_next(request)
    return response

# ============================
# HTML LOGIN PAGE (GET)
# ============================
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    # Zaten login'liyse direkt dashboard'a gönder
    if getattr(request.state, "current_user", None):
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})

# ============================
# HTML LOGIN SUBMIT (POST)
# ============================
@app.post("/login")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    api_key: str = Form(...),
):
    # Kullanıcıyı bul
    user = db.query(models.User).filter(models.User.name == name).first()

    if not user or not verify_api_key(api_key, user.api_key_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Kullanıcı adı veya API Key hatalı!"},
        )

    # JWT üret
    token = create_access_token({"sub": str(user.id), "role": user.role})

    # Cookie'ye yaz
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=60 * 60,
    )

    return response

# ============================
# REGISTER PAGE (GET)
# ============================
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if getattr(request.state, "current_user", None):
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse("register.html", {"request": request})

# ============================
# REGISTER SUBMIT (POST)
# ============================
@app.post("/register")
def register_submit(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    email: str = Form(...),
    api_key: str = Form(...),
):
    # Bu email daha önce kullanılmış mı?
    exists = db.query(models.User).filter(models.User.email == email).first()
    if exists:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Bu email zaten kayıtlı!"},
        )

    # API key'i hash'le
    hashed = hash_api_key(api_key)

    # Yeni kullanıcı oluştur
    user = models.User(
        name=name,
        email=email,
        api_key_hash=hashed,
        role="user",
    )

    db.add(user)
    db.commit()

    # Kayıttan sonra login sayfasına yönlendir
    return RedirectResponse("/login", status_code=302)

# ============================
# LOGOUT
# ============================
@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session_token")
    return response

# ============================
# Dashboard (GENEL ÖZET) – Login ZORUNLU
# ============================
@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    """
    Genel istatistiklerin ve son 5 run'ın olduğu ana sayfa.
    Login olmayanlar /login sayfasına yönlendirilir.
    """
    if not getattr(request.state, "current_user", None):
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("index.html", {"request": request})

# ============================
# RUN DETAIL PAGE – Login zorunlu
# ============================
@app.get("/run/{run_id}", response_class=HTMLResponse)
def run_detail(
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    # Login kontrolü
    if not getattr(request.state, "current_user", None):
        return RedirectResponse("/login", status_code=302)

    # Run kaydı
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run bulunamadı")

    # Metrikler (ts'e göre sırala)
    metrics = (
        db.query(models.Metric)
        .filter(models.Metric.run_id == run_id)
        .order_by(models.Metric.ts.asc())
        .all()
    )

    # Emisyon kaydı
    emission = (
        db.query(models.Emission)
        .filter(models.Emission.run_id == run_id)
        .first()
    )

    # === BÖLGESEL KARŞILAŞTIRMA SENARYOLARI ===
    region_scenarios = []

    if emission and emission.energy_kwh:
        total_energy_kwh = float(emission.energy_kwh or 0.0)
        total_emission_kg = float(emission.emission_kg or 0.0)

        # 1) TR – veritabanındaki gerçek değer (faktör: kg CO2e / kWh)
        tr_factor = None
        if total_energy_kwh > 0:
            tr_factor = total_emission_kg / total_energy_kwh

        region_scenarios.append(
            {
                "code": emission.region_code or "TR",
                "label": f"Türkiye (gerçek bölge: {emission.region_code or 'TR'})",
                "factor": tr_factor,
                "co2_kg": total_emission_kg,
            }
        )

        # 2) Senaryo bölgeleri (aynı enerji, farklı emisyon faktörü)
        scenario_regions = [
            {
                "code": "EU-FR",
                "label": "AB - Fransa (EU, France)",
                "factor": 0.06,
            },
            {
                "code": "US-IA",
                "label": "ABD - Iowa (US, Iowa)",
                "factor": 0.40,
            },
        ]

        for reg in scenario_regions:
            region_scenarios.append(
                {
                    "code": reg["code"],
                    "label": reg["label"],
                    "factor": reg["factor"],
                    "co2_kg": total_energy_kwh * reg["factor"],
                }
            )

    # === GreenScore (0–100) ===
    greenscore = None
    greenscore_comment = None

    if emission and emission.energy_kwh and emission.emission_kg:
        try:
            energy_kwh = float(emission.energy_kwh)
            emission_kg = float(emission.emission_kg)
            if energy_kwh > 0:
                intensity = emission_kg / energy_kwh  # kg CO2e / kWh

                # 0.1–0.9 aralığını ölçekleyip 0–100'e map edelim
                min_i, max_i = 0.1, 0.9
                x = max(min(intensity, max_i), min_i)
                greenscore = round(100 - (x - min_i) / (max_i - min_i) * 100)

                if greenscore >= 80:
                    greenscore_comment = "Çok iyi: düşük karbon yoğunluğu."
                elif greenscore >= 60:
                    greenscore_comment = "İyi: enerji verimliliği kabul edilebilir düzeyde."
                elif greenscore >= 40:
                    greenscore_comment = "Orta: iyileştirme potansiyeli var."
                else:
                    greenscore_comment = "Düşük: karbon yoğunluğu yüksek, optimizasyon gerekli."
        except Exception:
            greenscore = None
            greenscore_comment = None

    # === Kümülatif enerji serisi (kWh) ===
    energy_series = []
    if metrics:
        cumulative_kwh = 0.0
        prev_ts = None
        raw_series = []

        for m in metrics:
            if not m.ts:
                continue

            # İlk nokta: 0 kWh ile başlasın
            if prev_ts is None:
                prev_ts = m.ts
                raw_series.append(
                    {
                        "time": m.ts.strftime("%H:%M:%S"),
                        "kwh": round(cumulative_kwh, 6),
                    }
                )
                continue

            delta_s = (m.ts - prev_ts).total_seconds()
            if delta_s < 0:
                delta_s = 0

            power_w = float(m.gpu_power_w or 0.0)
            incremental = power_w * delta_s / 3_600_000.0  # Wh -> kWh
            cumulative_kwh += incremental

            raw_series.append(
                {
                    "time": m.ts.strftime("%H:%M:%S"),
                    "kwh": round(cumulative_kwh, 6),
                }
            )
            prev_ts = m.ts

        # Eğer emisyon tablosunda toplam enerji varsa, seriyi ona scale edelim
        try:
            if emission and emission.energy_kwh and cumulative_kwh > 0:
                target_kwh = float(emission.energy_kwh)
                scale = target_kwh / cumulative_kwh
                for p in raw_series:
                    p["kwh"] = round(p["kwh"] * scale, 6)
        except Exception:
            pass

        energy_series = raw_series

    # Template'e gönder
    return templates.TemplateResponse(
        "run_detail.html",
        {
            "request": request,
            "run": run,
            "metrics": metrics,
            "emission": emission,
            "region_scenarios": region_scenarios,
            "greenscore": greenscore,
            "greenscore_comment": greenscore_comment,
            "energy_series": energy_series,
        },
    )

# ============================
# LIST PAGES FOR RUNS / DEVICES / USERS – Login zorunlu
# ============================
@app.get("/runs/list", response_class=HTMLResponse)
def runs_list(
    request: Request,
    db: Session = Depends(get_db),
):
    if not getattr(request.state, "current_user", None):
        return RedirectResponse("/login", status_code=302)

    runs = db.query(models.Run).all()
    return templates.TemplateResponse(
        "runs_list.html",
        {"request": request, "runs": runs},
    )


@app.get("/devices/list", response_class=HTMLResponse)
def devices_list(
    request: Request,
    db: Session = Depends(get_db),
):
    if not getattr(request.state, "current_user", None):
        return RedirectResponse("/login", status_code=302)

    devices = db.query(models.Device).all()
    return templates.TemplateResponse(
        "devices_list.html",
        {"request": request, "devices": devices},
    )


@app.get("/users/list", response_class=HTMLResponse)
def users_list(
    request: Request,
    db: Session = Depends(get_db),
):
    if not getattr(request.state, "current_user", None):
        return RedirectResponse("/login", status_code=302)

    users = db.query(models.User).all()
    return templates.TemplateResponse(
        "users_list.html",
        {"request": request, "users": users},
    )
