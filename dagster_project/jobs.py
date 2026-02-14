"""Dagster Jobs"""
from dagster import define_asset_job, AssetSelection

# Training job
training_job = define_asset_job(
    name="model_training_job",
    selection=AssetSelection.groups("gold"),
    description="Train ML model on latest data"
)

# Batch prediction job
batch_prediction_job = define_asset_job(
    name="batch_prediction_job",
    selection=AssetSelection.all(),
    description="Generate batch predictions"
)
