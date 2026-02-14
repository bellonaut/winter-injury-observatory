"""
Dagster Definitions

Main entry point for the Dagster project defining all assets, resources,
jobs, schedules, and sensors.
"""
from dagster import Definitions, load_assets_from_modules

from dagster_project.assets import bronze, silver, gold
from dagster_project.resources import get_resources
from dagster_project.jobs import training_job, batch_prediction_job
from dagster_project.schedules import (
    weather_ingestion_schedule,
    feature_engineering_schedule,
    model_training_schedule,
)

# Load all assets from modules
bronze_assets = load_assets_from_modules([bronze])
silver_assets = load_assets_from_modules([silver])
gold_assets = load_assets_from_modules([gold])

# Combine all assets
all_assets = [*bronze_assets, *silver_assets, *gold_assets]

# Define Dagster instance
defs = Definitions(
    assets=all_assets,
    resources=get_resources(),
    jobs=[training_job, batch_prediction_job],
    schedules=[
        weather_ingestion_schedule,
        feature_engineering_schedule,
        model_training_schedule,
    ],
)
