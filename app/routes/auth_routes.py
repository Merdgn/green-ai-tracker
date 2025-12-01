# app/routes/auth_routes.py

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.utils.auth import verify_api_key, create_access_token, decode_access_token

# Bu router sadece API autentikasyonu için
router = APIRouter(tags=["Auth"])

# Swagger'daki "Authorize" butonuna bilgi vermek için kullanılıyor
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ============================
# 1) API LOGIN SCHEMA
# ============================
class LoginRequest(BaseModel):
    name: str       # Kullanıcı adı
    api_key: str    # API Key


# ============================
# 2) API LOGIN (train_model.py için)
# ============================
@router.post("/auth/login")
def api_login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    train_model.py tarafından kullanılan login endpoint'i.
    Kullanıcı adına ve API Key'e göre JWT üretir.
    """
    user = db.query(models.User).filter(models.User.name == data.name).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı"
        )

    if not verify_api_key(data.api_key, user.api_key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key hatalı"
        )

    # JWT token üret
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(hours=5),
    )

    return {"access_token": token, "token_type": "bearer"}


# ============================
# 3) BEARER TOKEN'DAN USER ÇIKAR
# ============================
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Authorization: Bearer <token> içinden kullanıcıyı çözer.
    API tarafında korumalı endpoint'lerde dependency olarak kullanılır.
    """
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token payload",
        )

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı",
        )

    return user
