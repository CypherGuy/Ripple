import os
from urllib.parse import urlparse
import httpx


def validate_callback_url(url: str) -> None:
    orchestrator_url = os.environ.get("ORCHESTRATOR_URL", "")
    allowed_host = urlparse(orchestrator_url).netloc
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.netloc != allowed_host:
        raise ValueError(f"callback_url not in allowlist: {url!r}")


def emit_event(callback_url: str | None, data: dict) -> None:
    if not callback_url:
        return
    try:
        validate_callback_url(callback_url)
        httpx.post(callback_url, json=data, timeout=5)
    except ValueError:
        pass
    except Exception:
        pass
