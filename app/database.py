from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL
import re

# Sanitize the DATABASE_URL: strip channel_binding parameter that breaks psycopg2-binary
# Neon adds channel_binding=require by default but psycopg2-binary doesn't support SCRAM channel binding
db_url = re.sub(r'[&?]channel_binding=[^&]*', '', DATABASE_URL)

# Connect arguments depend on backend
connect_args = {}
engine_kwargs = {}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL (Neon) — use pool settings suitable for serverless pooler
    engine_kwargs = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 30,
    }

engine = create_engine(db_url, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
