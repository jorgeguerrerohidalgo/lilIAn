from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# S4-19: tune the connection pool for production with multi-minute LLM
# calls. The default pool (5 connections, no recycle) saturates when
# BackgroundTasks holds a connection while waiting on the LLM and other
# endpoints need fresh ones — that's what produced the "trigger
# analysis → entire backend 500s" regression. ``pool_recycle`` forces
# connections to be discarded before Supabase's proxy closes them
# silently.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,
    pool_timeout=30,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
