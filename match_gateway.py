import asyncio
import hmac
import json
import os
import re
import time
from contextlib import suppress
from pathlib import Path

from websockets.asyncio.server import serve


BASE_DIR = Path(__file__).resolve().parent
HOST = os.getenv("MATCHER_GATEWAY_HOST", "0.0.0.0")
PORT = int(os.getenv("MATCHER_GATEWAY_PORT", "8765"))
MATCHER_TOKEN = os.getenv("MATCHER_TOKEN", "")
STATE_FILE = BASE_DIR / ".runtime" / "matcher_status.json"
REQUEST_DIR = BASE_DIR / ".runtime" / "match_requests"
JOB_DIR = BASE_DIR / ".runtime" / "match_jobs"
RESULT_DIR = BASE_DIR / ".runtime" / "match_results"
MAX_WORKER_MESSAGE_SIZE = 128 * 1024


def write_state(online: bool, worker_id: str | None = None) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "online": online,
        "workerId": worker_id,
        "updatedAt": time.time(),
    }
    temporary_file = STATE_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    temporary_file.replace(STATE_FILE)


async def keep_status_alive(worker_id: str) -> None:
    while True:
        write_state(True, worker_id)
        await asyncio.sleep(5)


async def forward_match_requests(connection) -> None:
    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        for request_file in sorted(REQUEST_DIR.glob("*.json")):
            try:
                payload = json.loads(request_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                request_file.unlink(missing_ok=True)
                continue

            await connection.send(json.dumps(payload, ensure_ascii=False))
            request_file.unlink(missing_ok=True)
            print(f"[gateway] forwarded match request: {payload.get('requestId')}", flush=True)
        await asyncio.sleep(0.2)


def save_match_result(payload: dict, worker_id: str) -> str:
    request_id = str(payload.get("requestId", ""))
    if not re.fullmatch(r"[a-f0-9]{32}", request_id):
        raise ValueError("invalid requestId")
    if not (JOB_DIR / f"{request_id}.json").is_file():
        raise ValueError("unknown requestId")

    normalized = dict(payload)
    normalized["type"] = "match_result"
    normalized["requestId"] = request_id
    normalized["workerId"] = worker_id
    normalized["receivedAt"] = time.time()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    result_file = RESULT_DIR / f"{request_id}.json"
    temporary_file = result_file.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(normalized, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_file.replace(result_file)
    return request_id


async def handle_worker(connection) -> None:
    if connection.request.path != "/ws/matcher":
        await connection.close(code=1008, reason="unsupported websocket path")
        return

    authorization = connection.request.headers.get("Authorization", "")
    expected_authorization = f"Bearer {MATCHER_TOKEN}"
    if not MATCHER_TOKEN or not hmac.compare_digest(authorization, expected_authorization):
        await connection.close(code=1008, reason="worker authentication failed")
        return

    worker_id = connection.request.headers.get("X-Worker-ID", "matcher-worker")
    print(f"[gateway] worker connected: {worker_id}", flush=True)
    write_state(True, worker_id)
    heartbeat = asyncio.create_task(keep_status_alive(worker_id))
    request_forwarder = asyncio.create_task(forward_match_requests(connection))

    try:
        async for raw_message in connection:
            if not isinstance(raw_message, str) or len(raw_message) > MAX_WORKER_MESSAGE_SIZE:
                print("[gateway] rejected oversized or binary worker response", flush=True)
                continue

            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                print("[gateway] rejected invalid worker JSON", flush=True)
                continue

            if not isinstance(payload, dict):
                print("[gateway] rejected non-object worker response", flush=True)
                continue

            message_type = payload.get("type")
            if message_type == "ack":
                print(
                    f"[gateway] worker accepted request: {payload.get('requestId')}",
                    flush=True,
                )
                continue

            if message_type != "match_result":
                print(f"[gateway] ignored worker message: {message_type}", flush=True)
                continue

            try:
                request_id = save_match_result(payload, worker_id)
                print(f"[gateway] saved match result: {request_id}", flush=True)
            except (OSError, TypeError, ValueError) as error:
                print(f"[gateway] rejected match result: {error}", flush=True)
    finally:
        heartbeat.cancel()
        request_forwarder.cancel()
        for task in (heartbeat, request_forwarder):
            with suppress(asyncio.CancelledError):
                await task
        write_state(False)
        print(f"[gateway] worker disconnected: {worker_id}", flush=True)


async def run_gateway() -> None:
    if not MATCHER_TOKEN:
        raise RuntimeError("MATCHER_TOKEN must be set before starting the production gateway")

    write_state(False)
    print(f"[gateway] listening on ws://{HOST}:{PORT}/ws/matcher", flush=True)
    try:
        async with serve(handle_worker, HOST, PORT, ping_interval=10, ping_timeout=10):
            await asyncio.Future()
    finally:
        write_state(False)


if __name__ == "__main__":
    try:
        asyncio.run(run_gateway())
    except KeyboardInterrupt:
        print("\n[gateway] stopped", flush=True)
