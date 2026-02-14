# Urban Winter Injury Risk & Equity Observatory

A production-ready MLOps system for predicting and monitoring winter-related injury risks in Edmonton, integrating real-time weather data, historical injury patterns, and socioeconomic factors.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Ingestion Layer                     │
├─────────────────────────────────────────────────────────────┤
│  Environment Canada API  │  Open Data Edmonton  │  Synthetic │
│  (Weather, Conditions)   │  (Injuries, Demographics) │  Data  │
└───────────────┬─────────────────────────┬──────────────────┘
                │                         │
                ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Dagster Orchestration (ECS/Local)              │
├─────────────────────────────────────────────────────────────┤
│  Bronze Layer  →  Silver Layer  →  Gold Layer              │
│  (Raw Data)       (Cleaned)        (Features & Aggregates) │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│           PostgreSQL RDS (TimescaleDB Extension)            │
│  Tables: weather_raw, injuries_raw, demographics,           │
│          weather_features, injury_aggregates, predictions   │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│              ML Pipeline (Lambda + ECS)                     │
├─────────────────────────────────────────────────────────────┤
│  XGBoost Training  →  MLflow Tracking  →  Model Registry   │
│  Feature Engineering │  Hyperparameter Tuning              │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Application (ECS Fargate)              │
├─────────────────────────────────────────────────────────────┤
│  /predict  │  /batch_predict  │  /model_metrics │  /health │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│         Evidently Monitoring (S3 + CloudWatch)              │
│  Data Drift │  Model Performance │  Data Quality            │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.11+
- Docker & Docker Compose
- AWS CLI configured with credentials
- Terraform 1.5+
- PostgreSQL client (psql)
- Git

## 🚀 Quick Start (Local Development)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd winter-injury-observatory

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configurations
# Required variables:
# - DATABASE_URL
# - AWS_REGION
# - MLFLOW_TRACKING_URI
# - ENVIRONMENT_CANADA_API_KEY (optional, public API)
```

### 3. Start Local Infrastructure

```bash
# Start PostgreSQL, MLflow, and supporting services
docker-compose up -d

# Wait for services to be healthy
docker-compose ps
```

### 4. Initialize Database

```bash
# Run migrations
python scripts/init_db.py

# Generate synthetic data for development
python synthetic_data/generate_data.py --days 365 --output data/synthetic
```

### 5. Start Dagster

```bash
# In one terminal
dagster dev -f dagster_project/definitions.py
```

### 6. Train Initial Model

```bash
# Run training pipeline
python ml_pipeline/training/train_model.py --config configs/training_config.yaml
```

### 7. Start API

```bash
# In another terminal
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Visit:
- Dagster UI: http://localhost:3000
- MLflow UI: http://localhost:5000
- API Docs: http://localhost:8000/docs

## ☁️ AWS Deployment

### 1. Infrastructure Provisioning

```bash
cd terraform/environments/dev

# Initialize Terraform
terraform init

# Review plan
terraform plan -var-file="dev.tfvars"

# Apply infrastructure
terraform apply -var-file="dev.tfvars"

# Outputs will include:
# - RDS endpoint
# - ECS cluster name
# - S3 bucket names
# - Lambda function ARNs
```

### 2. Deploy Services

```bash
# Build and push Docker images
./scripts/build_and_push.sh

# Deploy via GitHub Actions (automatic on push to main)
git push origin main

# Or manually deploy
./scripts/deploy.sh
```

### 3. Configure Secrets

```bash
# Store secrets in AWS Secrets Manager
aws secretsmanager create-secret \
  --name winter-injury-observatory/prod/db-password \
  --secret-string "your-secure-password"

aws secretsmanager create-secret \
  --name winter-injury-observatory/prod/mlflow-credentials \
  --secret-string '{"username":"admin","password":"secure-password"}'
```

## 📊 Data Pipeline

### Dagster Assets

**Bronze Layer** (Raw Data Ingestion):
- `weather_raw`: Environment Canada weather observations
- `injuries_raw`: Historical injury data from Open Data Edmonton
- `demographics_raw`: Census and socioeconomic data

**Silver Layer** (Cleaned Data):
- `weather_cleaned`: Validated and normalized weather data
- `injuries_cleaned`: Deduplicated and standardized injury records
- `demographics_processed`: Aggregated demographic features

**Gold Layer** (Analytics-Ready):
- `weather_features`: Engineered weather features (rolling averages, lag features)
- `injury_aggregates`: Daily/weekly injury counts by type and location
- `model_training_data`: Final feature matrix for ML training

### Scheduling

- Weather data ingestion: Every 1 hour
- Injury data ingestion: Daily at 2 AM
- Feature engineering: Daily at 3 AM
- Model retraining: Weekly on Sundays at 4 AM

## 🤖 ML Pipeline

### Model Architecture

**XGBoost Classifier** for injury risk prediction:
- Binary classification: High risk (>75th percentile) vs. Normal
- Multi-class classification: Risk level (Low/Medium/High/Critical)

**Features** (~50 total):
- Weather: Temperature, wind chill, precipitation, snowfall, ice conditions
- Temporal: Hour, day of week, month, holidays, school breaks
- Spatial: Neighborhood, socioeconomic indicators, infrastructure
- Historical: Lagged injury counts, moving averages

**Evaluation Metrics**:
- Accuracy, Precision, Recall, F1-Score
- ROC-AUC, PR-AUC
- Calibration curves
- Feature importance analysis

### MLflow Tracking

All experiments tracked with:
- Hyperparameters
- Metrics per epoch/fold
- Model artifacts
- Feature importance plots
- Confusion matrices

### Model Deployment

