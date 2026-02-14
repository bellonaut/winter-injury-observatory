"""
Database Initialization Script

Creates all necessary tables and indexes.
"""
import os
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize database schema"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    engine = create_engine(database_url)
    
    # SQL schema
    schema = """
    -- Enable TimescaleDB extension
    CREATE EXTENSION IF NOT EXISTS timescaledb;
    
    -- Weather raw data table
    CREATE TABLE IF NOT EXISTS weather_raw (
        id SERIAL PRIMARY KEY,
        station_id VARCHAR(50) NOT NULL,
        observation_time TIMESTAMPTZ NOT NULL,
        temperature FLOAT,
        dewpoint FLOAT,
        wind_speed FLOAT,
        wind_direction VARCHAR(10),
        wind_gust FLOAT,
        visibility FLOAT,
        pressure FLOAT,
        humidity FLOAT,
        condition VARCHAR(50),
        precipitation_1h FLOAT,
        precipitation_24h FLOAT,
        snow_depth FLOAT,
        wind_chill FLOAT,
        humidex FLOAT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(station_id, observation_time)
    );
    
    -- Convert to hypertable
    SELECT create_hypertable('weather_raw', 'observation_time', if_not_exists => TRUE);
    
    -- Injuries raw data table
    CREATE TABLE IF NOT EXISTS injuries_raw (
        id SERIAL PRIMARY KEY,
        incident_id VARCHAR(100) UNIQUE NOT NULL,
        incident_date TIMESTAMPTZ NOT NULL,
        incident_type VARCHAR(50),
        location_description TEXT,
        latitude FLOAT,
        longitude FLOAT,
        neighborhood VARCHAR(100),
        severity INTEGER,
        age_group VARCHAR(20),
        weather_condition VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Demographics table
    CREATE TABLE IF NOT EXISTS demographics_raw (
        id SERIAL PRIMARY KEY,
        neighborhood VARCHAR(100) UNIQUE NOT NULL,
        population INTEGER,
        median_age INTEGER,
        median_income INTEGER,
        ses_index FLOAT,
        infrastructure_quality FLOAT,
        pop_density FLOAT,
        pct_seniors FLOAT,
        pct_children FLOAT,
        sidewalk_coverage FLOAT,
        lighting_quality FLOAT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Weather cleaned table
    CREATE TABLE IF NOT EXISTS weather_cleaned (
        id SERIAL PRIMARY KEY,
        station_id VARCHAR(50) NOT NULL,
        observation_time TIMESTAMPTZ NOT NULL,
        temperature FLOAT,
        wind_speed FLOAT,
        wind_chill FLOAT,
        precipitation FLOAT,
        snow_depth FLOAT,
        humidity FLOAT,
        pressure FLOAT,
        visibility FLOAT,
        condition VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(station_id, observation_time)
    );
    
    -- Injuries cleaned table
    CREATE TABLE IF NOT EXISTS injuries_cleaned (
        id SERIAL PRIMARY KEY,
        incident_id VARCHAR(100) UNIQUE NOT NULL,
        incident_date TIMESTAMPTZ NOT NULL,
        incident_type VARCHAR(50),
        neighborhood VARCHAR(100),
        severity INTEGER,
        age_group VARCHAR(20),
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Weather features table
    CREATE TABLE IF NOT EXISTS weather_features (
        id SERIAL PRIMARY KEY,
        station_id VARCHAR(50) NOT NULL,
        observation_time TIMESTAMPTZ NOT NULL,
        temperature FLOAT,
        wind_speed FLOAT,
        wind_chill FLOAT,
        precipitation FLOAT,
        snow_depth FLOAT,
        hour INTEGER,
        day_of_week INTEGER,
        month INTEGER,
        is_weekend INTEGER,
        temp_lag_1h FLOAT,
        temp_lag_3h FLOAT,
        temp_lag_6h FLOAT,
        temp_rolling_mean_24h FLOAT,
        freeze_thaw_risk INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Predictions table
    CREATE TABLE IF NOT EXISTS predictions (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL,
        prediction INTEGER,
        probability FLOAT,
        risk_level VARCHAR(20),
        features JSONB,
        model_version VARCHAR(50),
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_weather_raw_time ON weather_raw(observation_time DESC);
    CREATE INDEX IF NOT EXISTS idx_injuries_raw_date ON injuries_raw(incident_date DESC);
    CREATE INDEX IF NOT EXISTS idx_injuries_neighborhood ON injuries_raw(neighborhood);
    CREATE INDEX IF NOT EXISTS idx_predictions_time ON predictions(timestamp DESC);
    
    -- MLflow tables (for MLflow backend)
    -- These are created automatically by MLflow, but we ensure the database exists
    """
    
    with engine.connect() as conn:
        for statement in schema.split(';'):
            if statement.strip():
                try:
                    conn.execute(text(statement))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Statement failed (may already exist): {e}")
    
    logger.info("Database initialization completed successfully")


if __name__ == "__main__":
    init_database()
