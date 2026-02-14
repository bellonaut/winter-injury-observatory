"""
FastAPI Application for Winter Injury Observatory.

Provides landing page, prediction endpoints, model metrics, and health checks.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.models import BatchPredictionRequest, PredictionRequest, PredictionResponse
from api.services import DatabaseService, ModelService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LANDING_PAGE_PATH = Path(__file__).parent / "static" / "index.html"

# Global model service
model_service: Optional[ModelService] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifecycle management."""
    global model_service

    logger.info("Initializing model service...")
    model_service = ModelService()
    await model_service.load_model()
    if model_service.model is None:
        logger.warning("Model unavailable: %s", model_service.load_error)

    yield

    logger.info("Shutting down API")


app = FastAPI(
    title="Winter Injury Risk Observatory API",
    description="ML-powered winter injury risk prediction for Edmonton",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Verify demo token or API secret token."""
    expected_token = os.getenv("DEMO_API_TOKEN") or os.getenv(
        "API_SECRET_KEY", "dev-secret"
    )
    if credentials is None or credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return credentials


@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Serve portfolio landing page."""
    if LANDING_PAGE_PATH.exists():
        return LANDING_PAGE_PATH.read_text(encoding="utf-8")

    return """
    <html>
      <body>
        <h1>Winter Injury Risk &amp; Equity Observatory</h1>
        <p>See API docs at <a href="/docs">/docs</a>.</p>
      </body>
    </html>
    """


@app.get("/api/info")
async def api_info():
    """Machine-readable service metadata."""
    return {
        "name": "Winter Injury Risk Observatory API",
        "version": "1.1.0",
        "status": "operational",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_service = DatabaseService()
    db_state = db_service.check_connection()
    if db_state is None:
        db_status = "disabled"
    else:
        db_status = "connected" if db_state else "disconnected"

    model_loaded = model_service is not None and model_service.model is not None

    health_status = {
        "status": "healthy" if model_loaded else "degraded",
        "model_loaded": model_loaded,
        "model_backend": model_service.model_backend if model_service else None,
        "model_version": model_service.model_version if model_service else None,
        "model_error": model_service.load_error if model_service else None,
        "database": db_status,
    }
    return health_status


def _to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.post("/predict", response_model=PredictionResponse)
async def predict(
    request: PredictionRequest,
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
):
    """
    Make a single prediction for injury risk.

    Returns risk probability and risk level classification.
    """
    del credentials
    if model_service is None or model_service.model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=model_service.load_error if model_service else "Model service unavailable",
        )

    try:
        features = _to_dict(request)
        df = pd.DataFrame([features])
        prediction = model_service.predict(df)

        return PredictionResponse(
            prediction=int(prediction["prediction"]),
            probability=float(prediction["probability"]),
            risk_level=prediction["risk_level"],
            features=features,
        )
    except Exception as exc:
        logger.error("Prediction error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {exc}",
        ) from exc


@app.post("/batch_predict")
async def batch_predict(
    request: BatchPredictionRequest,
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
):
    """
    Make batch predictions for multiple inputs.

    Returns list of predictions.
    """
    del credentials
    if model_service is None or model_service.model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=model_service.load_error if model_service else "Model service unavailable",
        )

    try:
        df = pd.DataFrame([_to_dict(item) for item in request.predictions])
        predictions = model_service.batch_predict(df)
        return {"count": len(predictions), "predictions": predictions}
    except Exception as exc:
        logger.error("Batch prediction error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction failed: {exc}",
        ) from exc


@app.get("/model/metrics")
async def get_model_metrics(
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
):
    """Get current model performance metrics."""
    del credentials
    if model_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model service not available",
        )

    return model_service.get_metrics()


@app.get("/model/info")
async def get_model_info():
    """Get model information."""
    if model_service is None:
        return {"status": "model_service_not_initialized"}
    if model_service.model is None:
        return {
            "status": "no_model_loaded",
            "backend": model_service.model_backend,
            "error": model_service.load_error,
        }

    return {
        "status": "ready",
        "model_version": model_service.model_version,
        "model_uri": model_service.model_uri,
        "loaded_at": model_service.loaded_at.isoformat()
        if model_service.loaded_at
        else None,
        "feature_count": len(model_service.feature_names)
        if model_service.feature_names
        else None,
        "backend": model_service.model_backend,
    }


@app.post("/model/reload")
async def reload_model(
    credentials: HTTPAuthorizationCredentials = Depends(verify_token),
):
    """Reload the model."""
    del credentials
    if model_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model service not available",
        )

    await model_service.load_model(force_reload=True)
    if model_service.model is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model reload failed: {model_service.load_error}",
        )
    return {"status": "success", "message": "Model reloaded successfully"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
        workers=int(os.getenv("API_WORKERS", 1)),
    )
