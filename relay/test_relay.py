from fastapi.testclient import TestClient

import server


def test_phone_send_and_desktop_poll(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "STORE_PATH", tmp_path / "relay.sqlite3")

    with TestClient(server.app) as client:
        queued = client.post(
            "/v1/pairs/test-pair/phone/send",
            json={"token": "12345678", "type": "text", "content": "hello"},
        )
        assert queued.status_code == 200

        polled = client.get(
            "/v1/pairs/test-pair/messages/desktop",
            params={"token": "12345678"},
        )
        assert polled.status_code == 200
        data = polled.json()
        assert data["messages"][0]["payload"]["content"] == "hello"


def test_wrong_token_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "STORE_PATH", tmp_path / "relay.sqlite3")

    with TestClient(server.app) as client:
        client.post(
            "/v1/pairs/test-pair/phone/send",
            json={"token": "12345678", "type": "text", "content": "hello"},
        )

        response = client.get(
            "/v1/pairs/test-pair/messages/desktop",
            params={"token": "abcdefgh"},
        )
        assert response.status_code == 403

