import os
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, create_engine
)
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
    engine_l = Column(Float)
    fuel_type = Column(String)
    transmission = Column(String)
    price_eur = Column(Float)
    scraped_at = Column(DateTime, default=datetime.utcnow)


class CleanListing(Base):
    __tablename__ = "clean_listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_id = Column(Integer, ForeignKey("raw_listings.id"), nullable=False)
    brand_enc = Column(Integer)
    model_enc = Column(Integer)
    year = Column(Integer)
    mileage_km = Column(Integer)
    engine_l = Column(Float)
    fuel_enc = Column(Integer)
    trans_enc = Column(Integer)
    price_eur = Column(Float)
    predicted_price = Column(Float)  # filled after training
