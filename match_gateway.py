import asyncio
import hmac
import json
import os
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
            print(f"[gateway] received from worker: {raw_message}", flush=True)
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
