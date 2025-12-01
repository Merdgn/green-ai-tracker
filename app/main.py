# main.py
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
            # Kısa bir DB oturumu açıp kullanıcıyı bul
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
    # İstersen girişliyse dashboard'a at:
    if getattr(request.state, "current_user", None):
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "register.html",
        {"request": request},
    )


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
            {
                "request": request,
                "error": "Bu email zaten kayıtlı!"
            },
        )

    # API key'i hash'le
    hashed = hash_api_key(api_key)

    # Yeni kullanıcı oluştur
    user = models.User(
        name=name,
        email=email,
        api_key_hash=hashed,
        role="user",   # ilk kullanıcı admin olsun istiyorsan burayı "admin" yapabilirsin
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

    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )


# ============================
# RUN DETAIL PAGE – Login zorunlu
# ============================
@app.get("/run/{run_id}", response_class=HTMLResponse)
def run_detail(
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    if not getattr(request.state, "current_user", None):
        return RedirectResponse("/login", status_code=302)

    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run bulunamadı")

    metrics = db.query(models.Metric).filter(models.Metric.run_id == run_id).all()
    emission = db.query(models.Emission).filter(models.Emission.run_id == run_id).first()

    return templates.TemplateResponse(
        "run_detail.html",
        {
            "request": request,
            "run": run,
            "metrics": metrics,
            "emission": emission,
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
