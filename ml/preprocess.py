import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder
import joblib
import os

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
ENC_PATH = os.path.join(MODEL_DIR, "encoder.joblib")

CAT_COLS = ["brand", "model", "fuel_type", "transmission"]
NUM_COLS = ["year", "mileage_km", "power_kw", "age", "km_per_year"]
TARGET = "price_eur"

REQUIRED = ["brand", "year", "mileage_km", "price_eur"]


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    # drop rows missing the columns we can't impute
    df = df.dropna(subset=REQUIRED).copy()

    # fill optional numerics with median
    for col in ["power_kw"]:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    # fill optional categoricals with mode
    for col in ["fuel_type", "transmission", "model"]:
        if col in df.columns:
            mode_val = df[col].mode()
            df[col] = df[col].fillna(mode_val[0] if len(mode_val) else "Unknown")

    # remove price outliers via IQR
    q1, q3 = df[TARGET].quantile(0.05), df[TARGET].quantile(0.95)
    df = df[(df[TARGET] >= q1) & (df[TARGET] <= q3)]

    # sanity: year in realistic range, mileage > 0
    df = df[(df["year"] >= 1990) & (df["year"] <= 2025)]
    df = df[df["mileage_km"] >= 0]

    # feature engineering
    CURRENT_YEAR = 2025
    df["age"] = CURRENT_YEAR - df["year"]
    df["age"] = df["age"].clip(lower=0)
    df["km_per_year"] = df["mileage_km"] / (df["age"] + 1)

    return df.reset_index(drop=True)


def encode_df(df: pd.DataFrame, fit=True) -> tuple[pd.DataFrame, OrdinalEncoder]:
    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    cat_present = [c for c in CAT_COLS if c in df.columns]

    if fit:
        df[cat_present] = enc.fit_transform(df[cat_present].astype(str)).astype(int)
        os.makedirs(MODEL_DIR, exist_ok=True)
        joblib.dump(enc, ENC_PATH)
    else:
        enc = joblib.load(ENC_PATH)
        df[cat_present] = enc.transform(df[cat_present].astype(str)).astype(int)

    # rename to *_enc columns so we know they're encoded
    rename = {c: f"{c}_enc" for c in cat_present}
    df = df.rename(columns=rename)

    return df, enc


def feature_cols(df: pd.DataFrame) -> list[str]:
    enc_cats = [f"{c}_enc" for c in CAT_COLS if f"{c}_enc" in df.columns]
    nums = [c for c in NUM_COLS if c in df.columns]
    return enc_cats + nums
