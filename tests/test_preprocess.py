"""Tests for ml/preprocess.py data cleaning pipeline."""
import pytest
import pandas as pd
import numpy as np
from ml.preprocess import clean_df, feature_cols


def _sample_df(**overrides):
    base = {
        "brand": ["BMW", "Toyota", "VW", "Audi", "Ford"] * 10,
        "model": ["3 Series", "Corolla", "Golf", "A4", "Focus"] * 10,
        "year": [2018, 2019, 2020, 2017, 2016] * 10,
        "mileage_km": [80000, 50000, 100000, 120000, 150000] * 10,
        "power_kw": [140.0, 90.0, 85.0, 110.0, 75.0] * 10,
        "fuel_type": ["Petrol", "Hybrid", "Diesel", "Petrol", "Diesel"] * 10,
        "transmission": ["Manual", "Automatic", "Manual", "Automatic", "Manual"] * 10,
        "price_eur": [20000, 15000, 12000, 18000, 8000] * 10,
    }
    base.update(overrides)
    return pd.DataFrame(base)


class TestCleanDf:
    def test_drops_missing_price(self):
        df = _sample_df()
        df.loc[0, "price_eur"] = None
        result = clean_df(df)
        assert len(result) < len(df)

    def test_drops_missing_brand(self):
        df = _sample_df()
        df.loc[0, "brand"] = None
        result = clean_df(df)
        assert len(result) < len(df)

    def test_drops_missing_year(self):
        df = _sample_df()
        df.loc[0, "year"] = None
        result = clean_df(df)
        assert len(result) < len(df)

    def test_fills_power_kw_with_median(self):
        df = _sample_df()
        df.loc[0, "power_kw"] = None
        result = clean_df(df)
        assert result["power_kw"].isna().sum() == 0

    def test_fills_fuel_with_mode(self):
        df = _sample_df()
        df.loc[0, "fuel_type"] = None
        result = clean_df(df)
        assert result["fuel_type"].isna().sum() == 0

    def test_age_engineering(self):
        df = _sample_df()
        result = clean_df(df)
        assert "age" in result.columns
        assert (result["age"] >= 0).all()

    def test_km_per_year_engineering(self):
        df = _sample_df()
        result = clean_df(df)
        assert "km_per_year" in result.columns
        assert (result["km_per_year"] >= 0).all()

    def test_year_filter(self):
        df = _sample_df(year=[1850, 2030, 2000, 2010, 2015] * 10)
        result = clean_df(df)
        assert (result["year"] >= 1990).all()
        assert (result["year"] <= 2025).all()

    def test_mileage_non_negative(self):
        df = _sample_df(mileage_km=[-100, 50000, 80000, 90000, 70000] * 10)
        result = clean_df(df)
        assert (result["mileage_km"] >= 0).all()

    def test_price_outlier_removal(self):
        df = _sample_df()
        df.loc[0, "price_eur"] = 10_000_000  # extreme outlier
        df.loc[1, "price_eur"] = 1           # extreme low
        result = clean_df(df)
        assert result["price_eur"].max() < 10_000_000

    def test_returns_reset_index(self):
        df = _sample_df()
        result = clean_df(df)
        assert list(result.index) == list(range(len(result)))


class TestFeatureCols:
    def test_includes_encoded_cats(self):
        df = pd.DataFrame({
            "brand_enc": [0], "model_enc": [1], "year": [2020],
            "mileage_km": [50000], "power_kw": [100.0],
            "age": [5], "km_per_year": [10000.0],
            "fuel_type_enc": [0], "transmission_enc": [1],
        })
        cols = feature_cols(df)
        assert "brand_enc" in cols
        assert "fuel_type_enc" in cols
        assert "year" in cols

    def test_only_present_columns(self):
        df = pd.DataFrame({"year": [2020], "mileage_km": [50000]})
        cols = feature_cols(df)
        assert "brand_enc" not in cols
        assert "year" in cols
