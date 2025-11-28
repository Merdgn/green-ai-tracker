# app/routes/user_routes.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import UserCreate, UserResponse
from app.utils.auth import hash_api_key
from app.routes.auth_routes import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Yeni kullanıcı oluşturur.
    (Projede ilk kullanıcıyı oluşturmak için açık bırakıyoruz.)
    """
    hashed = hash_api_key(user.api_key)

    new_user = models.User(
        name=user.name,
        email=user.email,
        api_key_hash=hashed,
        role="user",
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Tüm kullanıcıları döner.
    API tarafında Bearer token ile korunuyor.
    (Swagger'da Authorize butonuna token verip çağırabilirsin.)
    """
    return db.query(models.User).all()
