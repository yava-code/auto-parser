import logging
import os
import sys
import pandas as pd
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ml.preprocess import CAT_COLS, NUM_COLS, ENC_PATH, feature_cols

log = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "car_model.joblib")
CURRENT_YEAR = 2025

_model = None
_enc = None
_explainer = None


def load_model():
    global _model, _enc
    if _model is None:
        _model = joblib.load(MODEL_PATH)
        log.info("model loaded from %s", MODEL_PATH)
    if _enc is None:
        _enc = joblib.load(ENC_PATH)
    return _model, _enc


def _build_df(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission):
    age = max(0, CURRENT_YEAR - int(year))
    row = {
        "brand": brand,
        "model": model_name,
        "year": int(year),
        "mileage_km": int(mileage_km),
        "power_kw": float(power_kw),
        "fuel_type": fuel_type,
        "transmission": transmission,
        "age": age,
        "km_per_year": int(mileage_km) / (age + 1),
    }
    df = pd.DataFrame([row])
    _, enc = load_model()
    cat_present = [c for c in CAT_COLS if c in df.columns]
    df[cat_present] = enc.transform(df[cat_present].astype(str)).astype(int)
    df = df.rename(columns={c: f"{c}_enc" for c in cat_present})
    return df


def predict_price(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission) -> float:
    m, _ = load_model()
    df = _build_df(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission)
    feats = feature_cols(df)
    return round(float(m.predict(df[feats])[0]), 2)


def explain_price(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission) -> dict:
    """Return predicted price with SHAP-based feature contributions."""
    global _explainer
    m, _ = load_model()
    df = _build_df(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission)
    feats = feature_cols(df)
    price = round(float(m.predict(df[feats])[0]), 2)

    try:
        import shap
        if _explainer is None:
            _explainer = shap.TreeExplainer(m)
        shap_vals = _explainer.shap_values(df[feats])
        base_val = float(_explainer.expected_value)
        contributions = {feat: round(float(shap_vals[0][i]), 2) for i, feat in enumerate(feats)}
    except Exception as e:
        log.warning("SHAP explain failed: %s", e)
        contributions = {}
        base_val = price

    return {
        "price_eur": price,
        "base_value": round(base_val, 2),
        "contributions": contributions,
    }


def model_ready() -> bool:
    return os.path.exists(MODEL_PATH) and os.path.exists(ENC_PATH)
