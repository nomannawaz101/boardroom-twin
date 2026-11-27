import pytest
from fastapi.testclient import TestClient

import config
from app import app

client = TestClient(app)


def test_page_shows_product_name() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert config.APP_NAME in response.text


def test_stylesheet_is_served() -> None:
    assert client.get("/static/css/style.css").status_code == 200


def test_health_reports_mode_features_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "sample")
    body = client.get("/api/health").json()
    assert body == {
        "status": "ok",
        "mode": "sample",
        "features": config.FEATURES,
        "version": config.APP_VERSION,
        "agents": 14,
        "tools": 3,
    }


def test_unknown_run_mode_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_MODE", "turbo")
    assert client.get("/api/health").json()["mode"] == config.DEFAULT_RUN_MODE


def test_version_uses_deployed_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.COMMIT_ENV_VAR, "abc123")
    assert client.get("/api/version").json() == {"commit": "abc123"}


def test_version_without_commit_says_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.COMMIT_ENV_VAR, raising=False)
    assert client.get("/api/version").json() == {"commit": config.UNKNOWN_COMMIT}
