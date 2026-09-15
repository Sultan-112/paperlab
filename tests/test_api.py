import importlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from libs.config import settings
from services.runtime import Runtime


@pytest.fixture
def client(tmp_path, monkeypatch):
    main = importlib.import_module("apps.api.main")
    runtime_module = importlib.import_module("services.runtime")
    db_module = importlib.import_module("libs.db")
    engine = create_engine("sqlite:///" + str(tmp_path / "api.db"), connect_args={"check_same_thread": False})
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "Session", sessions)
    monkeypatch.setattr(main, "Session", sessions)
    monkeypatch.setattr(runtime_module, "Session", sessions)
    monkeypatch.setattr(settings, "token", "test-token")
    monkeypatch.setattr(settings, "mode", "replay")
    monkeypatch.setattr(main, "runtime", Runtime())
    with TestClient(main.app) as c:
        c.headers["Authorization"] = "Bearer test-token"
        yield c
    engine.dispose()


def test_auth_and_search(client):
    assert client.get("/api/state", headers={"Authorization": ""}).status_code == 401
    rows = client.get("/api/assets?market=KSA").json()
    assert len(rows) == 2
    assert client.get("/health/live").json()["execution"] == "SIMULATED_ONLY"


def test_ws_orders_and_kill(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"token": "test-token"})
        state = ws.receive_json()
        assert state["mode"] == "replay"
        assert "US:AAPL" in state["quotes"]
    order = {"asset_id": "US:AAPL", "side": "BUY", "quantity": "1", "order_id": str(uuid.uuid4())}
    assert client.post("/api/orders", json=order).status_code == 200
    assert client.post("/api/orders", json=order).status_code == 200
    assert len(client.get("/api/state").json()["trades"]) == 1
    client.put("/api/kill-switch", json={"enabled": True})
    order["order_id"] = str(uuid.uuid4())
    assert client.post("/api/orders", json=order).status_code == 400


def test_cross_origin_and_input_validation(client):
    assert (
        client.put(
            "/api/kill-switch", json={"enabled": True}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/orders",
            json={"asset_id": "US:AAPL", "side": "BUY", "quantity": "NaN", "order_id": "abcdefgh"},
        ).status_code
        == 422
    )
    assert client.put("/api/replay", json={"paused": True, "speed": 0}).status_code == 422


def test_ollama_fallback(client, monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:1")
    result = client.post("/api/explain/US:AAPL").json()
    assert result["source"] == "deterministic fallback"


def test_automation_and_replay_controls(client):
    assert client.get("/api/state").json()["autopaper"] is False
    assert client.put("/api/autopaper", json={"enabled": True}).status_code == 200
    assert client.get("/api/state").json()["autopaper"] is True
    client.put("/api/autopaper", json={"enabled": False})
    client.put("/api/replay", json={"paused": True, "speed": 5})
    state = client.get("/api/state").json()
    assert state["replay"]["paused"] is True and state["replay"]["speed"] == 5
