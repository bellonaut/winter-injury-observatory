"""Dagster Schedules"""
from dagster import ScheduleDefinition, DefaultScheduleStatus

# Weather ingestion every hour
weather_ingestion_schedule = ScheduleDefinition(
    job_name="weather_ingestion_job",
    cron_schedule="0 * * * *",
    default_status=DefaultScheduleStatus.RUNNING,
)

# Feature engineering daily at 3 AM
feature_engineering_schedule = ScheduleDefinition(
    job_name="feature_engineering_job",
    cron_schedule="0 3 * * *",
    default_status=DefaultScheduleStatus.RUNNING,
)

# Model training weekly on Sundays at 4 AM
model_training_schedule = ScheduleDefinition(
    job_name="model_training_job",
    cron_schedule="0 4 * * 0",
    default_status=DefaultScheduleStatus.RUNNING,
)
