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

PREVIEW_STATE_FILE = BASE_DIR / ".runtime" / "preview_status.json"
PREVIEW_REQUEST_DIR = BASE_DIR / ".runtime" / "preview_requests"
PREVIEW_JOB_DIR = BASE_DIR / ".runtime" / "preview_jobs"
PREVIEW_RESULT_DIR = BASE_DIR / ".runtime" / "preview_results"

MAX_WORKER_MESSAGE_SIZE = 128 * 1024


def write_state(
    online: bool,
    worker_id: str | None = None,
    state_file: Path = STATE_FILE,
) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "online": online,
        "workerId": worker_id,
        "updatedAt": time.time(),
    }
    temporary_file = state_file.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    temporary_file.replace(state_file)


def write_worker_states(online: bool, worker_id: str | None = None) -> None:
    for state_file in (STATE_FILE, PREVIEW_STATE_FILE):
        write_state(online, worker_id, state_file)


async def keep_status_alive(worker_id: str) -> None:
    while True:
        write_worker_states(True, worker_id)
        await asyncio.sleep(5)


async def forward_requests(connection) -> None:
    request_sources = (
        (REQUEST_DIR, "matcher"),
        (PREVIEW_REQUEST_DIR, "preview"),
    )
    for request_dir, _ in request_sources:
        request_dir.mkdir(parents=True, exist_ok=True)

    while True:
        for request_dir, label in request_sources:
            for request_file in sorted(request_dir.glob("*.json")):
                try:
                    payload = json.loads(request_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    request_file.unlink(missing_ok=True)
                    continue

                await connection.send(json.dumps(payload, ensure_ascii=False))
                request_file.unlink(missing_ok=True)
                print(
                    f"[gateway:{label}] forwarded request: {payload.get('requestId')}",
                    flush=True,
                )
        await asyncio.sleep(0.2)


def save_worker_result(
    payload: dict,
    worker_id: str,
    *,
    result_type: str,
    job_dir: Path,
    result_dir: Path,
) -> str:
    request_id = str(payload.get("requestId", ""))
    if not re.fullmatch(r"[a-f0-9]{32}", request_id):
        raise ValueError("invalid requestId")
    if not (job_dir / f"{request_id}.json").is_file():
        raise ValueError("unknown requestId")

    normalized = dict(payload)
    normalized["type"] = result_type
    normalized["requestId"] = request_id
    normalized["workerId"] = worker_id
    normalized["receivedAt"] = time.time()

    result_dir.mkdir(parents=True, exist_ok=True)
    result_file = result_dir / f"{request_id}.json"
    temporary_file = result_file.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(normalized, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_file.replace(result_file)
    return request_id


def save_match_result(payload: dict, worker_id: str) -> str:
    return save_worker_result(
        payload,
        worker_id,
        result_type="match_result",
        job_dir=JOB_DIR,
        result_dir=RESULT_DIR,
    )


def save_preview_result(payload: dict, worker_id: str) -> str:
    return save_worker_result(
        payload,
        worker_id,
        result_type="preview_result",
        job_dir=PREVIEW_JOB_DIR,
        result_dir=PREVIEW_RESULT_DIR,
    )


def worker_channel(path: str) -> dict | None:
    if path == "/ws/matcher":
        return {
            "label": "worker",
            "token": MATCHER_TOKEN,
            "defaultWorkerId": "lace-worker",
            "resultHandlers": {
                "match_result": save_match_result,
                "preview_result": save_preview_result,
            },
        }
    return None


async def handle_worker(connection) -> None:
    channel = worker_channel(connection.request.path)
    if channel is None:
        await connection.close(code=1008, reason="unsupported websocket path")
        return

    authorization = connection.request.headers.get("Authorization", "")
    expected_authorization = f"Bearer {channel['token']}"
    if not channel["token"] or not hmac.compare_digest(authorization, expected_authorization):
        await connection.close(code=1008, reason="worker authentication failed")
        return

    label = channel["label"]
    worker_id = connection.request.headers.get("X-Worker-ID", channel["defaultWorkerId"])
    print(f"[gateway:{label}] worker connected: {worker_id}", flush=True)
    write_worker_states(True, worker_id)
    heartbeat = asyncio.create_task(keep_status_alive(worker_id))
    request_forwarder = asyncio.create_task(forward_requests(connection))

    try:
        async for raw_message in connection:
            if not isinstance(raw_message, str) or len(raw_message) > MAX_WORKER_MESSAGE_SIZE:
                print(f"[gateway:{label}] rejected oversized or binary response", flush=True)
                continue

            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                print(f"[gateway:{label}] rejected invalid worker JSON", flush=True)
                continue

            if not isinstance(payload, dict):
                print(f"[gateway:{label}] rejected non-object worker response", flush=True)
                continue

            message_type = payload.get("type")
            if message_type == "ack":
                print(
                    f"[gateway:{label}] worker accepted request: {payload.get('requestId')}",
                    flush=True,
                )
                continue

            save_result = channel["resultHandlers"].get(message_type)
            if save_result is None:
                print(f"[gateway:{label}] ignored worker message: {message_type}", flush=True)
                continue

            try:
                request_id = save_result(payload, worker_id)
                print(f"[gateway:{message_type}] saved result: {request_id}", flush=True)
            except (OSError, TypeError, ValueError) as error:
                print(f"[gateway:{label}] rejected result: {error}", flush=True)
    finally:
        heartbeat.cancel()
        request_forwarder.cancel()
        for task in (heartbeat, request_forwarder):
            with suppress(asyncio.CancelledError):
                await task
        write_worker_states(False)
        print(f"[gateway:{label}] worker disconnected: {worker_id}", flush=True)


async def run_gateway() -> None:
    if not MATCHER_TOKEN:
        raise RuntimeError("MATCHER_TOKEN must be set before starting the gateway")

    write_worker_states(False)
    print(f"[gateway] listening on ws://{HOST}:{PORT}/ws/matcher", flush=True)
    try:
        async with serve(handle_worker, HOST, PORT, ping_interval=10, ping_timeout=10):
            await asyncio.Future()
    finally:
        write_worker_states(False)


if __name__ == "__main__":
    try:
        asyncio.run(run_gateway())
    except KeyboardInterrupt:
        print("\n[gateway] stopped", flush=True)
