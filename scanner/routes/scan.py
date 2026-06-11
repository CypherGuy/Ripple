import asyncio
import concurrent.futures
import os
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from scanner.agent import scan_service
from scanner.streaming import emit_event

router = APIRouter()

# Launch agents on a staggered schedule rather than all at once. Firing 12 ADK
# agents simultaneously stampedes the Gemini API (rate-limit/503), which made
# every ADK scan time out and fall back to regex. Spacing the launches keeps
# only ~1-2 agents calling the model at any moment so the real ADK path
# actually completes, and makes the dashboard tiles light up progressively
# instead of all flipping at once. Tunable live via SCAN_STAGGER_SECONDS.
_STAGGER_SECONDS = float(os.environ.get("SCAN_STAGGER_SECONDS", "1.2"))


class ServiceEntry(BaseModel):
    name: str
    repo: str | None = None
    gitlab_namespace: str


class ScanPayload(BaseModel):
    pattern: str
    incident_context: dict
    services: list[ServiceEntry]
    callback_url: str | None = None


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/scan")
async def scan(payload: ScanPayload):
    # One thread per service, sized exactly to this request - no global pool cap.
    # asyncio.to_thread uses the event loop's shared default executor; on Cloud Run
    # that pool can be as small as 6, batching a 12-service scan into two rounds.
    # Using run_in_executor with a dedicated pool guarantees all services start in
    # parallel regardless of how many there are.
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=len(payload.services))

    async def scan_one(svc: ServiceEntry, idx: int) -> list[dict]:
        # Stagger the start so agents don't all hit Gemini in the same instant.
        if idx and _STAGGER_SECONDS > 0:
            await asyncio.sleep(idx * _STAGGER_SECONDS)

        emit_event(payload.callback_url, {
            "event": "agent_started",
            "service": svc.name,
            "timestamp": _ts(),
        })

        try:
            hits = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    scan_service,
                    svc.model_dump(),
                    payload.pattern,
                    payload.incident_context,
                ),
                timeout=60,
            )
        except (asyncio.TimeoutError, Exception):
            hits = []
        tagged = [{**h, "service": svc.name} for h in hits]

        if tagged:
            for hit in tagged:
                emit_event(payload.callback_url, {
                    "event": "hit_found",
                    "service": svc.name,
                    "timestamp": _ts(),
                    "data": {
                        "file_path": hit.get("file_path"),
                        "matching_lines": hit.get("matching_lines", []),
                        "confidence": hit.get("confidence", 0),
                    },
                })
        else:
            emit_event(payload.callback_url, {
                "event": "no_hit",
                "service": svc.name,
                "timestamp": _ts(),
            })

        return tagged

    try:
        results = await asyncio.gather(
            *[scan_one(svc, i) for i, svc in enumerate(payload.services)])
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return {
        "incident_context": payload.incident_context,
        "hits": [h for hits in results for h in hits],
    }
