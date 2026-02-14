"""Pydantic models for API"""
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class PredictionRequest(BaseModel):
    """Single prediction request"""
    temperature: float = Field(..., description="Temperature in Celsius")
    wind_speed: float = Field(..., description="Wind speed in km/h")
    wind_chill: float = Field(..., description="Wind chill in Celsius")
    precipitation: float = Field(..., description="Precipitation in mm")
    snow_depth: float = Field(..., description="Snow depth in cm")
    hour: int = Field(..., ge=0, le=23, description="Hour of day")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday)")
    month: int = Field(..., ge=1, le=12, description="Month")
    neighborhood: str = Field(..., description="Neighborhood name")
    ses_index: float = Field(..., ge=0, le=1, description="Socioeconomic status index")
    infrastructure_quality: float = Field(..., ge=0, le=1, description="Infrastructure quality index")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "temperature": -15.5,
                "wind_speed": 25.0,
                "wind_chill": -28.0,
                "precipitation": 2.5,
                "snow_depth": 30.0,
                "hour": 8,
                "day_of_week": 1,
                "month": 1,
                "neighborhood": "Downtown",
                "ses_index": 0.45,
                "infrastructure_quality": 0.70,
            }
        }
    )


class PredictionResponse(BaseModel):
    """Single prediction response"""
    prediction: int = Field(..., description="Binary prediction (0=low risk, 1=high risk)")
    probability: float = Field(..., description="Probability of high risk")
    risk_level: str = Field(..., description="Risk level: low, medium, high, critical")
    features: dict = Field(..., description="Input features used for prediction")


class BatchPredictionRequest(BaseModel):
    """Batch prediction request"""
    predictions: List[PredictionRequest]
