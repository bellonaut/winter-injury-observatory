"""Service layer for API."""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


class ModelService:
    """ML model service supporting local artifacts and MLflow."""

    def __init__(self):
        self.model: Optional[Any] = None
        self.model_version: Optional[str] = None
        self.model_uri: Optional[str] = None
        self.feature_names: Optional[List[str]] = None
        self.loaded_at: Optional[datetime] = None
        self.load_error: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

        self.model_backend = os.getenv("MODEL_BACKEND", "local").strip().lower()
        self.model_artifact_path = os.getenv(
            "MODEL_ARTIFACT_PATH", "artifacts/demo_model.joblib"
        ).strip()

    async def load_model(self, force_reload: bool = False):
        """Load model using selected backend."""
        if self.model is not None and not force_reload:
            logger.info("Model already loaded")
            return

        self.model = None
        self.load_error = None
        backend = self.model_backend

        if backend not in {"local", "mlflow"}:
            logger.warning("Unknown MODEL_BACKEND '%s'; defaulting to local", backend)
            backend = "local"

        if backend == "mlflow":
            try:
                self._load_mlflow_model()
                return
            except Exception as mlflow_error:
                logger.warning(
                    "MLflow model load failed, trying local fallback: %s", mlflow_error
                )
                try:
                    self._load_local_model()
                    self.model_backend = "local"
                    return
                except Exception as local_error:
                    self.load_error = (
                        f"mlflow error: {mlflow_error}; local fallback error: {local_error}"
                    )
                    logger.error("Model load failed: %s", self.load_error)
                    return

        try:
            self._load_local_model()
        except Exception as local_error:
            self.load_error = str(local_error)
            logger.error("Model load failed: %s", self.load_error)

    def _load_local_model(self):
        artifact_path = Path(self.model_artifact_path).resolve()
        if not artifact_path.exists():
            raise FileNotFoundError(
                f"Local model artifact not found at '{artifact_path}'. "
                "Build it with: python scripts/build_demo_model.py"
            )

        self.model = joblib.load(artifact_path)
        self.model_uri = str(artifact_path)
        self.model_version = "local-demo"
        self.loaded_at = datetime.now(timezone.utc)

        metadata_path = artifact_path.with_name("demo_model_meta.json")
        if metadata_path.exists():
            self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.feature_names = self.metadata.get("feature_columns")
            self.model_version = self.metadata.get("model_version", self.model_version)
        else:
            self.metadata = {}
            self.feature_names = None

        logger.info("Loaded local model artifact from %s", artifact_path)

    def _load_mlflow_model(self):
        try:
            import mlflow
            import mlflow.xgboost
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "MLflow backend requested but mlflow/xgboost dependencies are not installed"
            ) from exc

        mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(mlflow_tracking_uri)

        model_name = os.getenv("MODEL_NAME", "winter-injury-risk")
        model_version = os.getenv("MODEL_VERSION", "production")
        if model_version.lower() == "production":
            model_uri = f"models:/{model_name}/Production"
        else:
            model_uri = f"models:/{model_name}/{model_version}"

        self.model = mlflow.xgboost.load_model(model_uri)
        self.model_version = model_version
        self.model_uri = model_uri
        self.loaded_at = datetime.now(timezone.utc)
        self.feature_names = None
        self.metadata = {}
        logger.info("Loaded MLflow model from %s", model_uri)

    @staticmethod
    def _risk_level(probability: float) -> str:
        if probability < 0.3:
            return "low"
        if probability < 0.6:
            return "medium"
        if probability < 0.8:
            return "high"
        return "critical"

    def _predict_probability(self, df: pd.DataFrame) -> List[float]:
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(df)
            if getattr(probabilities, "ndim", 1) == 1:
                return [float(p) for p in probabilities]
            return [float(p[1]) for p in probabilities]

        predictions = self.model.predict(df)
        return [float(pred) for pred in predictions]

    def predict(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Make single prediction."""
        if self.model is None:
            raise ValueError(self.load_error or "Model not loaded")

        prediction = int(self.model.predict(df)[0])
        probability = self._predict_probability(df)[0]
        return {
            "prediction": prediction,
            "probability": probability,
            "risk_level": self._risk_level(probability),
        }

    def batch_predict(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Make batch predictions."""
        if self.model is None:
            raise ValueError(self.load_error or "Model not loaded")

        predictions = self.model.predict(df)
        probabilities = self._predict_probability(df)

        results: List[Dict[str, Any]] = []
        for pred, prob in zip(predictions, probabilities):
            results.append(
                {
                    "prediction": int(pred),
                    "probability": float(prob),
                    "risk_level": self._risk_level(float(prob)),
                }
            )
        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get available model metrics."""
        if self.model_backend == "mlflow":
            try:
                import mlflow

                client = mlflow.tracking.MlflowClient()
                runs = client.search_runs(
                    experiment_ids=["0"], order_by=["start_time DESC"], max_results=1
                )
                if runs:
                    run = runs[0]
                    return {
                        "backend": "mlflow",
                        "model_uri": self.model_uri,
                        "model_version": self.model_version,
                        "loaded_at": self.loaded_at.isoformat()
                        if self.loaded_at
                        else None,
                        "metrics": run.data.metrics,
                    }
            except Exception as exc:
                logger.warning("Unable to fetch MLflow metrics: %s", exc)

        return {
            "backend": self.model_backend,
            "model_uri": self.model_uri,
            "model_version": self.model_version,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "metrics": self.metadata.get("metrics", {}),
            "load_error": self.load_error,
        }


class DatabaseService:
    """Database service with optional DB support."""

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.engine = create_engine(self.database_url) if self.database_url else None

    @property
    def enabled(self) -> bool:
        return self.engine is not None

    def check_connection(self) -> Optional[bool]:
        """Check database connection status."""
        if self.engine is None:
            return None

        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_recent_predictions(self, limit: int = 100) -> pd.DataFrame:
        """Get recent predictions from database."""
        if self.engine is None:
            raise ValueError("DATABASE_URL is not configured")

        query = (
            "SELECT * FROM predictions "
            "ORDER BY timestamp DESC "
            f"LIMIT {int(limit)}"
        )
        return pd.read_sql(query, self.engine)
