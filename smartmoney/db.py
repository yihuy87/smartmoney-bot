# smartmoney/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base
from .env import env

DB_URL = env("DATABASE_URL", "sqlite:///smartmoney.db")

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

def init_db():
    Base.metadata.create_all(bind=engine)
