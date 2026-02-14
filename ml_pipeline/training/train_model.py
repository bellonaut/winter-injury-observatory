"""
XGBoost Training Pipeline with MLflow Tracking

Trains injury risk prediction model with comprehensive logging.
"""
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix
)
import shap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WinterInjuryModel:
    """Winter injury risk prediction model"""
    
    def __init__(
        self,
        experiment_name: str = "winter-injury-risk",
        model_type: str = "binary"  # binary or multiclass
    ):
        self.experiment_name = experiment_name
        self.model_type = model_type
        self.model = None
        self.feature_names = None
        
        # Setup MLflow
        mlflow.set_experiment(experiment_name)
    
    def prepare_data(
        self,
        df: pd.DataFrame,
        target_col: str = "high_risk",
        test_size: float = 0.2
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """Prepare data for training"""
        # Separate features and target
        feature_cols = [c for c in df.columns if c not in [target_col, "injury_count", "neighborhood"]]
        X = df[feature_cols]
        y = df[target_col]
        
        self.feature_names = feature_cols
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        logger.info(f"Training set: {len(X_train)} samples")
        logger.info(f"Test set: {len(X_test)} samples")
        logger.info(f"Features: {len(feature_cols)}")
        
        return X_train, X_test, y_train, y_test
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        params: Dict = None
    ):
        """Train XGBoost model"""
        if params is None:
            params = {
                "objective": "binary:logistic" if self.model_type == "binary" else "multi:softmax",
                "max_depth": 6,
                "learning_rate": 0.1,
                "n_estimators": 100,
                "min_child_weight": 1,
                "gamma": 0,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "random_state": 42,
            }
        
        with mlflow.start_run(run_name=f"xgboost_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            # Log parameters
            mlflow.log_params(params)
            mlflow.log_param("model_type", self.model_type)
            mlflow.log_param("num_features", len(self.feature_names))
            mlflow.log_param("num_train_samples", len(X_train))
            
            # Train model
            self.model = xgb.XGBClassifier(**params)
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_train, y_train)],
                verbose=False
            )
            
            # Log model
            mlflow.xgboost.log_model(
                self.model,
                "model",
                input_example=X_train.head(5)
            )
            
            logger.info("Model training completed")
    
    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict:
        """Evaluate model and log metrics"""
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)[:, 1] if self.model_type == "binary" else None
        
        # Calculate metrics
        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, average="binary" if self.model_type == "binary" else "weighted"),
            "recall": recall_score(y_test, y_pred, average="binary" if self.model_type == "binary" else "weighted"),
            "f1": f1_score(y_test, y_pred, average="binary" if self.model_type == "binary" else "weighted"),
        }
        
        if y_proba is not None:
            metrics["roc_auc"] = roc_auc_score(y_test, y_proba)
        
        # Log metrics
        for metric_name, metric_value in metrics.items():
            mlflow.log_metric(metric_name, metric_value)
        
        # Log classification report
        report = classification_report(y_test, y_pred, output_dict=True)
        mlflow.log_dict(report, "classification_report.json")
        
        # Log confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        mlflow.log_dict({"confusion_matrix": cm.tolist()}, "confusion_matrix.json")
        
        logger.info(f"Model evaluation - Accuracy: {metrics['accuracy']:.4f}, F1: {metrics['f1']:.4f}")
        
        return metrics
    
    def feature_importance(self, X_train: pd.DataFrame):
        """Calculate and log feature importance"""
        importance = self.model.feature_importances_
        feature_importance_df = pd.DataFrame({
            "feature": self.feature_names,
            "importance": importance
        }).sort_values("importance", ascending=False)
        
        # Log as artifact
        feature_importance_df.to_csv("feature_importance.csv", index=False)
        mlflow.log_artifact("feature_importance.csv")
        
        # Log top 10 features as params
        for idx, row in feature_importance_df.head(10).iterrows():
            mlflow.log_param(f"top_feature_{idx+1}", row["feature"])
        
        logger.info("Top 5 features:")
        for idx, row in feature_importance_df.head(5).iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")
    
    def shap_analysis(self, X_train: pd.DataFrame):
        """Perform SHAP analysis"""
        try:
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(X_train.sample(min(1000, len(X_train))))
            
            # Log SHAP values as artifact
            shap_df = pd.DataFrame(shap_values, columns=self.feature_names)
            shap_df.to_csv("shap_values.csv", index=False)
            mlflow.log_artifact("shap_values.csv")
            
            logger.info("SHAP analysis completed")
        except Exception as e:
            logger.warning(f"SHAP analysis failed: {e}")


def train_model(config_path: str = None):
    """Main training function"""
    # Load config
    if config_path:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    
    # Load data from database
    import os
    from sqlalchemy import create_engine
    
    engine = create_engine(os.getenv("DATABASE_URL"))
    df = pd.read_sql("SELECT * FROM model_training_data", engine)
    
    logger.info(f"Loaded {len(df)} records for training")
    
    # Initialize model
    model = WinterInjuryModel()
    
    # Prepare data
    X_train, X_test, y_train, y_test = model.prepare_data(df)
    
    # Train
    model.train(X_train, y_train, params=config.get("model_params"))
    
    # Evaluate
    metrics = model.evaluate(X_test, y_test)
    
    # Feature importance
    model.feature_importance(X_train)
    
    # SHAP analysis
    model.shap_analysis(X_train)
    
    return metrics


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, help="Path to config file")
    args = parser.parse_args()
    
    metrics = train_model(config_path=args.config)
    print(f"\nTraining completed. Final metrics: {metrics}")
