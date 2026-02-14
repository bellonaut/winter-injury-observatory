# Urban Winter Injury Risk & Equity Observatory

FastAPI + MLOps portfolio project that predicts neighborhood-level winter injury risk in Edmonton using weather, temporal, and socioeconomic features.

This repository is optimized for recruiter review: reproducible startup, deterministic local model inference, smoke-tested API routes, and clear docs for Codespaces and live deployment.

## Architecture Snapshot

- Inference/API: `FastAPI` in `api/`
- Demo model artifact: `artifacts/demo_model.joblib`
- Synthetic data generator: `synthetic_data/generate_data.py`
- Training and pipeline modules: `ml_pipeline/`, `dagster_project/`
- Infra-as-code (documented path): `terraform/`

## Frontend Map Stack

- Map engine: `MapLibre GL JS` loaded via CDN for static frontend compatibility.
- Spatial utilities: `Turf.js` loaded via CDN for client-side map calculations.
- No frontend build step required for deployment on the current single Render service.

## Map Data Sources (Edmonton Open Data)

- Neighborhood boundaries: `xu6q-xcmj`
- Curb / sidewalk network: `4feb-tv8p`
- Winter route status: `8pdx-hfxi`
- Trail closures: `k4mi-dkvi`
- Elevation spots: `tarx-cg5m`

Map layers are fetched live with an hourly TTL cache and stale fallback.

## API Surface (Map + Prediction)

- Public read endpoints:
  - `GET /map/config`
  - `GET /map/layers/neighborhood-risk`
  - `GET /map/layers/sidewalks`
  - `GET /map/layers/winter-routes`
  - `GET /map/layers/trail-closures`
  - `GET /map/layers/elevation-spots`
  - `POST /map/route/neighborhood`
- Token-protected endpoints:
  - `POST /predict`
  - `POST /batch_predict`
  - `GET /model/metrics`
  - `POST /model/reload`

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

Route endpoint example:

```bash
curl -X POST "https://<your-render-service>.onrender.com/map/route/neighborhood" \
  -H "Content-Type: application/json" \
  -d '{
    "from_neighborhood": "Downtown",
    "to_neighborhood": "Terwillegar",
    "hour_offset": 4,
    "temperature": -12.0,
    "precipitation": 2.1,
    "snow_depth": 21.0
  }'
```

## Calibration Disclosure

- `raw_probability` is the direct model output from the bundled classifier.
- `probability` is the adjusted value after domain guardrails (seasonality, overnight exposure, and warm-condition dampening).
- Map tooltips and API responses expose both values plus `calibration_delta`.

## Reviewer Walkthrough (2-3 minutes)

1. Open `/` and confirm map + controls load.
2. Toggle overlays (sidewalks and winter routes) to validate layer fetch and rendering.
3. Move the 24h slider and note top-risk neighborhood changes.
4. Run `/predict` from the UI using demo token and inspect raw response.
5. Run Safest Corridor + compare mode to inspect route sequence and risk delta narrative.

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
- `ENABLE_MAP_V1=true`
- `ENABLE_ROUTE_API_V1=true`
- `ENABLE_SEGMENT_MODEL=false`

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

## Known Limits (Map v1)

- Corridor routing is neighborhood-level approximation, not sidewalk segment A* routing.
- Elevation data is spot-based, not a complete surface raster.
- Risk model is synthetic-data-based and intended for portfolio demonstration, not operational dispatch.

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
