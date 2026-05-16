import json
from fastapi.websockets import WebSocket

_connections: set[WebSocket] = set()


def register(ws: WebSocket) -> None:
    _connections.add(ws)


def unregister(ws: WebSocket) -> None:
    _connections.discard(ws)


async def broadcast_event(data: dict) -> None:
    dead = set()
    for ws in _connections:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)
