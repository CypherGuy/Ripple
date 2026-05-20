import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from scanner.agent import scan_service
from scanner.streaming import emit_event

router = APIRouter()


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
    # All 12 services scan simultaneously — semaphore removed.
    # Each service has its own 60s timeout, so the total pipeline time
    # is bounded by the slowest single service, not slowest * batches.
    async def scan_one(svc: ServiceEntry) -> list[dict]:
        if True:
            emit_event(payload.callback_url, {
                "event": "agent_started",
                "service": svc.name,
                "timestamp": _ts(),
            })

            try:
                hits = await asyncio.wait_for(
                    asyncio.to_thread(
                        scan_service,
                        svc.model_dump(),
                        payload.pattern,
                        payload.incident_context,
                    ),
                    timeout=60,
                )
            except asyncio.TimeoutError:
                hits = []
            tagged = [{"service": svc.name, **h} for h in hits]

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

    results = await asyncio.gather(*[scan_one(svc) for svc in payload.services])

    return {
        "incident_context": payload.incident_context,
        "hits": [h for hits in results for h in hits],
    }
