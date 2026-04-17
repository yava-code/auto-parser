from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    brand: str
    model_name: str
    year: int = Field(ge=1990, le=2025)
    mileage_km: int = Field(ge=0, le=1_500_000)
    power_kw: float = Field(ge=10, le=1000)
    fuel_type: str
    transmission: str


class PredictResponse(BaseModel):
    price_eur: float


class ExplainResponse(BaseModel):
    price_eur: float
    base_value: float
    contributions: dict[str, float]
