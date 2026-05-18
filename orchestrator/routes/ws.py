import os
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from orchestrator.ws_manager import register, unregister

router = APIRouter()


def _allowed_origins() -> set[str]:
    origins = {"http://localhost:3000", "http://localhost:3001"}
    dashboard_url = os.environ.get("DASHBOARD_URL", "")
    if dashboard_url:
        origins.add(dashboard_url)
    return origins


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin", "")
    if origin and origin not in _allowed_origins():
        await ws.close(code=1008)
        return
    await ws.accept()
    register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        unregister(ws)
