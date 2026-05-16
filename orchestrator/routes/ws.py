from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from orchestrator.ws_manager import register, unregister

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        unregister(ws)
