from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

# Connect arguments depend on backend
connect_args = {}
engine_kwargs = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL (Neon) — use pool settings suitable for serverless pooler
    engine_kwargs = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
