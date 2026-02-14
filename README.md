# Urban Winter Injury Risk & Equity Observatory

FastAPI + MLOps portfolio project that predicts neighborhood-level winter injury risk in Edmonton using weather, temporal, and socioeconomic features.

This repository is optimized for recruiter review: reproducible startup, deterministic local model inference, smoke-tested API routes, and clear docs for Codespaces and live deployment.

## Architecture Snapshot

- Inference/API: `FastAPI` in `api/`
- Demo model artifact: `artifacts/demo_model.joblib`
- Synthetic data generator: `synthetic_data/generate_data.py`
- Training and pipeline modules: `ml_pipeline/`, `dagster_project/`
- Infra-as-code (documented path): `terraform/`

## Live Demo

- Landing page: `https://<your-render-service>.onrender.com/`
- API docs: `https://<your-render-service>.onrender.com/docs`
- Health: `https://<your-render-service>.onrender.com/health`

Set a token in Render as `DEMO_API_TOKEN`, then call:

```bash
curl -X POST "https://<your-render-service>.onrender.com/predict" \
  -H "Authorization: Bearer <DEMO_API_TOKEN>" \
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
```

## Run in Codespaces

```bash
python -m venv .venv
source .venv/bin/activate
make install-runtime
make build-demo-model
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Open:

- `http://localhost:8000/`
- `http://localhost:8000/docs`

## Demo Credentials

- Auth scheme: Bearer token
- Environment variable: `DEMO_API_TOKEN`
- Fallback: `API_SECRET_KEY` if `DEMO_API_TOKEN` is not set

For local testing:

```bash
export DEMO_API_TOKEN=dev-secret
```

## Model Backend Modes

- Default (demo-safe): `MODEL_BACKEND=local`
  - Loads `MODEL_ARTIFACT_PATH` (default: `artifacts/demo_model.joblib`)
  - Starts reliably without MLflow
- Optional: `MODEL_BACKEND=mlflow`
  - Attempts MLflow model loading
  - Falls back to local artifact if configured and available

## Smoke Testing

Local smoke tests:

```bash
pytest tests/smoke -v
```

Live smoke script:

```bash
python scripts/smoke_live.py --base-url "https://<your-render-service>.onrender.com" --token "<DEMO_API_TOKEN>"
```

## Render Deployment (Free Tier)

Build from `docker/Dockerfile.api` and set these environment variables in Render UI:

- `MODEL_BACKEND=local`
- `MODEL_ARTIFACT_PATH=artifacts/demo_model.joblib`
- `DEMO_API_TOKEN=<your-demo-token>`
- `API_SECRET_KEY=<optional-fallback-token>`
- `DATABASE_URL` optional for demo mode

Health check path:

- `/health`

## Production-Ready vs Demo Mode

- Production-shaped components included:
  - Dagster pipeline modules
  - MLflow training/registry integration paths
  - Terraform infrastructure definitions
- Demo-mode defaults for reliability tonight:
  - Local bundled model artifact
  - Optional DB dependency
  - Single-service landing page + API deployment

## Common Commands

```bash
make install             # Full stack dependencies
make install-runtime     # Runtime + dev dependencies
make build-demo-model    # Regenerate artifacts/demo_model.joblib
make test                # Full test suite
make smoke               # Smoke suite
```

## Roadmap

- [ ] Publicly host Dagster UI and MLflow tracking as separate services
- [ ] Add production auth/key rotation flow
- [ ] Add integration tests for Docker Compose startup
- [ ] Add drift report publishing to hosted dashboard
- [ ] Add custom domain and TLS policy documentation
