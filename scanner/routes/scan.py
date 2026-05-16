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
    async def scan_one(svc: ServiceEntry) -> list[dict]:
        emit_event(payload.callback_url, {
            "event": "agent_started",
            "service": svc.name,
            "timestamp": _ts(),
        })

        hits = await asyncio.to_thread(
            scan_service,
            svc.model_dump(),
            payload.pattern,
            payload.incident_context,
        )
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
