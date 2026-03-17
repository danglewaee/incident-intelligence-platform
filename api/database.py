import os
import time

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://incident:incident@postgres:5432/incident_intel",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema(max_attempts: int = 5, retry_delay_seconds: float = 1.0):
    for attempt in range(1, max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except IntegrityError as exc:
            # Multiple services may try to create the same tables at startup.
            # Retry briefly and let the winner finish the DDL.
            if "pg_type_typname_nsp_index" not in str(exc) or attempt == max_attempts:
                raise
            time.sleep(retry_delay_seconds)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
