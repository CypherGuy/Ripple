import pytest


@pytest.fixture(autouse=True)
def reset_webhook_rate_limiter():
    """Reset the webhook rate limiter before each test so tests don't interfere."""
    import orchestrator.routes.webhook as wh
    wh._last_webhook_time = None
    yield
    wh._last_webhook_time = None
