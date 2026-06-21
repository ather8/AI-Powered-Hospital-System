from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from dotenv import load_dotenv
import os

# Load backend/.env here directly rather than relying on some other module
# (main.py, config.py, alembic/env.py, ...) having already called
# load_dotenv() before this module gets imported. Whichever module imports
# app.db first wins/loses that race otherwise, which is exactly what broke
# both `uvicorn app.main:app` and `alembic upgrade head` above.
load_dotenv()

# Database URL must come from the environment. Never hardcode credentials here —
# this file is committed to git, and a hardcoded fallback effectively leaks the
# credential to anyone with repo access (including git history).
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Define it in backend/.env or your environment."
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
