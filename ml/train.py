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

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "car_model.joblib")


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


def save_clean(df: pd.DataFrame, predictions: list[float]):
    session = SessionLocal()
    try:
        # wipe and re-insert — keeps it simple for MVP
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
            ))
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[train] DB save error: {e}")
    finally:
        session.close()


def run_training():
    init_db()
    df = load_raw()

    if len(df) < 10:
        print(f"[train] not enough data ({len(df)} rows) — aborting")
        return None

    print(f"[train] loaded {len(df)} raw rows")
    df = clean_df(df)
    print(f"[train] after cleaning: {len(df)} rows")

    df, enc = encode_df(df, fit=True)
    feats = feature_cols(df)

    X = df[feats]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # CatBoost: encoded cats are already ints, pass as cat indices
    cat_feat_indices = [i for i, col in enumerate(feats) if col.endswith("_enc")]

    model = CatBoostRegressor(
        iterations=500,
        learning_rate=0.05,
        depth=6,
        loss_function="RMSE",
        cat_features=cat_feat_indices,
        verbose=100,
        random_seed=42,
    )
    model.fit(X_train, y_train, eval_set=(X_test, y_test))

    preds_test = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds_test)
    r2 = r2_score(y_test, preds_test)
    median_price = float(y.median())
    mae_pct = mae / median_price * 100

    print(f"\n[train] MAE: €{mae:.0f}  ({mae_pct:.1f}% of median €{median_price:.0f})")
    print(f"[train] R²:  {r2:.4f}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"[train] model saved → {MODEL_PATH}")

    # SHAP summary plot
    try:
        import shap
        import matplotlib.pyplot as plt
        os.makedirs("assets", exist_ok=True)
        explainer = shap.TreeExplainer(model)
        sample = X_test.sample(min(200, len(X_test)), random_state=42)
        shap_vals = explainer.shap_values(sample)
        shap.summary_plot(shap_vals, sample, show=False)
        plt.tight_layout()
        plt.savefig("assets/shap_summary.png", dpi=120, bbox_inches="tight")
        plt.close()
        print("[train] SHAP plot saved → assets/shap_summary.png")
    except Exception as e:
        print(f"[train] SHAP skipped: {e}")

    # predict on full df to store in clean_listings
    all_preds = model.predict(X).tolist()
    save_clean(df, all_preds)
    print(f"[train] clean_listings updated")

    return {"mae": mae, "mae_pct": mae_pct, "r2": r2, "rows": len(df)}


if __name__ == "__main__":
    run_training()
