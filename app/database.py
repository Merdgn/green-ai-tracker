from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://postgres:1100@localhost/green_ai_tracker"

# SQLAlchemy Engine
engine = create_engine(DATABASE_URL, echo=True)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class (modeller bunu miras alacak)
Base = declarative_base()

# DB bağlantısını her istek öncesi açıp sonrasında kapatmamızı sağlayan fonksiyon
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
