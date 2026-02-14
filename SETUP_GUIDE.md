# Urban Winter Injury Risk & Equity Observatory - Setup Guide

## 🎯 Quick Start (5 Minutes)

### Prerequisites Check
```bash
# Verify installations
python --version  # Should be 3.11+
docker --version
docker-compose --version
terraform --version  # Should be 1.5+
aws --version
```

### Step 1: Clone and Setup Environment
```bash
cd winter-injury-observatory

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
make install

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your values
```

### Step 2: Start Local Services
```bash
# Start all services (PostgreSQL, MLflow, MinIO, API, Dagster)
make dev

# Wait 30 seconds for services to initialize
sleep 30

# Initialize database
python scripts/init_db.py

# Generate synthetic data (optional for dev)
python synthetic_data/generate_data.py --days 90
```

### Step 3: Train Initial Model
```bash
# Train model with MLflow tracking
python ml_pipeline/training/train_model.py --config configs/training_config.yaml

# View training results
open http://localhost:5000  # MLflow UI
```

### Step 4: Test API
```bash
# Health check
curl http://localhost:8000/health

# Get API token (simplified for dev)
export API_TOKEN="dev-secret"

# Make prediction
curl -X POST http://localhost:8000/predict \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
    "infrastructure_quality": 0.70
  }'

# View API docs
open http://localhost:8000/docs
```

### Step 5: View Dagster UI
```bash
open http://localhost:3000
# Click "Materialize all" to run the full data pipeline
```

## 🚀 AWS Deployment (Production)

### Step 1: Configure AWS
```bash
# Configure AWS CLI
aws configure

# Create S3 bucket for Terraform state
aws s3 mb s3://winter-injury-observatory-terraform-state

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name winter-injury-observatory-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### Step 2: Deploy Infrastructure
```bash
cd terraform/environments/dev

# Initialize Terraform
terraform init

# Review plan
terraform plan -var-file="dev.tfvars"

# Apply (will create VPC, RDS, ECS, Lambda, S3)
terraform apply -var-file="dev.tfvars"

# Save outputs
terraform output > ../../../terraform-outputs.txt
```

### Step 3: Configure Secrets
```bash
# Get database password from Terraform output
DB_SECRET_ARN=$(terraform output -raw database_secret_arn)

# Store API secret
aws secretsmanager create-secret \
  --name winter-injury-observatory/dev/api-secret \
  --secret-string "your-secure-random-secret-here"
```

### Step 4: Deploy Application
```bash
cd ../../..  # Back to project root

# Build and deploy
./scripts/deploy.sh dev

# Monitor deployment
aws ecs describe-services \
  --cluster winter-injury-observatory-dev-cluster \
  --services winter-injury-observatory-dev-api
```

### Step 5: Initialize Production Database
```bash
# Get RDS endpoint from Terraform
RDS_ENDPOINT=$(cd terraform/environments/dev && terraform output -raw database_endpoint)

# Set DATABASE_URL
export DATABASE_URL="postgresql://postgres:PASSWORD@$RDS_ENDPOINT/winter_injury_observatory"

# Initialize
python scripts/init_db.py
```

### Step 6: Verify Deployment
```bash
# Get API URL
API_URL=$(cd terraform/environments/dev && terraform output -raw api_url)

# Test health
curl $API_URL/health

# Test prediction (requires auth token)
curl -X POST $API_URL/predict \
  -H "Authorization: Bearer $API_SECRET" \
  -H "Content-Type: application/json" \
  -d @examples/sample_request.json
```

## 🧪 Testing

### Run All Tests
```bash
make test
```

### Run Specific Test Suites
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests (requires Docker)
pytest tests/integration/ -v

# With coverage report
pytest --cov=api --cov=ml_pipeline --cov=dagster_project --cov-report=html
open htmlcov/index.html
```

### Load Testing
```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load/locustfile.py --host=http://localhost:8000
open http://localhost:8089
```

## 📊 Monitoring

### View Logs
```bash
# Docker logs
docker-compose logs -f api
docker-compose logs -f dagster

# AWS CloudWatch logs
aws logs tail /ecs/winter-injury-observatory-dev --follow
```

### MLflow Tracking
```bash
# Local
open http://localhost:5000

# View experiments
mlflow experiments list

# Compare runs
mlflow ui
```

### Evidently Reports
```bash
# Generate drift report
python monitoring/generate_reports.py --report-type drift

# View report
open reports/drift_report.html
```

## 🔧 Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Restart database
docker-compose restart postgres
```

### Model Not Loading
```bash
# Check MLflow server
curl http://localhost:5000/health

# List registered models
mlflow models list

# Re-register model
mlflow models register --model-uri runs:/RUN_ID/model --name winter-injury-risk
```

### API Not Responding
```bash
# Check API logs
docker-compose logs api

# Restart API
docker-compose restart api

# Check health
curl http://localhost:8000/health
```

### Dagster Pipeline Failures
```bash
# View Dagster logs
docker-compose logs dagster

# Check asset status in UI
open http://localhost:3000

# Rematerialize failed assets
# Use Dagster UI to rematerialize specific assets
```

## 📈 Scaling & Optimization

### Increase ECS Task Resources
Edit `terraform/modules/ecs/main.tf`:
```hcl
cpu    = "512"   # Was 256
memory = "1024"  # Was 512
```

### Enable Auto-Scaling
Already configured in Terraform with target CPU 70%

### Optimize Database Queries
```sql
-- Add indexes
CREATE INDEX idx_weather_neighborhood ON weather_features(neighborhood, observation_time DESC);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM weather_features WHERE ...;
```

### Reduce Costs
- Use Spot instances for ECS (requires code changes)
- Schedule ECS tasks to scale down at night
- Enable S3 Intelligent-Tiering (already configured)
- Use RDS reserved instances for production

## 🔐 Security Checklist

- [ ] Rotate database passwords monthly
- [ ] Enable MFA on AWS account
- [ ] Review IAM policies (principle of least privilege)
- [ ] Enable AWS CloudTrail for audit logs
- [ ] Set up AWS GuardDuty for threat detection
- [ ] Configure VPC Flow Logs
- [ ] Enable RDS encryption at rest
- [ ] Use HTTPS/TLS for all API endpoints
- [ ] Implement rate limiting on API
- [ ] Regular security patches (Docker images, Python packages)

## 📚 Additional Resources

- [Dagster Documentation](https://docs.dagster.io)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [XGBoost Documentation](https://xgboost.readthedocs.io)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Evidently Documentation](https://docs.evidentlyai.com)

## 🆘 Getting Help

1. Check logs first (see Monitoring section)
2. Review this guide's Troubleshooting section
3. Check GitHub Issues
4. Consult documentation links above
5. Open a new GitHub Issue with:
   - Clear description of problem
   - Steps to reproduce
   - Relevant logs
   - Environment details (OS, Python version, etc.)
