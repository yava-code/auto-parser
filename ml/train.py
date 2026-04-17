import logging
import os
import sys
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from catboost import CatBoostRegressor
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import SessionLocal, init_db
from db.models import RawListing, CleanListing
from ml.preprocess import clean_df, encode_df, feature_cols, TARGET
from ml.anomaly import train_anomaly

log = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "car_model.joblib")
MODEL_Q025 = os.path.join(MODEL_DIR, "car_model_q025.joblib")
MODEL_Q975 = os.path.join(MODEL_DIR, "car_model_q975.joblib")


def load_raw() -> pd.DataFrame:
    session = SessionLocal()
    try:
        rows = session.query(RawListing).all()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([{
            "raw_id": r.id, "brand": r.brand, "model": r.model, "year": r.year,
            "mileage_km": r.mileage_km, "power_kw": r.power_kw,
            "fuel_type": r.fuel_type, "transmission": r.transmission,
            "price_eur": r.price_eur,
        } for r in rows])
    finally:
        session.close()


def save_clean(df: pd.DataFrame, predictions: list[float], anomaly_scores: list[float]):
    session = SessionLocal()
    try:
        session.query(CleanListing).delete()
        for i, row in df.iterrows():
            session.add(CleanListing(
                raw_id=int(row.get("raw_id", 0)),
                brand_enc=int(row.get("brand_enc", -1)),
                model_enc=int(row.get("model_enc", -1)),
                year=int(row["year"]),
                mileage_km=int(row["mileage_km"]),
                power_kw=float(row.get("power_kw", 0)),
                age=int(row.get("age", 0)),
                km_per_year=float(row.get("km_per_year", 0)),
                fuel_enc=int(row.get("fuel_type_enc", -1)),
                trans_enc=int(row.get("transmission_enc", -1)),
                price_eur=float(row[TARGET]),
                predicted_price=float(predictions[i]),
                anomaly_score=float(anomaly_scores[i]) if i < len(anomaly_scores) else None,
            ))
        session.commit()
        log.info("clean_listings updated: %d rows", len(df))
    except Exception as e:
        session.rollback()
        log.error("DB save error: %s", e)
    finally:
        session.close()


def _train_quantile(X_train, y_train, X_test, y_test, cat_idx, alpha, path):
    """Train a quantile regression model and save it."""
    m = CatBoostRegressor(
        iterations=300,
        learning_rate=0.05,
        depth=5,
        loss_function=f"Quantile:alpha={alpha}",
        cat_features=cat_idx,
        verbose=0,
        random_seed=42,
    )
    m.fit(X_train, y_train, eval_set=(X_test, y_test))
    joblib.dump(m, path)
    log.info("quantile model (alpha=%.3f) saved → %s", alpha, path)
    return m


def run_training():
    init_db()
    df = load_raw()

    if len(df) < 10:
        log.warning("not enough data (%d rows) — aborting", len(df))
        return None

    log.info("loaded %d raw rows", len(df))
    df = clean_df(df)
    log.info("after cleaning: %d rows", len(df))

    df, enc = encode_df(df, fit=True)
    feats = feature_cols(df)

    X = df[feats]
    y = df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    cat_idx = [i for i, col in enumerate(feats) if col.endswith("_enc")]

    # — main model (RMSE) —
    model = CatBoostRegressor(
        iterations=500,
        learning_rate=0.05,
        depth=6,
        loss_function="RMSE",
        cat_features=cat_idx,
        verbose=100,
        random_seed=42,
    )
    model.fit(X_train, y_train, eval_set=(X_test, y_test))

    preds_test = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds_test)
    r2 = r2_score(y_test, preds_test)
    median_price = float(y.median())
    mae_pct = mae / median_price * 100

    log.info("MAE: €%.0f  (%.1f%% of median €%.0f)", mae, mae_pct, median_price)
    log.info("R²:  %.4f", r2)
    print(f"\n[train] MAE: €{mae:.0f}  ({mae_pct:.1f}% of median €{median_price:.0f})")
    print(f"[train] R²:  {r2:.4f}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    log.info("main model saved → %s", MODEL_PATH)

    # — quantile models for 95% prediction interval —
    try:
        _train_quantile(X_train, y_train, X_test, y_test, cat_idx, 0.025, MODEL_Q025)
        _train_quantile(X_train, y_train, X_test, y_test, cat_idx, 0.975, MODEL_Q975)
    except Exception as e:
        log.warning("quantile training failed: %s", e)

    # — anomaly detection —
    try:
        # add price_eur back for anomaly scoring (it's in df still)
        anomaly_scores = train_anomaly(df).tolist()
        log.info("anomaly model trained on %d rows", len(df))
    except Exception as e:
        log.warning("anomaly training failed: %s", e)
        anomaly_scores = [0.0] * len(df)

    # — SHAP summary plot —
    try:
        import shap, matplotlib.pyplot as plt
        os.makedirs("assets", exist_ok=True)
        explainer = shap.TreeExplainer(model)
        sample = X_test.sample(min(200, len(X_test)), random_state=42)
        shap_vals = explainer.shap_values(sample)
        shap.summary_plot(shap_vals, sample, show=False)
        plt.tight_layout()
        plt.savefig("assets/shap_summary.png", dpi=120, bbox_inches="tight")
        plt.close()
        log.info("SHAP plot saved → assets/shap_summary.png")
    except Exception as e:
        log.warning("SHAP skipped: %s", e)

    # — MLflow tracking —
    try:
        import mlflow
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "mlruns")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("car-price-prediction")

        with mlflow.start_run():
            mlflow.log_params({
                "iterations": 500, "learning_rate": 0.05,
                "depth": 6, "loss_function": "RMSE", "rows": len(df),
            })
            mlflow.log_metrics({"mae": mae, "r2": r2, "mae_pct": mae_pct})
            mlflow.log_artifact(MODEL_PATH, artifact_path="models")
            if os.path.exists("assets/shap_summary.png"):
                mlflow.log_artifact("assets/shap_summary.png", artifact_path="plots")
        log.info("MLflow run logged to %s", tracking_uri)
    except Exception as e:
        log.warning("MLflow logging skipped: %s", e)

    # — save clean listings with predictions + anomaly scores —
    all_preds = model.predict(X).tolist()
    save_clean(df, all_preds, anomaly_scores)

    return {"mae": mae, "mae_pct": mae_pct, "r2": r2, "rows": len(df)}


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
    run_training()
