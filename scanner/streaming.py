import httpx


def emit_event(callback_url: str | None, data: dict) -> None:
    if not callback_url:
        return
    try:
        httpx.post(callback_url, json=data, timeout=5)
    except Exception:
        pass
