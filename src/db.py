import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required for database connections.")

normalized_url = DATABASE_URL
if normalized_url.startswith("postgres://"):
    normalized_url = normalized_url.replace("postgres://", "postgresql+psycopg://", 1)
elif normalized_url.startswith("postgresql://"):
    normalized_url = normalized_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(normalized_url, future=True, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()