- Models versioned in MLflow Model Registry
- Automatic staging: None → Staging → Production
- A/B testing capability via model version routing
- Rollback mechanism on performance degradation

## 🔌 API Endpoints

### Core Endpoints

**POST /predict**
```json
{
  "temperature": -15.5,
  "wind_speed": 25.0,
  "precipitation": 2.5,
  "hour": 8,
  "day_of_week": 1,
  "neighborhood": "downtown"
}
```

**POST /batch_predict**
```json
{
  "predictions": [
    {"temperature": -15.5, "wind_speed": 25.0, ...},
    {"temperature": -12.0, "wind_speed": 15.0, ...}
  ]
}
```

**GET /model_metrics**
Returns current model performance metrics

**GET /health**
Service health check with dependency status

### Authentication

API uses JWT tokens for authentication:
```bash
# Get token
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secure"

# Use token
curl -X POST "http://localhost:8000/predict" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"temperature": -15.5, ...}'
```

## 📈 Monitoring

### Evidently Integration

Monitors tracked automatically:
- **Data Drift**: Detecting feature distribution changes
- **Model Performance**: Real-time accuracy, precision, recall
- **Data Quality**: Missing values, range violations, schema changes
- **Prediction Drift**: Shifts in prediction distribution

Reports generated:
- Hourly: Data quality checks
- Daily: Data drift analysis
- Weekly: Model performance review

Alerts sent to CloudWatch when:
- Data drift score > 0.3
- Model accuracy drops > 10%
- Data quality issues detected
- Prediction latency > 500ms

### CloudWatch Dashboards

Custom dashboards for:
- API latency and error rates
- Prediction volume and distribution
- Model performance metrics
- Database query performance
- ECS task health and resource usage

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests (requires Docker)
pytest tests/integration/

# With coverage
pytest --cov=dagster_project --cov=ml_pipeline --cov=api tests/

# Load testing
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

## 📦 Project Structure

```
winter-injury-observatory/
├── terraform/                  # Infrastructure as Code
│   ├── modules/               # Reusable Terraform modules
│   │   ├── lambda/           # Lambda function configs
│   │   ├── kinesis/          # Kinesis stream configs
│   │   ├── rds/              # RDS PostgreSQL configs
│   │   ├── ecs/              # ECS Fargate configs
│   │   ├── s3/               # S3 bucket configs
│   │   └── iam/              # IAM roles and policies
│   └── environments/          # Environment-specific configs
│       ├── dev/
│       └── prod/
├── dagster_project/           # Data orchestration
│   ├── assets/               # Data assets (bronze/silver/gold)
│   ├── resources/            # External connections
│   ├── jobs/                 # Job definitions
│   ├── sensors/              # Event-driven triggers
│   └── schedules/            # Time-based triggers
├── data_connectors/           # API clients
│   ├── environment_canada.py
│   └── open_data_edmonton.py
├── synthetic_data/            # Data generation
│   └── generate_data.py
├── ml_pipeline/               # Machine learning
│   ├── training/             # Model training scripts
│   ├── models/               # Model definitions
│   └── evaluation/           # Evaluation utilities
├── api/                       # FastAPI application
│   ├── routers/              # API endpoints
│   ├── models/               # Pydantic models
│   └── services/             # Business logic
├── monitoring/                # Evidently configs
├── docker/                    # Dockerfiles
├── .github/workflows/         # CI/CD pipelines
├── tests/                     # Test suite
├── configs/                   # Configuration files
└── scripts/                   # Utility scripts
```

## 💰 Cost Estimation (AWS Free Tier / <$20/month)

- **RDS**: db.t3.micro (free tier eligible) - $0-15/month
- **ECS Fargate**: 0.25 vCPU, 0.5 GB RAM - $5-10/month
- **Lambda**: 1M requests/month free - $0-2/month
- **S3**: 5 GB storage - $0-1/month
- **CloudWatch**: Basic monitoring - $0-2/month
- **Data Transfer**: <1 GB/month - $0-1/month

**Total**: ~$10-20/month with careful resource management

### Cost Optimization Tips

1. Use RDS snapshots instead of continuous backups
2. Set up ECS task auto-scaling with conservative thresholds
3. Use S3 Intelligent-Tiering for model artifacts
4. Schedule non-critical jobs during off-peak hours
5. Set up billing alerts at $15 and $25 thresholds

## 🔐 Security Best Practices

1. **Secrets Management**: All credentials in AWS Secrets Manager or environment variables
2. **Network Security**: VPC with private subnets for RDS and ECS
3. **IAM**: Least privilege principle for all roles
4. **API Security**: JWT authentication, rate limiting
5. **Data Encryption**: At rest (RDS) and in transit (TLS)
6. **Logging**: Comprehensive CloudWatch logs for audit trails

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add type hints to all functions
- Write docstrings for public APIs
- Maintain test coverage >80%
- Update documentation for new features

## 📝 License

This project is licensed under the MIT License - see LICENSE file for details.

## 📧 Contact

For questions or support, please open an issue on GitHub.

## 🙏 Acknowledgments

- Environment Canada for weather data API
- City of Edmonton Open Data Portal
- Canadian winter injury research literature
- Open-source community (Dagster, MLflow, FastAPI, XGBoost)

## 🗺️ Roadmap

- [ ] Real-time streaming predictions via Kinesis
- [ ] Interactive dashboard with Streamlit/Plotly
- [ ] Mobile app integration
- [ ] Advanced spatial analysis with GeoPandas
- [ ] Deep learning models (LSTM for time series)
- [ ] Multi-city expansion beyond Edmonton
- [ ] Public health department integration
