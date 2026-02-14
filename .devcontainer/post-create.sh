#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(pwd)"
cd "${REPO_ROOT}"

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-runtime.txt
pip install -r requirements-dev.txt

if [ ! -f "artifacts/demo_model.joblib" ]; then
  python scripts/build_demo_model.py --days 120 --seed 42 --output artifacts
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi
