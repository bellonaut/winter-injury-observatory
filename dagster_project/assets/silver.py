"""
Silver Layer Assets

Cleaned and validated data with standardization applied.
"""
import pandas as pd
from dagster import asset, AssetExecutionContext, AssetIn, Output, MetadataValue

from dagster_project.resources import DatabaseResource


@asset(
    group_name="silver",
    ins={"weather_raw": AssetIn()},
    description="Cleaned and validated weather data",
    compute_kind="python"
)
def weather_cleaned(
    context: AssetExecutionContext,
    database: DatabaseResource,
    weather_raw: pd.DataFrame
) -> Output[pd.DataFrame]:
    """Clean and validate weather data"""
    context.log.info(f"Cleaning {len(weather_raw)} weather records...")
    
    df = weather_raw.copy()
    
    # Remove duplicates
    df = df.drop_duplicates(subset=["station_id", "observation_time"])
    
    # Validate temperature range (-50 to 40 °C for Edmonton)
    df = df[(df["temperature"] >= -50) & (df["temperature"] <= 40)]
    
    # Fill missing values with interpolation
    numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns
    df[numeric_cols] = df[numeric_cols].interpolate(method="linear", limit=3)
    
    # Store in database
    engine = database.get_engine()
    df.to_sql("weather_cleaned", engine, if_exists="append", index=False)
    
    return Output(
        value=df,
        metadata={
            "num_records": len(df),
            "dropped_records": len(weather_raw) - len(df),
            "preview": MetadataValue.md(df.head().to_markdown()),
        }
    )


@asset(
    group_name="silver",
    ins={"injuries_raw": AssetIn()},
    description="Cleaned and standardized injury data",
    compute_kind="python"
)
def injuries_cleaned(
    context: AssetExecutionContext,
    database: DatabaseResource,
    injuries_raw: pd.DataFrame
) -> Output[pd.DataFrame]:
    """Clean and standardize injury data"""
    context.log.info(f"Cleaning {len(injuries_raw)} injury records...")
    
    df = injuries_raw.copy()
    
    # Remove duplicates
    df = df.drop_duplicates(subset=["incident_id"])
    
    # Standardize injury types
    injury_type_mapping = {
        "fall": "slip_fall",
        "slip": "slip_fall",
        "motor vehicle": "vehicle_collision",
        "vehicle": "vehicle_collision",
    }
    if "incident_type" in df.columns:
        df["incident_type"] = df["incident_type"].str.lower().replace(injury_type_mapping)
    
    # Validate severity (1-5)
    if "severity" in df.columns:
        df = df[(df["severity"] >= 1) & (df["severity"] <= 5)]
    
    # Store in database
    engine = database.get_engine()
    df.to_sql("injuries_cleaned", engine, if_exists="append", index=False)
    
    return Output(
        value=df,
        metadata={
            "num_records": len(df),
            "dropped_records": len(injuries_raw) - len(df),
            "injury_types": df["incident_type"].value_counts().to_dict() if "incident_type" in df else {},
        }
    )


@asset(
    group_name="silver",
    ins={"demographics_raw": AssetIn()},
    description="Processed demographic data with derived features",
    compute_kind="python"
)
def demographics_processed(
    context: AssetExecutionContext,
    database: DatabaseResource,
    demographics_raw: pd.DataFrame
) -> Output[pd.DataFrame]:
    """Process demographic data"""
    context.log.info(f"Processing {len(demographics_raw)} demographic records...")
    
    df = demographics_raw.copy()
    
    # Calculate derived features
    if "population" in df.columns and "median_income" in df.columns:
        df["income_per_capita"] = df["median_income"] / df["population"]
    
    # Normalize indices to 0-1 range
    for col in ["ses_index", "infrastructure_quality", "pop_density"]:
        if col in df.columns:
            df[f"{col}_normalized"] = (df[col] - df[col].min()) / (df[col].max() - df[col].min())
    
    # Store in database
    engine = database.get_engine()
    df.to_sql("demographics_processed", engine, if_exists="replace", index=False)
    
    return Output(
        value=df,
        metadata={
            "num_neighborhoods": len(df),
            "preview": MetadataValue.md(df.head().to_markdown()),
        }
    )
