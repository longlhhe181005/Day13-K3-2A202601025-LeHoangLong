import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.challenge import load_challenge, ordered_queries
from app.cli import configure_utf8_stdio

BASE_URL = "http://127.0.0.1:8000"
QUERIES = Path("data/sample_queries.jsonl")


def send_request(client: httpx.Client, payload: dict) -> None:
    try:
        start = time.perf_counter()
        r = client.post(f"{BASE_URL}/chat", json=payload)
        latency = (time.perf_counter() - start) * 1000
        print(f"[{r.status_code}] {r.json().get('correlation_id')} | {payload['feature']} | {latency:.1f}ms")
    except Exception as e:
        print(f"Error: {e}")


def check_tracing(client: httpx.Client) -> None:
    try:
        health = client.get(f"{BASE_URL}/health", timeout=5.0).json()
    except Exception as e:
        print(f"Warning: could not reach {BASE_URL}/health ({e}). Is the API running?")
        return

    if not health.get("tracing_enabled"):
        print(
            f"Warning: {BASE_URL} reports tracing_enabled=false. "
            "Traces will NOT show up on Langfuse. Restart the API with "
            "`uvicorn app.main:app --reload --env-file .env` (make sure "
            "LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST are set in .env)."
        )
        return

    env_host = None
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("LANGFUSE_HOST"):
                env_host = line.split("=", 1)[1].strip().strip('"')

    api_host = health.get("langfuse_host")
    if env_host and api_host and env_host != api_host:
        print(
            f"Warning: API process is sending traces to {api_host}, but .env "
            f"currently has LANGFUSE_HOST={env_host}. The API was likely started "
            "before .env was last edited (or without --env-file) — restart it "
            "with `uvicorn app.main:app --reload --env-file .env` so traces land "
            "in the right Langfuse project."
        )


def main() -> None:
    global BASE_URL
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent requests")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"API base URL to send requests to (default: {BASE_URL})",
    )
    parser.add_argument(
        "--challenge",
        action="store_true",
        help="Dùng input chính thức trong config/challenge.json sau khi được release.",
    )
    args = parser.parse_args()
    BASE_URL = args.base_url

    if args.challenge:
        challenge = load_challenge()
        payloads = ordered_queries(challenge)
        print(f"Challenge: {challenge.challenge_id} | Cohort: {challenge.cohort}")
    else:
        payloads = [
            json.loads(line)
            for line in QUERIES.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    
    with httpx.Client(timeout=30.0) as client:
        check_tracing(client)
        if args.concurrency > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                futures = [executor.submit(send_request, client, payload) for payload in payloads]
                concurrent.futures.wait(futures)
        else:
            for payload in payloads:
                send_request(client, payload)


if __name__ == "__main__":
    main()
