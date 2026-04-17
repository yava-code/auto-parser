import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ml_service.schemas import PredictRequest, PredictResponse, ExplainResponse

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

app = FastAPI(title="Car Price ML Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# simple in-memory request counter for /metrics
_request_counts: dict[str, int] = {}
_latencies: dict[str, list[float]] = {}


def _track(endpoint: str, elapsed: float):
    _request_counts[endpoint] = _request_counts.get(endpoint, 0) + 1
    _latencies.setdefault(endpoint, []).append(elapsed)
    if len(_latencies[endpoint]) > 1000:
        _latencies[endpoint] = _latencies[endpoint][-500:]


@app.on_event("startup")
def startup():
    from ml.predict import load_model, model_ready
    if model_ready():
        load_model()
        log.info("ML model preloaded at startup")
    else:
        log.warning("No trained model found — POST /predict will return 503")


@app.get("/health")
def health():
    from ml.predict import model_ready
    ready = model_ready()
    return {"status": "ok" if ready else "degraded", "model_ready": ready}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    from ml.predict import predict_price, model_ready
    if not model_ready():
        raise HTTPException(503, "Model not trained yet")

    t0 = time.perf_counter()
    try:
        price = predict_price(
            req.brand, req.model_name, req.year,
            req.mileage_km, req.power_kw, req.fuel_type, req.transmission,
        )
    except Exception as e:
        log.error("predict error: %s", e)
        raise HTTPException(500, f"Prediction failed: {e}")

    _track("predict", time.perf_counter() - t0)
    log.info("predict: %s %s %d → €%.0f", req.brand, req.model_name, req.year, price)
    return PredictResponse(price_eur=price)


@app.post("/predict/explain", response_model=ExplainResponse)
def predict_explain(req: PredictRequest):
    from ml.predict import explain_price, model_ready
    if not model_ready():
        raise HTTPException(503, "Model not trained yet")

    t0 = time.perf_counter()
    try:
        result = explain_price(
            req.brand, req.model_name, req.year,
            req.mileage_km, req.power_kw, req.fuel_type, req.transmission,
        )
    except Exception as e:
        log.error("explain error: %s", e)
        raise HTTPException(500, f"Explanation failed: {e}")

    _track("explain", time.perf_counter() - t0)
    return ExplainResponse(**result)


@app.get("/metrics")
def metrics():
    """Prometheus-style plaintext metrics."""
    lines = ["# HELP ml_requests_total Total requests per endpoint"]
    lines.append("# TYPE ml_requests_total counter")
    for ep, cnt in _request_counts.items():
        lines.append(f'ml_requests_total{{endpoint="{ep}"}} {cnt}')

    lines.append("# HELP ml_latency_p50_seconds Median latency per endpoint")
    lines.append("# TYPE ml_latency_p50_seconds gauge")
    for ep, lats in _latencies.items():
        if lats:
            sorted_lats = sorted(lats)
            p50 = sorted_lats[len(sorted_lats) // 2]
            p95 = sorted_lats[int(len(sorted_lats) * 0.95)]
            lines.append(f'ml_latency_p50_seconds{{endpoint="{ep}"}} {p50:.4f}')
            lines.append(f'ml_latency_p95_seconds{{endpoint="{ep}"}} {p95:.4f}')

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
