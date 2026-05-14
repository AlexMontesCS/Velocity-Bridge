"""
Velocity Bridge Relay

Small HTTPS-friendly relay for syncing clipboard data when the phone and
desktop are not on the same local network. Deploy behind TLS on any public
host; both clients only need outbound HTTPS.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


STORE_PATH = Path(os.environ.get("VELOCITY_RELAY_STORE", "/tmp/velocity-relay.sqlite3"))
MESSAGE_TTL_SECONDS = int(os.environ.get("VELOCITY_RELAY_MESSAGE_TTL_SECONDS", "86400"))
MAX_LIMIT = 100

app = FastAPI(
    title="Velocity Bridge Relay",
    description="Outbound HTTPS relay for Velocity Bridge clipboard messages",
    version="0.1.0",
)


class RelayPayload(BaseModel):
    token: str = Field(min_length=8)
    kind: Literal["clipboard", "command", "response"] = "clipboard"
    type: str | None = None
    content: str | None = None
    image: str | None = None
    filename: str | None = None
    command: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@contextmanager
def db() -> Any:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STORE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pairs (
                pair_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair_id TEXT NOT NULL,
                target TEXT NOT NULL,
                kind TEXT NOT NULL,
                correlation_id TEXT,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_pair_target_id "
            "ON messages(pair_id, target, id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_expires_at "
            "ON messages(expires_at)"
        )


def cleanup_expired(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM messages WHERE expires_at <= ?", (time.time(),))


def clear_phone_clipboard_queue(conn: sqlite3.Connection, pair_id: str) -> None:
    conn.execute(
        "DELETE FROM messages WHERE pair_id = ? AND target = 'phone' AND kind = 'clipboard'",
        (pair_id,),
    )


def require_pair(conn: sqlite3.Connection, pair_id: str, token: str) -> None:
    if not pair_id or len(pair_id) > 80:
        raise HTTPException(status_code=400, detail="Invalid pair id")

    token_hash = _hash_token(token)
    row = conn.execute("SELECT token_hash FROM pairs WHERE pair_id = ?", (pair_id,)).fetchone()

    if row is None:
        conn.execute(
            "INSERT INTO pairs(pair_id, token_hash, created_at) VALUES (?, ?, ?)",
            (pair_id, token_hash, time.time()),
        )
        return

    if row["token_hash"] != token_hash:
        raise HTTPException(status_code=403, detail="Invalid relay token")


def row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "target": row["target"],
        "kind": row["kind"],
        "correlation_id": row["correlation_id"],
        "payload": json.loads(row["payload_json"]),
        "created_at": row["created_at"],
    }


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "Velocity Bridge Relay"}


@app.post("/v1/pairs/{pair_id}/messages/{target}")
async def post_message(
    pair_id: str,
    target: Literal["desktop", "phone"],
    payload: RelayPayload,
) -> dict[str, Any]:
    init_db()
    now = time.time()
    correlation_id = payload.correlation_id or payload.request_id
    payload_dict = payload.dict(exclude={"token"}, exclude_none=True)

    with db() as conn:
        cleanup_expired(conn)
        require_pair(conn, pair_id, payload.token)
        if target == "phone" and payload.kind == "clipboard":
            clear_phone_clipboard_queue(conn, pair_id)
        cursor = conn.execute(
            """
            INSERT INTO messages(
                pair_id, target, kind, correlation_id, payload_json, created_at, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pair_id,
                target,
                payload.kind,
                correlation_id,
                json.dumps(payload_dict, separators=(",", ":")),
                now,
                now + MESSAGE_TTL_SECONDS,
            ),
        )
        message_id = cursor.lastrowid

    return {"status": "queued", "id": message_id, "expires_in": MESSAGE_TTL_SECONDS}


@app.get("/v1/pairs/{pair_id}/messages/{target}")
async def get_messages(
    pair_id: str,
    target: Literal["desktop", "phone"],
    token: str = Query(min_length=8),
    after: int = 0,
    limit: int = 25,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    init_db()
    limit = max(1, min(limit, MAX_LIMIT))

    with db() as conn:
        cleanup_expired(conn)
        require_pair(conn, pair_id, token)

        params: list[Any] = [pair_id, target, after]
        correlation_filter = ""
        if correlation_id:
            correlation_filter = "AND correlation_id = ?"
            params.append(correlation_id)
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT id, target, kind, correlation_id, payload_json, created_at
            FROM messages
            WHERE pair_id = ? AND target = ? AND id > ?
            {correlation_filter}
            ORDER BY id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()

    messages = [row_to_message(row) for row in rows]
    return {
        "status": "success",
        "messages": messages,
        "cursor": messages[-1]["id"] if messages else after,
    }


@app.get("/v1/pairs/{pair_id}/phone/latest_clipboard")
async def phone_latest_clipboard(
    pair_id: str,
    token: str = Query(min_length=8),
) -> dict[str, Any]:
    init_db()

    with db() as conn:
        cleanup_expired(conn)
        require_pair(conn, pair_id, token)

        row = conn.execute(
            """
            SELECT id, target, kind, correlation_id, payload_json, created_at
            FROM messages
            WHERE pair_id = ? AND target = 'phone' AND kind = 'clipboard'
            ORDER BY id DESC
            LIMIT 1
            """,
            (pair_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="No clipboard queued")

    message = row_to_message(row)
    return {
        "status": "success",
        "message": message,
    }


@app.post("/v1/pairs/{pair_id}/phone/send")
async def phone_send(pair_id: str, payload: RelayPayload) -> dict[str, Any]:
    payload.kind = "clipboard"
    return await post_message(pair_id, "desktop", payload)


@app.post("/v1/pairs/{pair_id}/phone/request_clipboard")
async def phone_request_clipboard(pair_id: str, payload: RelayPayload) -> dict[str, Any]:
    request_id = payload.request_id or str(uuid.uuid4())
    command = RelayPayload(
        token=payload.token,
        kind="command",
        command="get_clipboard",
        request_id=request_id,
        correlation_id=request_id,
    )
    queued = await post_message(pair_id, "desktop", command)
    return {"status": "queued", "request_id": request_id, "message_id": queued["id"]}

