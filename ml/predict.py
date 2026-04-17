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
MODEL_Q025 = os.path.join(MODEL_DIR, "car_model_q025.joblib")
MODEL_Q975 = os.path.join(MODEL_DIR, "car_model_q975.joblib")
CURRENT_YEAR = 2025

_model = None
_enc = None
_q025 = None
_q975 = None
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
        "brand": brand, "model": model_name,
        "year": int(year), "mileage_km": int(mileage_km),
        "power_kw": float(power_kw), "fuel_type": fuel_type,
        "transmission": transmission, "age": age,
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
    return round(float(m.predict(df[feature_cols(df)])[0]), 2)


def predict_interval(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission) -> dict:
    """Return point estimate + 95% prediction interval from quantile models."""
    global _q025, _q975
    df = _build_df(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission)
    feats = feature_cols(df)
    m, _ = load_model()
    point = round(float(m.predict(df[feats])[0]), 2)

    lo, hi = point, point
    try:
        if _q025 is None and os.path.exists(MODEL_Q025):
            _q025 = joblib.load(MODEL_Q025)
        if _q975 is None and os.path.exists(MODEL_Q975):
            _q975 = joblib.load(MODEL_Q975)
        if _q025 and _q975:
            lo = round(float(_q025.predict(df[feats])[0]), 2)
            hi = round(float(_q975.predict(df[feats])[0]), 2)
    except Exception as e:
        log.warning("quantile predict failed: %s", e)

    return {"point": point, "lower_95": lo, "upper_95": hi}


def explain_price(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission) -> dict:
    """Return predicted price with SHAP-based feature contributions."""
    global _explainer
    m, _ = load_model()
    df = _build_df(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission)
    feats = feature_cols(df)
    price = round(float(m.predict(df[feats])[0]), 2)

    interval = predict_interval(brand, model_name, year, mileage_km, power_kw, fuel_type, transmission)

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
        "lower_95": interval["lower_95"],
        "upper_95": interval["upper_95"],
        "base_value": round(base_val, 2),
        "contributions": contributions,
    }


def model_ready() -> bool:
    return os.path.exists(MODEL_PATH) and os.path.exists(ENC_PATH)
