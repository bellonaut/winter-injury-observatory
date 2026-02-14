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
        artifact_path = self._resolve_local_artifact_path()
        if artifact_path is None:
            raise FileNotFoundError(
                f"Local model artifact not found. Checked MODEL_ARTIFACT_PATH='{self.model_artifact_path}' "
                "and common artifact locations under ./artifacts and /app/artifacts. "
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

    def _resolve_local_artifact_path(self) -> Optional[Path]:
        configured = Path(self.model_artifact_path)
        candidates: List[Path] = []

        # Primary configured value (relative to cwd or absolute).
        candidates.append(configured)

        # If configured as filename-only, also check artifacts directory.
        if configured.parent in (Path("."), Path("")):
            candidates.append(Path("artifacts") / configured.name)

        # Standard repository/container defaults.
        candidates.append(Path("artifacts/demo_model.joblib"))
        candidates.append(Path("/app/artifacts/demo_model.joblib"))

        seen = set()
        for candidate in candidates:
            resolved = candidate.expanduser().resolve()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            if resolved.exists():
                if str(resolved) != str(configured.expanduser().resolve()):
                    logger.warning(
                        "Configured MODEL_ARTIFACT_PATH '%s' not found; using '%s' instead",
                        self.model_artifact_path,
                        resolved,
                    )
                return resolved

        return None

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

    @staticmethod
    def _hazard_score(row: pd.Series) -> float:
        """Domain-informed hazard score to stabilize model extrapolations."""
        temperature = float(row.get("temperature", 0.0))
        wind_chill = float(row.get("wind_chill", temperature))
        precipitation = float(row.get("precipitation", 0.0))
        snow_depth = float(row.get("snow_depth", 0.0))
        hour = int(row.get("hour", 12))
        ses_index = float(row.get("ses_index", 0.5))
        infrastructure_quality = float(row.get("infrastructure_quality", 0.7))

        score = 0.02

        # Freeze-thaw and deep-freeze risk bands.
        if -15 <= temperature <= -2:
            score += 0.28
        elif -25 <= temperature < -15:
            score += 0.16
        elif temperature > 6:
            score -= 0.10

        # Wet icy surfaces are more dangerous near freezing than warm rain.
        if precipitation > 0.5 and temperature < 2:
            score += 0.20
        elif precipitation > 0.5 and temperature >= 6:
            score += 0.04

        if snow_depth >= 10:
            score += 0.12
        elif snow_depth <= 3:
            score -= 0.04

        if wind_chill < -20:
            score += 0.10

        if hour in {7, 8, 17, 18}:
            score += 0.08

        if infrastructure_quality < 0.6:
            score += 0.08
        if ses_index < 0.5:
            score += 0.04

        return max(0.01, min(0.95, score))

    def _apply_domain_guardrails(self, row: pd.Series, model_probability: float) -> float:
        """Blend model output with domain constraints for physically plausible risk."""
        temperature = float(row.get("temperature", 0.0))
        wind_chill = float(row.get("wind_chill", temperature))
        precipitation = float(row.get("precipitation", 0.0))
        snow_depth = float(row.get("snow_depth", 0.0))

        hazard = self._hazard_score(row)
        blended = 0.65 * float(model_probability) + 0.35 * hazard

        # Warm, low-snow conditions should not produce high winter injury risk.
        if temperature >= 10 and wind_chill >= 0 and snow_depth < 3:
            blended = min(blended, 0.18)
        elif temperature >= 6 and wind_chill >= -1 and snow_depth < 8:
            blended = min(blended, 0.32)
        elif temperature >= 3 and precipitation <= 1.5 and snow_depth < 6:
            blended = min(blended, 0.42)

        return max(0.0, min(1.0, blended))

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

        model_prediction = int(self.model.predict(df)[0])
        raw_probability = self._predict_probability(df)[0]
        probability = self._apply_domain_guardrails(df.iloc[0], raw_probability)
        prediction = int(probability >= 0.5)
        return {
            "prediction": prediction,
            "probability": probability,
            "risk_level": self._risk_level(probability),
            "raw_prediction": model_prediction,
            "raw_probability": float(raw_probability),
        }

    def batch_predict(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Make batch predictions."""
        if self.model is None:
            raise ValueError(self.load_error or "Model not loaded")

        raw_predictions = self.model.predict(df)
        raw_probabilities = self._predict_probability(df)

        results: List[Dict[str, Any]] = []
        for idx, (pred, prob) in enumerate(zip(raw_predictions, raw_probabilities)):
            adjusted_prob = self._apply_domain_guardrails(df.iloc[idx], float(prob))
            results.append(
                {
                    "prediction": int(adjusted_prob >= 0.5),
                    "probability": float(adjusted_prob),
                    "risk_level": self._risk_level(float(adjusted_prob)),
                    "raw_prediction": int(pred),
                    "raw_probability": float(prob),
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
