"""
Gold Layer Assets

Feature-engineered datasets ready for machine learning and analytics.
"""
import pandas as pd
from dagster import asset, AssetExecutionContext, AssetIn, Output

from dagster_project.resources import DatabaseResource


@asset(
    group_name="gold",
    ins={"weather_cleaned": AssetIn(), "demographics_processed": AssetIn()},
    description="Engineered weather features for ML",
    compute_kind="python"
)
def weather_features(
    context: AssetExecutionContext,
    database: DatabaseResource,
    weather_cleaned: pd.DataFrame,
    demographics_processed: pd.DataFrame
) -> Output[pd.DataFrame]:
    """Create engineered weather features"""
    df = weather_cleaned.copy()
    
    # Time-based features
    df["hour"] = pd.to_datetime(df["observation_time"]).dt.hour
    df["day_of_week"] = pd.to_datetime(df["observation_time"]).dt.dayofweek
    df["month"] = pd.to_datetime(df["observation_time"]).dt.month
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    
    # Lag features (previous hours)
    df = df.sort_values("observation_time")
    for lag in [1, 3, 6, 12, 24]:
        df[f"temp_lag_{lag}h"] = df.groupby("station_id")["temperature"].shift(lag)
        df[f"precip_lag_{lag}h"] = df.groupby("station_id")["precipitation"].shift(lag)
    
    # Rolling statistics
    df["temp_rolling_mean_24h"] = df.groupby("station_id")["temperature"].rolling(24, min_periods=1).mean().reset_index(0, drop=True)
    df["temp_rolling_std_24h"] = df.groupby("station_id")["temperature"].rolling(24, min_periods=1).std().reset_index(0, drop=True)
    
    # Freeze-thaw indicator
    df["freeze_thaw_risk"] = ((df["temperature"] > -5) & (df["temperature"] < 2)).astype(int)
    
    engine = database.get_engine()
    df.to_sql("weather_features", engine, if_exists="replace", index=False)
    
    return Output(value=df, metadata={"num_records": len(df), "num_features": len(df.columns)})


@asset(
    group_name="gold",
    ins={"injuries_cleaned": AssetIn(), "weather_features": AssetIn()},
    description="Injury aggregates with weather context",
    compute_kind="python"
)
def injury_aggregates(
    context: AssetExecutionContext,
    database: DatabaseResource,
    injuries_cleaned: pd.DataFrame,
    weather_features: pd.DataFrame
) -> Output[pd.DataFrame]:
    """Create injury aggregates"""
    df = injuries_cleaned.copy()
    
    # Daily aggregates by neighborhood
    df["date"] = pd.to_datetime(df["incident_date"]).dt.date
    daily_agg = df.groupby(["date", "neighborhood"]).agg({
        "incident_id": "count",
        "severity": "mean"
    }).rename(columns={"incident_id": "injury_count", "severity": "avg_severity"}).reset_index()
    
    # High risk flag (>75th percentile)
    daily_agg["high_risk"] = (daily_agg["injury_count"] > daily_agg["injury_count"].quantile(0.75)).astype(int)
    
    engine = database.get_engine()
    daily_agg.to_sql("injury_aggregates", engine, if_exists="replace", index=False)
    
    return Output(value=daily_agg, metadata={"num_records": len(daily_agg)})


@asset(
    group_name="gold",
    ins={"weather_features": AssetIn(), "injury_aggregates": AssetIn(), "demographics_processed": AssetIn()},
    description="Final ML training dataset",
    compute_kind="python"
)
def model_training_data(
    context: AssetExecutionContext,
    database: DatabaseResource,
    weather_features: pd.DataFrame,
    injury_aggregates: pd.DataFrame,
    demographics_processed: pd.DataFrame
) -> Output[pd.DataFrame]:
    """Create final training dataset"""
    # Merge all data
    weather_features["date"] = pd.to_datetime(weather_features["observation_time"]).dt.date
    df = injury_aggregates.merge(weather_features, on="date", how="left")
    df = df.merge(demographics_processed, on="neighborhood", how="left")
    
    # Select features
    feature_cols = [c for c in df.columns if c not in ["incident_id", "date", "observation_time"]]
    df = df[feature_cols].dropna()
    
    engine = database.get_engine()
    df.to_sql("model_training_data", engine, if_exists="replace", index=False)
    
    context.log.info(f"Created training data with {len(df)} records and {len(df.columns)} features")
    
    return Output(value=df, metadata={"num_records": len(df), "num_features": len(df.columns)})
