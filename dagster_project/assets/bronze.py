"""
Bronze Layer Assets

Raw data ingestion from external sources.
Assets are materialized as-is without transformation.
"""
from datetime import datetime, timedelta
from typing import Dict

import pandas as pd
from dagster import asset, AssetExecutionContext, Output, MetadataValue

from dagster_project.resources import (
    DatabaseResource,
    EnvironmentCanadaResource,
    OpenDataEdmontonResource,
)


@asset(
    group_name="bronze",
    description="Raw weather data from Environment Canada",
    compute_kind="python"
)
def weather_raw(
    context: AssetExecutionContext,
    environment_canada: EnvironmentCanadaResource,
    database: DatabaseResource
) -> Output[pd.DataFrame]:
    """
    Ingest raw weather data from Environment Canada.
    
    Fetches current hourly weather observations for Edmonton.
    """
    context.log.info("Fetching weather data from Environment Canada...")
    
    # Fetch current weather
    weather_obs = environment_canada.fetch_weather_data(
        station_id="CYEG"  # Edmonton International Airport
    )
    
    if weather_obs is None:
        context.log.warning("No weather data received")
        return Output(
            value=pd.DataFrame(),
            metadata={
                "num_records": 0,
                "status": "no_data"
            }
        )
    
    # Convert to DataFrame
    df = pd.DataFrame([weather_obs.dict()])
    
    # Store in database
    engine = database.get_engine()
    df.to_sql(
        "weather_raw",
        engine,
        if_exists="append",
        index=False,
        method="multi"
    )
    
    context.log.info(f"Ingested {len(df)} weather records")
    
    return Output(
        value=df,
        metadata={
            "num_records": len(df),
            "station_id": weather_obs.station_id,
            "temperature": f"{weather_obs.temperature}°C",
            "preview": MetadataValue.md(df.head().to_markdown()),
        }
    )


@asset(
    group_name="bronze",
    description="Raw injury/incident data from Open Data Edmonton",
    compute_kind="python"
)
def injuries_raw(
    context: AssetExecutionContext,
    open_data_edmonton: OpenDataEdmontonResource,
    database: DatabaseResource
) -> Output[pd.DataFrame]:
    """
    Ingest raw injury data from Open Data Edmonton.
    
    Fetches injury records from the past 24 hours.
    """
    context.log.info("Fetching injury data from Open Data Edmonton...")
    
    # Fetch recent injuries (last 24 hours)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    df = open_data_edmonton.fetch_injury_data(
        start_date=start_date,
        end_date=end_date
    )
    
    if df.empty:
        context.log.warning("No injury data received")
        return Output(
            value=df,
            metadata={
                "num_records": 0,
                "status": "no_data"
            }
        )
    
    # Store in database
    engine = database.get_engine()
    df.to_sql(
        "injuries_raw",
        engine,
        if_exists="append",
        index=False,
        method="multi"
    )
    
    context.log.info(f"Ingested {len(df)} injury records")
    
    return Output(
        value=df,
        metadata={
            "num_records": len(df),
            "date_range": f"{start_date.date()} to {end_date.date()}",
            "injury_types": df["incident_type"].value_counts().to_dict() if "incident_type" in df else {},
            "preview": MetadataValue.md(df.head().to_markdown()),
        }
    )


@asset(
    group_name="bronze",
    description="Raw demographic and socioeconomic data",
    compute_kind="python"
)
def demographics_raw(
    context: AssetExecutionContext,
    open_data_edmonton: OpenDataEdmontonResource,
    database: DatabaseResource
) -> Output[pd.DataFrame]:
    """
    Ingest raw demographic data from Open Data Edmonton.
    
    This is typically refreshed monthly or quarterly.
    """
    context.log.info("Fetching demographics data from Open Data Edmonton...")
    
    df = open_data_edmonton.fetch_demographics_data()
    
    if df.empty:
        context.log.warning("No demographics data received")
        return Output(
            value=df,
            metadata={
                "num_records": 0,
                "status": "no_data"
            }
        )
    
    # Store in database (replace existing)
    engine = database.get_engine()
    df.to_sql(
        "demographics_raw",
        engine,
        if_exists="replace",
        index=False,
        method="multi"
    )
    
    context.log.info(f"Ingested {len(df)} demographic records")
    
    return Output(
        value=df,
        metadata={
            "num_neighborhoods": len(df),
            "total_population": int(df["population"].sum()) if "population" in df else 0,
            "preview": MetadataValue.md(df.head().to_markdown()),
        }
    )
