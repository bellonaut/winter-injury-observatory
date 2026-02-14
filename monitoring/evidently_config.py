"""
Evidently Monitoring Configuration

Configures data drift, model performance, and data quality monitoring.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import (
    DataDriftPreset,
    DataQualityPreset,
    TargetDriftPreset,
)
from evidently.metrics import (
    ColumnDriftMetric,
    DatasetDriftMetric,
    DatasetMissingValuesMetric,
)

logger = logging.getLogger(__name__)


class Evidently Monitor:
    """Evidently monitoring for ML model"""
    
    def __init__(
        self,
        reference_data: pd.DataFrame,
        column_mapping: Optional[ColumnMapping] = None
    ):
        self.reference_data = reference_data
        self.column_mapping = column_mapping or ColumnMapping()
        
    def generate_data_drift_report(
        self,
        current_data: pd.DataFrame,
        output_path: Optional[Path] = None
    ) -> Dict:
        """Generate data drift report"""
        report = Report(metrics=[
            DataDriftPreset(),
            DatasetDriftMetric(),
        ])
        
        report.run(
            reference_data=self.reference_data,
            current_data=current_data,
            column_mapping=self.column_mapping
        )
        
        if output_path:
            report.save_html(str(output_path))
            logger.info(f"Data drift report saved to {output_path}")
        
        # Extract metrics
        results = report.as_dict()
        return {
            "dataset_drift": results["metrics"][0]["result"]["dataset_drift"],
            "drift_share": results["metrics"][0]["result"]["drift_share"],
            "n_drifted_features": results["metrics"][0]["result"]["number_of_drifted_columns"],
        }
    
    def generate_data_quality_report(
        self,
        current_data: pd.DataFrame,
        output_path: Optional[Path] = None
    ) -> Dict:
        """Generate data quality report"""
        report = Report(metrics=[
            DataQualityPreset(),
            DatasetMissingValuesMetric(),
        ])
        
        report.run(
            reference_data=self.reference_data,
            current_data=current_data,
            column_mapping=self.column_mapping
        )
        
        if output_path:
            report.save_html(str(output_path))
            logger.info(f"Data quality report saved to {output_path}")
        
        results = report.as_dict()
        return {
            "n_missing_values": results["metrics"][1]["result"]["current"]["number_of_missing_values"],
            "pct_missing_values": results["metrics"][1]["result"]["current"]["share_of_missing_values"],
        }
    
    def check_drift_alert(
        self,
        current_data: pd.DataFrame,
        threshold: float = 0.3
    ) -> bool:
        """Check if drift exceeds threshold"""
        drift_report = self.generate_data_drift_report(current_data)
        return drift_report["drift_share"] > threshold
