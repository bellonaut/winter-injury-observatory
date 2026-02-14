"""
Synthetic Winter Injury Data Generator

Generates realistic synthetic data based on Canadian winter injury literature:
- Richmond et al. (2016): Winter-related injuries in Canadian hospitals  
- Bernatsky et al. (2012): Ice storm injuries in Montreal
- Gao et al. (2018): Environmental factors and fall-related injuries
- Statistics Canada winter injury reports

This generates data for development/testing that reflects real patterns.
"""
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WinterInjuryDataGenerator:
    """
    Generates synthetic winter injury data based on research findings.
    
    Key patterns from literature:
    - Peak injury risk: temperatures -5°C to -15°C (freeze-thaw cycles)
    - Increased risk with precipitation, especially freezing rain
    - Morning/evening peaks (8-9 AM, 5-6 PM) during commute times
    - Higher risk for elderly (65+) and young adults (20-29)
    - Weekend peaks for recreational injuries
    - Geographic variation based on socioeconomic factors
    """
    
    # Edmonton neighborhoods with socioeconomic characteristics
    NEIGHBORHOODS = {
        "Downtown": {"ses_index": 0.45, "infrastructure_quality": 0.7, "pop_density": 0.9},
        "Oliver": {"ses_index": 0.65, "infrastructure_quality": 0.75, "pop_density": 0.8},
        "Strathcona": {"ses_index": 0.70, "infrastructure_quality": 0.80, "pop_density": 0.7},
        "Bonnie Doon": {"ses_index": 0.60, "infrastructure_quality": 0.70, "pop_density": 0.6},
        "Mill Woods": {"ses_index": 0.55, "infrastructure_quality": 0.65, "pop_density": 0.7},
        "West Edmonton": {"ses_index": 0.50, "infrastructure_quality": 0.60, "pop_density": 0.5},
        "North Edmonton": {"ses_index": 0.40, "infrastructure_quality": 0.55, "pop_density": 0.6},
        "Riverbend": {"ses_index": 0.75, "infrastructure_quality": 0.85, "pop_density": 0.5},
        "Terwillegar": {"ses_index": 0.80, "infrastructure_quality": 0.85, "pop_density": 0.4},
        "Castle Downs": {"ses_index": 0.58, "infrastructure_quality": 0.68, "pop_density": 0.6},
    }
    
    # Injury types and their typical severity
    INJURY_TYPES = {
        "slip_fall": {"severity_mean": 2.5, "severity_std": 1.0, "probability": 0.65},
        "vehicle_collision": {"severity_mean": 3.5, "severity_std": 1.5, "probability": 0.15},
        "recreational": {"severity_mean": 2.0, "severity_std": 1.2, "probability": 0.12},
        "sports": {"severity_mean": 2.2, "severity_std": 1.0, "probability": 0.05},
        "other": {"severity_mean": 2.0, "severity_std": 1.0, "probability": 0.03},
    }
    
    def __init__(self, random_seed: int = 42):
        """Initialize generator with random seed for reproducibility"""
        self.rng = np.random.RandomState(random_seed)
    
    def generate_weather_data(
        self,
        start_date: datetime,
        days: int
    ) -> pd.DataFrame:
        """
        Generate synthetic weather data for Edmonton.
        
        Based on Edmonton climate normals:
        - Winter mean temp: -10°C to -15°C
        - Temperature range: -40°C to +5°C
        - Significant snowfall November through March
        """
        dates = pd.date_range(start=start_date, periods=days * 24, freq="H")
        
        weather_records = []
        
        for date in dates:
            # Seasonal temperature pattern
            day_of_year = date.timetuple().tm_yday
            seasonal_temp = -15 + 10 * np.cos(2 * np.pi * (day_of_year - 30) / 365)
            
            # Daily temperature variation
            hour_temp_variation = -3 * np.cos(2 * np.pi * date.hour / 24)
            
            # Random variation
            temp_noise = self.rng.normal(0, 3)
            
            temperature = seasonal_temp + hour_temp_variation + temp_noise
            
            # Wind speed (higher in winter)
            wind_speed = max(0, self.rng.gamma(15, 2) + self.rng.normal(0, 5))
            
            # Wind chill
            if temperature < 10 and wind_speed > 4.8:
                wind_chill = (
                    13.12 + 0.6215 * temperature 
                    - 11.37 * (wind_speed ** 0.16) 
                    + 0.3965 * temperature * (wind_speed ** 0.16)
                )
            else:
                wind_chill = temperature
            
            # Precipitation (higher probability in certain temperature ranges)
            precip_prob = 0.15 if -5 <= temperature <= 0 else 0.08
            precipitation = (
                self.rng.exponential(2) if self.rng.random() < precip_prob else 0
            )
            
            # Snow depth accumulation (simplified)
            if date.month in [11, 12, 1, 2, 3]:
                base_snow_depth = 20 + self.rng.normal(0, 10)
            else:
                base_snow_depth = max(0, 5 - (date.month - 3) * 5 + self.rng.normal(0, 5))
            
            snow_depth = max(0, base_snow_depth)
            
            # Ice conditions (freezing rain indicator)
            ice_condition = (
                "icy" if (temperature > -5 and temperature < 2 and precipitation > 0)
                else "clear"
            )
            
            weather_records.append({
                "timestamp": date,
                "temperature": round(temperature, 1),
                "wind_speed": round(wind_speed, 1),
                "wind_chill": round(wind_chill, 1),
                "precipitation": round(precipitation, 2),
                "snow_depth": round(snow_depth, 1),
                "humidity": int(self.rng.uniform(60, 90)),
                "pressure": round(self.rng.normal(101.3, 1.0), 1),
                "visibility": round(max(0.1, 10 - precipitation * 2), 1),
                "condition": ice_condition,
            })
        
        return pd.DataFrame(weather_records)
    
    def calculate_injury_risk(
        self,
        weather: pd.Series,
        hour: int,
        day_of_week: int,
        neighborhood: str
    ) -> float:
        """
        Calculate injury risk based on conditions.
        
        Risk factors from literature:
        - Temperature: peak risk at -5°C to -15°C
        - Precipitation: increased risk, especially freezing rain
        - Wind chill: increased risk below -20°C
        - Time: peak during commute hours (7-9 AM, 5-7 PM)
        - Day: slightly higher on weekends for recreation
        - Neighborhood: lower SES = higher risk
        """
        base_risk = 0.001  # Base hourly injury rate
        
        # Temperature risk (U-shaped: worst at freeze-thaw temps)
        temp = weather["temperature"]
        if -15 <= temp <= -5:
            temp_factor = 3.0  # Peak risk
        elif -20 <= temp < -15 or -5 < temp <= 0:
            temp_factor = 2.0
        elif temp < -20 or temp > 0:
            temp_factor = 1.0
        else:
            temp_factor = 1.5
        
        # Precipitation risk
        precip_factor = 1.0 + 2.0 * weather["precipitation"]
        
        # Ice condition risk
        ice_factor = 2.5 if weather["condition"] == "icy" else 1.0
        
        # Wind chill risk
        wind_chill = weather["wind_chill"]
        wind_factor = 1.5 if wind_chill < -20 else 1.0
        
        # Time of day risk (commute peaks)
        if hour in [7, 8, 17, 18]:
            time_factor = 2.0
        elif hour in [9, 16, 19]:
            time_factor = 1.5
        elif 22 <= hour or hour <= 5:
            time_factor = 0.3  # Much lower overnight
        else:
            time_factor = 1.0
        
        # Day of week (slight weekend increase for recreation)
        day_factor = 1.2 if day_of_week in [5, 6] else 1.0
        
        # Neighborhood factors
        hood_data = self.NEIGHBORHOODS[neighborhood]
        ses_factor = 2.0 - hood_data["ses_index"]  # Lower SES = higher risk
        infra_factor = 2.0 - hood_data["infrastructure_quality"]
        
        # Combine all factors
        total_risk = (
            base_risk 
            * temp_factor 
            * precip_factor 
            * ice_factor 
            * wind_factor
            * time_factor 
            * day_factor 
            * ses_factor 
            * infra_factor
        )
        
        return total_risk
    
    def generate_injury_data(
        self,
        weather_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate injury records based on weather conditions"""
        injuries = []
        
        for idx, weather_row in weather_data.iterrows():
            hour = weather_row["timestamp"].hour
            day_of_week = weather_row["timestamp"].dayofweek
            
            # Generate injuries for each neighborhood
            for neighborhood in self.NEIGHBORHOODS.keys():
                risk = self.calculate_injury_risk(
                    weather_row, hour, day_of_week, neighborhood
                )
                
                # Poisson process: number of injuries this hour
                n_injuries = self.rng.poisson(risk * 1000)  # Scale up
                
                for _ in range(n_injuries):
                    # Sample injury type
                    injury_type = self.rng.choice(
                        list(self.INJURY_TYPES.keys()),
                        p=[v["probability"] for v in self.INJURY_TYPES.values()]
                    )
                    
                    # Sample severity (1-5 scale)
                    severity = np.clip(
                        self.rng.normal(
                            self.INJURY_TYPES[injury_type]["severity_mean"],
                            self.INJURY_TYPES[injury_type]["severity_std"]
                        ),
                        1, 5
                    )
                    
                    # Sample age (weighted toward vulnerable groups)
                    age_dist = [0.05, 0.25, 0.30, 0.25, 0.15]  # 0-17, 18-34, 35-54, 55-74, 75+
                    age_group = self.rng.choice(
                        ["0-17", "18-34", "35-54", "55-74", "75+"],
                        p=age_dist
                    )
                    
                    injuries.append({
                        "incident_id": f"INJ-{len(injuries):06d}",
                        "timestamp": weather_row["timestamp"],
                        "injury_type": injury_type,
                        "severity": int(round(severity)),
                        "neighborhood": neighborhood,
                        "age_group": age_group,
                        "temperature": weather_row["temperature"],
                        "wind_chill": weather_row["wind_chill"],
                        "precipitation": weather_row["precipitation"],
                        "ice_condition": weather_row["condition"],
                        "hour": hour,
                        "day_of_week": day_of_week,
                        "month": weather_row["timestamp"].month,
                    })
        
        logger.info(f"Generated {len(injuries)} injury records")
        return pd.DataFrame(injuries)
    
    def generate_demographics(self) -> pd.DataFrame:
        """Generate neighborhood demographic data"""
        demographics = []
        
        for neighborhood, characteristics in self.NEIGHBORHOODS.items():
            # Generate population data
            base_pop = int(self.rng.uniform(5000, 25000))
            
            demographics.append({
                "neighborhood": neighborhood,
                "population": base_pop,
                "median_age": int(self.rng.uniform(30, 45)),
                "median_income": int(50000 * characteristics["ses_index"]),
                "ses_index": characteristics["ses_index"],
                "infrastructure_quality": characteristics["infrastructure_quality"],
                "pop_density": characteristics["pop_density"],
                "pct_seniors": self.rng.uniform(0.10, 0.25),
                "pct_children": self.rng.uniform(0.15, 0.30),
                "sidewalk_coverage": characteristics["infrastructure_quality"] * 0.9,
                "lighting_quality": characteristics["infrastructure_quality"] * 0.85,
            })
        
        return pd.DataFrame(demographics)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="Generate synthetic winter injury data"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days to generate"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2023-01-01",
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/synthetic",
        help="Output directory"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse start date
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    
    logger.info(f"Generating {args.days} days of synthetic data...")
    logger.info(f"Start date: {start_date}")
    logger.info(f"Random seed: {args.seed}")
    
    # Initialize generator
    generator = WinterInjuryDataGenerator(random_seed=args.seed)
    
    # Generate weather data
    logger.info("Generating weather data...")
    weather_data = generator.generate_weather_data(start_date, args.days)
    weather_file = output_dir / "weather_data.parquet"
    weather_data.to_parquet(weather_file, index=False)
    logger.info(f"Saved weather data to {weather_file}")
    
    # Generate injury data
    logger.info("Generating injury data...")
    injury_data = generator.generate_injury_data(weather_data)
    injury_file = output_dir / "injury_data.parquet"
    injury_data.to_parquet(injury_file, index=False)
    logger.info(f"Saved injury data to {injury_file}")
    
    # Generate demographics
    logger.info("Generating demographics data...")
    demographics = generator.generate_demographics()
    demo_file = output_dir / "demographics.parquet"
    demographics.to_parquet(demo_file, index=False)
    logger.info(f"Saved demographics to {demo_file}")
    
    # Summary statistics
    logger.info("\n" + "="*60)
    logger.info("DATA GENERATION SUMMARY")
    logger.info("="*60)
    logger.info(f"Weather records: {len(weather_data):,}")
    logger.info(f"Injury records: {len(injury_data):,}")
    logger.info(f"Neighborhoods: {len(demographics)}")
    logger.info(f"Date range: {weather_data['timestamp'].min()} to {weather_data['timestamp'].max()}")
    logger.info(f"Temperature range: {weather_data['temperature'].min():.1f}°C to {weather_data['temperature'].max():.1f}°C")
    logger.info(f"\nInjury type distribution:")
    for injury_type, count in injury_data['injury_type'].value_counts().items():
        pct = 100 * count / len(injury_data)
        logger.info(f"  {injury_type}: {count:,} ({pct:.1f}%)")
    logger.info(f"\nMean daily injuries: {len(injury_data) / args.days:.1f}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
