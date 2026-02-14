"""
Dagster Resources

Resources for database connections, S3, API clients, etc.
"""
import os
from typing import Dict

from dagster import ConfigurableResource
from dagster_aws.s3 import S3Resource
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DatabaseResource(ConfigurableResource):
    """PostgreSQL database resource"""
    
    connection_string: str
    
    def get_connection(self):
        """Get a database connection"""
        return psycopg2.connect(self.connection_string)
    
    def get_engine(self):
        """Get SQLAlchemy engine"""
        return create_engine(self.connection_string)
    
    def get_session(self):
        """Get SQLAlchemy session"""
        engine = self.get_engine()
        Session = sessionmaker(bind=engine)
        return Session()


class EnvironmentCanadaResource(ConfigurableResource):
    """Environment Canada API resource"""
    
    api_url: str = "https://api.weather.gc.ca/collections/climate-hourly/items"
    timeout: int = 30
    
    def fetch_weather_data(self, station_id: str, **kwargs):
        """Fetch weather data from Environment Canada"""
        from data_connectors.environment_canada import EnvironmentCanadaClient
        
        with EnvironmentCanadaClient(timeout=self.timeout) as client:
            return client.get_current_weather(station_id=station_id)


class OpenDataEdmontonResource(ConfigurableResource):
    """Open Data Edmonton API resource"""
    
    app_token: str = ""
    timeout: int = 30
    
    def fetch_injury_data(self, **kwargs):
        """Fetch injury data from Open Data Edmonton"""
        from data_connectors.open_data_edmonton import OpenDataEdmontonClient
        
        with OpenDataEdmontonClient(
            app_token=self.app_token if self.app_token else None,
            timeout=self.timeout
        ) as client:
            return client.get_injury_data(**kwargs)


def get_resources() -> Dict:
    """
    Get all resources for Dagster.
    
    Returns:
        Dictionary of resource instances
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    return {
        "database": DatabaseResource(connection_string=database_url),
        "s3": S3Resource(
            region_name=os.getenv("AWS_REGION", "us-west-2")
        ),
        "environment_canada": EnvironmentCanadaResource(),
        "open_data_edmonton": OpenDataEdmontonResource(
            app_token=os.getenv("OPEN_DATA_APP_TOKEN", "")
        ),
    }
