"""Run smoke checks against a deployed API URL."""
import argparse
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PAYLOAD = {
    "temperature": -15.5,
    "wind_speed": 25.0,
    "wind_chill": -28.0,
    "precipitation": 2.5,
    "snow_depth": 30.0,
    "hour": 8,
    "day_of_week": 1,
    "month": 1,
    "neighborhood": "Unknown-Neighborhood",
    "ses_index": 0.45,
    "infrastructure_quality": 0.70,
}


def read_json(url: str, headers: dict | None = None, body: dict | None = None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    with urlopen(req, timeout=30) as resp:  # nosec B310 - explicit trusted URL input
        return resp.status, json.loads(resp.read().decode("utf-8"))


def read_text(url: str):
    with urlopen(url, timeout=30) as resp:  # nosec B310 - explicit trusted URL input
        return resp.status, resp.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Smoke test deployed API")
    parser.add_argument("--base-url", required=True, help="Base URL, e.g. https://demo.onrender.com")
    parser.add_argument("--token", required=True, help="Bearer token")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    token = args.token

    try:
        status, _ = read_json(f"{base_url}/health")
        assert status == 200, "/health did not return 200"
        print("PASS /health")

        status, docs = read_text(f"{base_url}/docs")
        assert status == 200 and "swagger-ui" in docs.lower(), "/docs not reachable"
        print("PASS /docs")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        status, pred = read_json(f"{base_url}/predict", headers=headers, body=PAYLOAD)
        assert status == 200, "/predict did not return 200"
        assert "probability" in pred and "risk_level" in pred, "Prediction payload incomplete"
        print("PASS /predict")
        print("Smoke checks passed.")
    except (AssertionError, HTTPError, OSError, ValueError) as exc:
        print(f"Smoke checks failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
