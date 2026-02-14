"""
Environment Canada Weather Data API Connector

Fetches current and historical weather data from Environment Canada's public API.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WeatherObservation(BaseModel):
    """Weather observation data model"""
    station_id: str
    observation_time: datetime
    temperature: Optional[float] = None  # Celsius
    dewpoint: Optional[float] = None
    wind_speed: Optional[float] = None  # km/h
    wind_direction: Optional[str] = None
    wind_gust: Optional[float] = None
    visibility: Optional[float] = None  # km
    pressure: Optional[float] = None  # kPa
    humidity: Optional[float] = None  # percentage
    condition: Optional[str] = None
    precipitation_1h: Optional[float] = None  # mm
    precipitation_24h: Optional[float] = None
    snow_depth: Optional[float] = None  # cm
    wind_chill: Optional[float] = None
    humidex: Optional[float] = None


class EnvironmentCanadaClient:
    """Client for Environment Canada weather data API"""
    
    # Edmonton International Airport station
    EDMONTON_STATION_ID = "CYEG"
    
    # API endpoints
    BASE_URL = "https://api.weather.gc.ca"
    CURRENT_CONDITIONS_URL = f"{BASE_URL}/collections/climate-hourly/items"
    HISTORICAL_URL = f"{BASE_URL}/collections/climate-daily/items"
    
    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        api_key: Optional[str] = None
    ):
        """
        Initialize Environment Canada API client.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            api_key: Optional API key (not required for public API)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_key = api_key
        
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True
        )
    
    def get_current_weather(
        self,
        station_id: str = EDMONTON_STATION_ID
    ) -> Optional[WeatherObservation]:
        """
        Fetch current weather observations for a station.
        
        Args:
            station_id: Weather station identifier
            
        Returns:
            WeatherObservation object or None if request fails
        """
        try:
            params = {
                "CLIMATE_IDENTIFIER": station_id,
                "limit": 1,
                "sortby": "-DATETIME",
                "f": "json"
            }
            
            response = self.client.get(
                self.CURRENT_CONDITIONS_URL,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("features"):
                logger.warning(f"No weather data found for station {station_id}")
                return None
            
            feature = data["features"][0]
            properties = feature["properties"]
            
            return WeatherObservation(
                station_id=station_id,
                observation_time=datetime.fromisoformat(
                    properties["DATETIME"].replace("Z", "+00:00")
                ),
                temperature=properties.get("TEMP"),
                dewpoint=properties.get("DEWPOINT_TEMP"),
                wind_speed=properties.get("WIND_SPEED"),
                wind_direction=properties.get("WIND_DIRECTION"),
                wind_gust=properties.get("WIND_GUST"),
                visibility=properties.get("VISIBILITY"),
                pressure=properties.get("STATION_PRESSURE"),
                humidity=properties.get("RELATIVE_HUMIDITY"),
                condition=properties.get("PRESENT_WEATHER"),
                wind_chill=properties.get("WIND_CHILL"),
                humidex=properties.get("HUMIDEX")
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching current weather: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching current weather: {e}")
            return None
    
    def get_historical_weather(
        self,
        start_date: datetime,
        end_date: datetime,
        station_id: str = EDMONTON_STATION_ID
    ) -> pd.DataFrame:
        """
        Fetch historical weather data for a date range.
        
        Args:
            start_date: Start date for historical data
            end_date: End date for historical data
            station_id: Weather station identifier
            
        Returns:
            DataFrame with historical weather observations
        """
        try:
            params = {
                "CLIMATE_IDENTIFIER": station_id,
                "datetime": f"{start_date.date()}/{end_date.date()}",
                "limit": 10000,
                "f": "json"
            }
            
            response = self.client.get(
                self.HISTORICAL_URL,
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("features"):
                logger.warning(
                    f"No historical data found for {station_id} "
                    f"between {start_date} and {end_date}"
                )
                return pd.DataFrame()
            
            records = []
            for feature in data["features"]:
                props = feature["properties"]
                records.append({
                    "station_id": station_id,
                    "date": props["LOCAL_DATE"],
                    "mean_temp": props.get("MEAN_TEMPERATURE"),
                    "min_temp": props.get("MIN_TEMPERATURE"),
                    "max_temp": props.get("MAX_TEMPERATURE"),
                    "total_precipitation": props.get("TOTAL_PRECIPITATION"),
                    "total_rain": props.get("TOTAL_RAIN"),
                    "total_snow": props.get("TOTAL_SNOW"),
                    "snow_on_ground": props.get("SNOW_ON_GROUND"),
                    "direction_max_gust": props.get("DIRECTION_MAX_GUST"),
                    "speed_max_gust": props.get("SPEED_MAX_GUST")
                })
            
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])
            
            logger.info(
                f"Fetched {len(df)} days of historical weather data "
                f"for {station_id}"
            )
            
            return df
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching historical weather: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching historical weather: {e}")
            return pd.DataFrame()
    
    def get_weather_for_date_range(
        self,
        days: int = 7,
        station_id: str = EDMONTON_STATION_ID
    ) -> pd.DataFrame:
        """
        Fetch weather data for the past N days.
        
        Args:
            days: Number of days to fetch
            station_id: Weather station identifier
            
        Returns:
            DataFrame with weather observations
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        return self.get_historical_weather(
            start_date=start_date,
            end_date=end_date,
            station_id=station_id
        )
    
    def get_forecast(
        self,
        station_id: str = EDMONTON_STATION_ID
    ) -> Dict:
        """
        Fetch weather forecast (Note: Limited availability in public API).
        
        Args:
            station_id: Weather station identifier
            
        Returns:
            Dictionary with forecast data
        """
        # Note: Full forecast data may require different API endpoints
        # This is a placeholder for potential forecast integration
        logger.warning("Forecast data access limited in public API")
        return {}
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function
def fetch_edmonton_weather(days: int = 7) -> pd.DataFrame:
    """
    Convenience function to fetch recent Edmonton weather data.
    
    Args:
        days: Number of days to fetch
        
    Returns:
        DataFrame with weather observations
    """
    with EnvironmentCanadaClient() as client:
        return client.get_weather_for_date_range(days=days)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Fetch current conditions
    with EnvironmentCanadaClient() as client:
        current = client.get_current_weather()
        if current:
            print(f"Current conditions in Edmonton:")
            print(f"Temperature: {current.temperature}°C")
            print(f"Wind Speed: {current.wind_speed} km/h")
            print(f"Humidity: {current.humidity}%")
        
        # Fetch last 7 days
        historical = client.get_weather_for_date_range(days=7)
        print(f"\nFetched {len(historical)} days of historical data")
        print(historical.head())
