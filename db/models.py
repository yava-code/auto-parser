from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class RawListing(Base):
    __tablename__ = "raw_listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    brand = Column(String)
    model = Column(String)
    year = Column(Integer)
    mileage_km = Column(Integer)
    power_kw = Column(Float)
    fuel_type = Column(String)
    transmission = Column(String)
    price_eur = Column(Float)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    color = Column(String)
    body_type = Column(String)
    location = Column(String)
    engine_cc = Column(Float)
    doors = Column(Integer)


class CleanListing(Base):
    __tablename__ = "clean_listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_id = Column(Integer, ForeignKey("raw_listings.id"), nullable=False)
    brand_enc = Column(Integer)
    model_enc = Column(Integer)
    year = Column(Integer)
    mileage_km = Column(Integer)
    power_kw = Column(Float)
    age = Column(Integer)
    km_per_year = Column(Float)
    fuel_enc = Column(Integer)
    trans_enc = Column(Integer)
    price_eur = Column(Float)
    predicted_price = Column(Float)
    anomaly_score = Column(Float)   # lower = more anomalous (IsolationForest decision score)


class UserUsage(Base):
    __tablename__ = "user_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    free_uses_left = Column(Integer, default=5, nullable=False)
    paid_uses = Column(Integer, default=0, nullable=False)
    total_uses = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class UserAlert(Base):
    __tablename__ = "user_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    brand = Column(String)
    max_price_eur = Column(Float)
    min_year = Column(Integer)
    max_mileage_km = Column(Integer)
    fuel_type = Column(String)
    active = Column(Boolean, default=True, nullable=False)
    last_notified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
