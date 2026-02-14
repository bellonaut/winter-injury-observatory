"""
Open Data Edmonton API Connector

Fetches injury, demographic, and infrastructure data from Edmonton's Open Data Portal.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import pandas as pd
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class InjuryRecord(BaseModel):
    """Injury record data model"""
    incident_id: str
    incident_date: datetime
    incident_type: str
    location_description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    neighborhood: Optional[str] = None
    severity: Optional[str] = None
    age_group: Optional[str] = None
    weather_condition: Optional[str] = None


class OpenDataEdmontonClient:
    """Client for City of Edmonton Open Data Portal"""
    
    BASE_URL = "https://data.edmonton.ca/resource"
    
    # Dataset identifiers (these are examples - actual IDs may differ)
    INJURY_DATASET = "emergency-calls.json"  # Example dataset
    DEMOGRAPHICS_DATASET = "census-data.json"
    INFRASTRUCTURE_DATASET = "sidewalk-conditions.json"
    
    def __init__(
        self,
        app_token: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize Open Data Edmonton API client.
        
        Args:
            app_token: Optional Socrata app token for higher rate limits
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.app_token = app_token
        self.timeout = timeout
        self.max_retries = max_retries
        
        headers = {}
        if app_token:
            headers["X-App-Token"] = app_token
        
        self.client = httpx.Client(
            timeout=timeout,
            headers=headers,
            follow_redirects=True
        )
    
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Make API request with error handling.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            List of records from API
        """
        try:
            url = f"{self.BASE_URL}/{endpoint}"
            response = self.client.get(url, params=params or {})
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error making request: {e}")
            return []
    
    def get_injury_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        injury_type: Optional[str] = None,
        limit: int = 10000
    ) -> pd.DataFrame:
        """
        Fetch injury/incident data.
        
        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            injury_type: Type of injury to filter
            limit: Maximum number of records
            
        Returns:
            DataFrame with injury records
        """
        params = {"$limit": limit}
        
        # Build SoQL WHERE clause
        where_clauses = []
        if start_date:
            where_clauses.append(
                f"incident_date >= '{start_date.date().isoformat()}'"
            )
        if end_date:
            where_clauses.append(
                f"incident_date <= '{end_date.date().isoformat()}'"
            )
        if injury_type:
            where_clauses.append(f"incident_type = '{injury_type}'")
        
        if where_clauses:
            params["$where"] = " AND ".join(where_clauses)
        
        data = self._make_request(self.INJURY_DATASET, params)
        
        if not data:
            logger.warning("No injury data found")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Standardize column names
        if "incident_date" in df.columns:
            df["incident_date"] = pd.to_datetime(df["incident_date"])
        
        logger.info(f"Fetched {len(df)} injury records")
        return df
    
    def get_demographics_data(
        self,
        neighborhoods: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Fetch demographic and socioeconomic data by neighborhood.
        
        Args:
            neighborhoods: List of neighborhood names to filter
            
        Returns:
            DataFrame with demographic data
        """
        params = {"$limit": 10000}
        
        if neighborhoods:
            neighborhood_filter = "', '".join(neighborhoods)
            params["$where"] = f"neighborhood IN ('{neighborhood_filter}')"
        
        data = self._make_request(self.DEMOGRAPHICS_DATASET, params)
        
        if not data:
            logger.warning("No demographics data found")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        logger.info(f"Fetched demographics for {len(df)} neighborhoods")
        return df
    
    def get_infrastructure_data(
        self,
        infrastructure_type: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch infrastructure data (sidewalks, roads, lighting, etc.).
        
        Args:
            infrastructure_type: Type of infrastructure to fetch
            
        Returns:
            DataFrame with infrastructure data
        """
        params = {"$limit": 10000}
        
        if infrastructure_type:
            params["$where"] = f"type = '{infrastructure_type}'"
        
        data = self._make_request(self.INFRASTRUCTURE_DATASET, params)
        
        if not data:
            logger.warning("No infrastructure data found")
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        logger.info(f"Fetched {len(df)} infrastructure records")
        return df
    
    def get_winter_maintenance_schedule(self) -> pd.DataFrame:
        """
        Fetch winter road/sidewalk maintenance schedule.
        
        Returns:
            DataFrame with maintenance schedule
        """
        # This would connect to Edmonton's winter maintenance dataset
        # Example implementation
        endpoint = "winter-maintenance.json"
        data = self._make_request(endpoint, {"$limit": 10000})
        
        if not data:
            return pd.DataFrame()
        
        return pd.DataFrame(data)
    
    def get_neighborhood_boundaries(self) -> pd.DataFrame:
        """
        Fetch neighborhood boundary geometries.
        
        Returns:
            DataFrame with neighborhood polygons
        """
        endpoint = "neighbourhood-boundaries.json"
        data = self._make_request(endpoint, {"$limit": 500})
        
        if not data:
            return pd.DataFrame()
        
        return pd.DataFrame(data)
    
    def search_datasets(self, query: str) -> List[Dict]:
        """
        Search for available datasets.
        
        Args:
            query: Search query
            
        Returns:
            List of matching datasets
        """
        # Use Socrata Discovery API
        discovery_url = "https://api.us.socrata.com/api/catalog/v1"
        params = {
            "domains": "data.edmonton.ca",
            "q": query,
            "limit": 100
        }
        
        try:
            response = self.client.get(discovery_url, params=params)
            response.raise_for_status()
            results = response.json()
            return results.get("results", [])
        except Exception as e:
            logger.error(f"Error searching datasets: {e}")
            return []
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience functions
def fetch_recent_injuries(days: int = 30) -> pd.DataFrame:
    """
    Fetch injury data for the past N days.
    
    Args:
        days: Number of days to fetch
        
    Returns:
        DataFrame with injury records
    """
    from datetime import timedelta
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    with OpenDataEdmontonClient() as client:
        return client.get_injury_data(
            start_date=start_date,
            end_date=end_date
        )


def fetch_edmonton_demographics() -> pd.DataFrame:
    """
    Fetch demographic data for all Edmonton neighborhoods.
    
    Returns:
        DataFrame with demographic data
    """
    with OpenDataEdmontonClient() as client:
        return client.get_demographics_data()


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    with OpenDataEdmontonClient() as client:
        # Search for relevant datasets
        print("Searching for injury-related datasets...")
        datasets = client.search_datasets("injury")
        for dataset in datasets[:5]:
            print(f"- {dataset.get('resource', {}).get('name', 'Unknown')}")
        
        # Fetch recent injuries
        print("\nFetching recent injury data...")
        injuries = fetch_recent_injuries(days=30)
        if not injuries.empty:
            print(f"Found {len(injuries)} injury records")
            print(injuries.head())
        
        # Fetch demographics
        print("\nFetching demographics data...")
        demographics = fetch_edmonton_demographics()
        if not demographics.empty:
            print(f"Found demographics for {len(demographics)} areas")
            print(demographics.head())
