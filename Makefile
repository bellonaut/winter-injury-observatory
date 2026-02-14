.PHONY: help install install-runtime dev test lint clean build deploy build-demo-model smoke

help:
	@echo "Available commands:"
	@echo "  make install          - Install full local stack (runtime + MLOps + dev)"
	@echo "  make install-runtime  - Install runtime + dev only (fast local/demo)"
	@echo "  make build-demo-model - Build deterministic demo model artifact"
	@echo "  make dev              - Start development environment"
	@echo "  make test             - Run all tests"
	@echo "  make smoke            - Run smoke tests"
	@echo "  make lint             - Run linters"
	@echo "  make clean            - Clean temporary files"
	@echo "  make build            - Build Docker images"
	@echo "  make deploy           - Deploy to AWS"

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

install-runtime:
	pip install -r requirements-runtime.txt
	pip install -r requirements-dev.txt

build-demo-model:
	python scripts/build_demo_model.py --days 120 --seed 42 --output artifacts

dev:
	docker-compose up -d
	@echo "Services starting..."
	@echo "API: http://localhost:8000"
	@echo "Dagster: http://localhost:3000"
	@echo "MLflow: http://localhost:5000"

test:
	pytest tests/ -v --cov

smoke:
	pytest tests/smoke -v

lint:
	black api/ ml_pipeline/ dagster_project/
	flake8 api/ ml_pipeline/ dagster_project/
	mypy api/ ml_pipeline/ dagster_project/ --ignore-missing-imports

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov

build:
	docker build -t winter-injury-api -f docker/Dockerfile.api .
	docker build -t winter-injury-dagster -f docker/Dockerfile.dagster .

deploy:
	./scripts/deploy.sh
