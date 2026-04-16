import os
import sys
import pandas as pd
import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ml.preprocess import CAT_COLS, NUM_COLS, ENC_PATH, feature_cols, encode_df

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "car_model.joblib")

_model = None
_enc = None


def load_model():
    global _model, _enc
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    if _enc is None:
        _enc = joblib.load(ENC_PATH)
    return _model, _enc


def predict_price(brand, model_name, year, mileage_km, engine_l, fuel_type, transmission) -> float:
    m, enc = load_model()

    row = {
        "brand": brand,
        "model": model_name,
        "year": int(year),
        "mileage_km": int(mileage_km),
        "engine_l": float(engine_l),
        "fuel_type": fuel_type,
        "transmission": transmission,
    }
    df = pd.DataFrame([row])

    # encode cats with the saved encoder (unknown → -1)
    cat_present = [c for c in CAT_COLS if c in df.columns]
    df[cat_present] = enc.transform(df[cat_present].astype(str))
    df = df.rename(columns={c: f"{c}_enc" for c in cat_present})

    feats = feature_cols(df)
    price = m.predict(df[feats])[0]
    return round(float(price), 2)


def model_ready() -> bool:
    return os.path.exists(MODEL_PATH) and os.path.exists(ENC_PATH)
