"""
Build a deterministic demo model artifact for local/Render inference.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from synthetic_data.generate_data import WinterInjuryDataGenerator


FEATURE_COLUMNS = [
    "temperature",
    "wind_speed",
    "wind_chill",
    "precipitation",
    "snow_depth",
    "hour",
    "day_of_week",
    "month",
    "neighborhood",
    "ses_index",
    "infrastructure_quality",
]


def build_training_data(days: int, seed: int) -> pd.DataFrame:
    """Generate synthetic feature rows and binary risk target."""
    generator = WinterInjuryDataGenerator(random_seed=seed)
    weather_df = generator.generate_weather_data(
        start_date=datetime(2024, 11, 1),
        days=days,
    )

    rng = np.random.RandomState(seed)
    rows: List[Dict] = []
    for _, weather in weather_df.iterrows():
        timestamp = weather["timestamp"]
        hour = int(timestamp.hour)
        day_of_week = int(timestamp.dayofweek)
        month = int(timestamp.month)

        for neighborhood, meta in generator.NEIGHBORHOODS.items():
            risk = generator.calculate_injury_risk(
                weather=weather,
                hour=hour,
                day_of_week=day_of_week,
                neighborhood=neighborhood,
            )
            injury_count = int(rng.poisson(max(risk * 1000.0, 0.0)))
            rows.append(
                {
                    "temperature": float(weather["temperature"]),
                    "wind_speed": float(weather["wind_speed"]),
                    "wind_chill": float(weather["wind_chill"]),
                    "precipitation": float(weather["precipitation"]),
                    "snow_depth": float(weather["snow_depth"]),
                    "hour": hour,
                    "day_of_week": day_of_week,
                    "month": month,
                    "neighborhood": neighborhood,
                    "ses_index": float(meta["ses_index"]),
                    "infrastructure_quality": float(meta["infrastructure_quality"]),
                    "injury_count": injury_count,
                }
            )

    df = pd.DataFrame(rows)
    threshold = float(df["injury_count"].quantile(0.75))
    df["high_risk"] = (df["injury_count"] > threshold).astype(int)
    return df


def train_pipeline(df: pd.DataFrame, seed: int) -> tuple[Pipeline, Dict[str, float]]:
    """Train a lightweight probabilistic classifier pipeline."""
    X = df[FEATURE_COLUMNS]
    y = df["high_risk"]

    numeric_columns = [c for c in FEATURE_COLUMNS if c != "neighborhood"]
    categorical_columns = ["neighborhood"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_columns),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_columns),
        ]
    )

    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=seed,
    )
    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", model),
        ]
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=seed
    )

    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
    }
    return pipeline, metrics


def main():
    parser = argparse.ArgumentParser(description="Build local demo model artifact.")
    parser.add_argument("--days", type=int, default=120, help="Synthetic data days.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts",
        help="Output directory for model and metadata.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = build_training_data(days=args.days, seed=args.seed)
    pipeline, metrics = train_pipeline(df=df, seed=args.seed)

    model_path = output_dir / "demo_model.joblib"
    meta_path = output_dir / "demo_model_meta.json"

    joblib.dump(pipeline, model_path)
    metadata = {
        "model_version": "local-demo-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sklearn_version": sklearn.__version__,
        "seed": args.seed,
        "days": args.days,
        "feature_columns": FEATURE_COLUMNS,
        "target_column": "high_risk",
        "metrics": metrics,
        "notes": "Synthetic-data portfolio model. Not for clinical/public safety use.",
    }
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Model artifact: {model_path}")
    print(f"Metadata: {meta_path}")
    print("Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value:.4f}")


if __name__ == "__main__":
    main()
