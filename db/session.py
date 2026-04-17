import logging
import os
from sqlalchemy import create_engine, text, inspect, exc
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cars:cars@localhost:5432/cars")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    from db.models import Base
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """Add new columns to existing tables without dropping data."""
    try:
        insp = inspect(engine)
        existing = {c["name"] for c in insp.get_columns("raw_listings")}
    except exc.NoSuchTableError:
        return

    new_cols = [
        ("color", "VARCHAR"),
        ("body_type", "VARCHAR"),
        ("location", "VARCHAR"),
        ("engine_cc", "FLOAT"),
        ("doors", "INTEGER"),
    ]
    with engine.begin() as conn:
        for col, dtype in new_cols:
            if col not in existing:
                try:
                    conn.execute(text(f"ALTER TABLE raw_listings ADD COLUMN {col} {dtype}"))
                    log.info("migrated: added raw_listings.%s", col)
                except Exception as e:
                    log.warning("migration skipped %s: %s", col, e)
