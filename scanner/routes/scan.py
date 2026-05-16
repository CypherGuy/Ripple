import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from scanner.agent import scan_service

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


@router.post("/scan")
async def scan(payload: ScanPayload):
    async def scan_one(svc: ServiceEntry) -> list[dict]:
        hits = await asyncio.to_thread(
            scan_service,
            svc.model_dump(),
            payload.pattern,
            payload.incident_context,
        )
        return [{"service": svc.name, **h} for h in hits]

    results = await asyncio.gather(*[scan_one(svc) for svc in payload.services])

    return {
        "incident_context": payload.incident_context,
        "hits": [h for hits in results for h in hits],
    }
