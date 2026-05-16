import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from orchestrator.main import app
    return TestClient(app)


def test_close_mrs_endpoint_exists(client):
    with patch("orchestrator.routes.admin.close_all_ripple_mrs", return_value={"closed": 0, "errors": 0}):
        r = client.post("/admin/close-mrs")
    assert r.status_code == 200


def test_close_mrs_returns_closed_count(client):
    with patch("orchestrator.routes.admin.close_all_ripple_mrs", return_value={"closed": 7, "errors": 0}):
        r = client.post("/admin/close-mrs")
    assert r.json()["closed"] == 7


def test_close_mrs_calls_gitlab_per_service():
    from fix_factory.tools.gitlab_mr import _GITLAB_BASE
    import httpx

    closed = []
    def mock_get(url, **kwargs):
        r = MagicMock()
        if "merge_requests" in url:
            r.json.return_value = [
                {"iid": 1, "source_branch": "ripple/fix-dt-4821-20260516"},
                {"iid": 2, "source_branch": "main"},  # not a ripple branch — should be skipped
            ]
        else:
            r.json.return_value = {}
        r.raise_for_status = MagicMock()
        return r

    def mock_put(url, **kwargs):
        closed.append(url)
        r = MagicMock()
        r.raise_for_status = MagicMock()
        return r

    with patch("orchestrator.routes.admin.httpx") as mock_httpx:
        mock_httpx.get = mock_get
        mock_httpx.put = mock_put
        from orchestrator.routes.admin import close_all_ripple_mrs
        result = close_all_ripple_mrs(["cypherguy-group/ripple-demo/auth-service"], "fake-token")

    assert any("merge_requests/1" in url for url in closed)
    assert not any("merge_requests/2" in url for url in closed)
