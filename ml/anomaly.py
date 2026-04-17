import logging
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib

log = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
ANOMALY_PATH = os.path.join(MODEL_DIR, "anomaly.joblib")

# features used for anomaly detection — only numerics, no encoding artifacts
ANOMALY_FEATS = ["year", "mileage_km", "power_kw", "price_eur", "age", "km_per_year"]


def train_anomaly(df: pd.DataFrame) -> np.ndarray:
    """Fit IsolationForest on clean features. Returns decision scores (lower = more anomalous)."""
    feats = [f for f in ANOMALY_FEATS if f in df.columns]
    X = df[feats].fillna(0).values

    clf = IsolationForest(
        n_estimators=100,
        contamination=0.05,  # expect ~5% anomalies
        max_samples="auto",
        random_state=42,
    )
    clf.fit(X)
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump((clf, feats), ANOMALY_PATH)
    log.info("anomaly model saved → %s", ANOMALY_PATH)

    # decision_function: higher = more normal, lower = more anomalous
    return clf.decision_function(X)


def score_anomaly(df: pd.DataFrame) -> np.ndarray:
    """Score rows; requires trained anomaly model. Returns decision scores."""
    if not os.path.exists(ANOMALY_PATH):
        return np.zeros(len(df))
    clf, feats = joblib.load(ANOMALY_PATH)
    available = [f for f in feats if f in df.columns]
    X = df[available].fillna(0).values
    return clf.decision_function(X)


def anomaly_ready() -> bool:
    return os.path.exists(ANOMALY_PATH)
