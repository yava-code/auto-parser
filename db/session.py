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


def _add_columns(conn, table: str, new_cols: list[tuple[str, str]]):
    insp = inspect(engine)
    try:
        existing = {c["name"] for c in insp.get_columns(table)}
    except exc.NoSuchTableError:
        return
    for col, dtype in new_cols:
        if col not in existing:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {dtype}"))
                log.info("migrated: added %s.%s", table, col)
            except Exception as e:
                log.warning("migration skipped %s.%s: %s", table, col, e)


def _migrate():
    with engine.begin() as conn:
        _add_columns(conn, "raw_listings", [
            ("color", "VARCHAR"),
            ("body_type", "VARCHAR"),
            ("location", "VARCHAR"),
            ("engine_cc", "FLOAT"),
            ("doors", "INTEGER"),
        ])
        _add_columns(conn, "clean_listings", [
            ("anomaly_score", "FLOAT"),
        ])
