from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.utils.auth import verify_api_key, create_access_token, decode_access_token, hash_api_key

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ============================
# API LOGIN SCHEMA
# ============================
class LoginRequest(BaseModel):
    name: str
    api_key: str


# ============================
# HTML LOGIN PAGE
# ============================
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    api_key: str = Form(...)
):
    user = db.query(models.User).filter(models.User.name == name).first()

    if not user or not verify_api_key(api_key, user.api_key_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Kullanıcı adı veya API key hatalı."}
        )

    # Token üret
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(hours=5),
    )

    response = RedirectResponse("/", status_code=302)
    response.set_cookie("session_token", access_token, httponly=True)

    return response


# ============================
# API LOGIN (TRAIN SCRIPT İÇİN)
# ============================
@router.post("/auth/login")
def api_login(data: LoginRequest, db: Session = Depends(get_db)):
    """Train_model.py tarafından kullanılan login."""
    user = db.query(models.User).filter(models.User.name == data.name).first()

    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")

    if not verify_api_key(data.api_key, user.api_key_hash):
        raise HTTPException(status_code=401, detail="API key hatalı")

    token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(hours=5),
    )

    return {"access_token": token, "token_type": "bearer"}


# ============================
# REGISTER PAGE
# ============================
@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
def register_submit(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    email: str = Form(...),
    api_key: str = Form(...)
):
    # email kontrol
    exists = db.query(models.User).filter(models.User.email == email).first()

    if exists:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Bu email zaten kayıtlı!"}
        )

    hashed = hash_api_key(api_key)

    user = models.User(
        name=name,
        email=email,
        api_key_hash=hashed,
        role="user"
    )
    db.add(user)
    db.commit()

    return RedirectResponse("/login", status_code=302)


# ============================
# LOGOUT
# ============================
@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("session_token")
    return response


# ============================
# TOKEN CHECK (API PROTECTION)
# ============================
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Geçersiz token")

    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()

    return user
