"""Minimal FastAPI chat app: user ⇄ persistent OpenCode session in a Modal sandbox.

One Modal sandbox is reused across every request; each user has a persistent
opencode session inside it. A chat message kicks off `client.session.chat(...)`
in the background while we tail `client.event.list()` and forward every event
(text parts, tool calls, reasoning, snapshots, …) to the client as
Server-Sent Events. When the chat call returns, we persist the user message,
the assembled assistant message and the tool-call parts to SQLite.

Run:

    uv pip install fastapi uvicorn opencode-ai modal httpx pydantic
    export LLM_API_KEY=fw_...           # or FIREWORKS_API_KEY
    export MODAL_TOKEN_ID=...
    export MODAL_TOKEN_SECRET=...
    python chat_app.py                   # serves on :8765 by default

Endpoints:

    POST /chat/{user_id}        body {"text": "..."}    →  text/event-stream
    GET  /history/{user_id}                              →  JSON list

The opencode side is reached via Modal's encrypted-port tunnel (no auth
header — the URL itself is the secret). State that has to survive process
restarts (the Modal `object_id` of the live sandbox + the per-user opencode
session id) lives in `chat.db`. Everything else is module-level globals.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx
import modal
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from httpx_sse import aconnect_sse
from pydantic import BaseModel


# ─── env loading ─────────────────────────────────────────────────────────────
# Read backend/.env (and a sibling .env if present) so `LLM_API_KEY` etc. show
# up without `set -a && . backend/.env`. Live process env wins over file values.

def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE / ".env", _HERE / "backend" / ".env"):
    _load_dotenv(_candidate)


# ─── config ──────────────────────────────────────────────────────────────────

MODAL_APP_NAME = os.environ.get("CHAT_MODAL_APP", "omoi-os-chat-app")
OPENCODE_PORT = int(os.environ.get("CHAT_OPENCODE_PORT", "4096"))
OPENCODE_PROVIDER = os.environ.get("OPENCODE_PROVIDER", "fireworks-ai")
OPENCODE_MODEL = os.environ.get(
    "OPENCODE_MODEL", "accounts/fireworks/routers/kimi-k2p5-turbo"
)
SANDBOX_TIMEOUT_SECONDS = int(os.environ.get("CHAT_SANDBOX_TIMEOUT", "86400"))
DB_PATH = Path(os.environ.get("CHAT_DB_PATH", "chat.db"))
LLM_API_KEY = os.environ.get("FIREWORKS_API_KEY") or os.environ.get("LLM_API_KEY")


# ─── sqlite ──────────────────────────────────────────────────────────────────

def _init_db() -> None:
    con = sqlite3.connect(DB_PATH)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS sandbox_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            modal_object_id TEXT NOT NULL,
            tunnel_url TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id TEXT PRIMARY KEY,
            opencode_session_id TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            parts_json TEXT,
            opencode_message_id TEXT,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_messages_user
            ON messages (user_id, created_at);
        """
    )
    con.commit()
    con.close()


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


# ─── modal sandbox bootstrap ─────────────────────────────────────────────────

# Module-level singletons. Populated on first request, reused thereafter.
_sandbox: Any = None
_tunnel_url: Optional[str] = None
_oc_client: Optional[httpx.AsyncClient] = None
_bootstrap_lock = asyncio.Lock()


def _opencode_image() -> Any:
    """The Modal image used for the chat sandbox.

    Bakes opencode at image-build time (per the proven runbook) so spawn
    latency is just sandbox-create + opencode-serve startup.
    """
    return (
        modal.Image.debian_slim()
        .apt_install("curl", "ca-certificates", "git", "unzip")
        .run_commands(
            "curl -fsSL https://opencode.ai/install | bash",
            "mkdir -p /root/.config/opencode /root/.local/share/opencode",
        )
        .env({"PATH": "/root/.opencode/bin:/usr/local/bin:/usr/bin:/bin"})
    )


async def _wait_for_health(url: str, timeout_s: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_s
    last: Optional[str] = None
    async with httpx.AsyncClient(timeout=3.0) as c:
        while time.monotonic() < deadline:
            try:
                r = await c.get(f"{url}/global/health")
                if r.status_code == 200:
                    return
                last = f"http {r.status_code}"
            except Exception as exc:  # noqa: BLE001
                last = type(exc).__name__
            await asyncio.sleep(1.5)
    raise RuntimeError(f"opencode never became healthy at {url} (last: {last})")


async def _spawn_sandbox() -> tuple[Any, str]:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY (or FIREWORKS_API_KEY) is required to populate "
            "opencode auth.json inside the sandbox"
        )

    app = await asyncio.to_thread(
        modal.App.lookup, MODAL_APP_NAME, create_if_missing=True
    )
    sandbox = await asyncio.to_thread(
        modal.Sandbox.create,
        "sleep",
        "infinity",
        app=app,
        image=_opencode_image(),
        timeout=SANDBOX_TIMEOUT_SECONDS,
        encrypted_ports=[OPENCODE_PORT],
    )

    auth_body = json.dumps(
        {OPENCODE_PROVIDER: {"type": "api", "key": LLM_API_KEY}}
    ).encode("utf-8")
    config_body = json.dumps(
        {
            "$schema": "https://opencode.ai/config.json",
            "model": f"{OPENCODE_PROVIDER}/{OPENCODE_MODEL}",
        }
    ).encode("utf-8")

    await asyncio.to_thread(
        sandbox.filesystem.write_bytes,
        auth_body,
        "/root/.local/share/opencode/auth.json",
    )
    await asyncio.to_thread(
        sandbox.filesystem.write_bytes,
        config_body,
        "/root/.config/opencode/opencode.json",
    )

    # opencode serve runs forever — spawn it nohup'd so the exec call
    # itself returns immediately.
    await asyncio.to_thread(
        sandbox.exec,
        "bash",
        "-lc",
        f"nohup opencode serve --port {OPENCODE_PORT} --hostname 0.0.0.0 "
        "> /tmp/opencode.log 2>&1 &",
    )

    tunnels = await asyncio.to_thread(sandbox.tunnels)
    url = tunnels[OPENCODE_PORT].url
    await _wait_for_health(url)
    return sandbox, url


async def _try_reattach() -> Optional[tuple[Any, str]]:
    """Resume the previously-spawned sandbox if it's still alive."""
    con = _db()
    row = con.execute(
        "SELECT modal_object_id, tunnel_url FROM sandbox_state WHERE id = 1"
    ).fetchone()
    con.close()
    if row is None:
        return None
    try:
        sandbox = await asyncio.to_thread(modal.Sandbox.from_id, row["modal_object_id"])
    except Exception:
        return None
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{row['tunnel_url']}/global/health")
        if r.status_code != 200:
            return None
    except Exception:
        return None
    return sandbox, row["tunnel_url"]


async def _get_sandbox() -> tuple[Any, str, httpx.AsyncClient]:
    global _sandbox, _tunnel_url, _oc_client
    if _sandbox is not None and _tunnel_url and _oc_client is not None:
        return _sandbox, _tunnel_url, _oc_client

    async with _bootstrap_lock:
        if _sandbox is not None and _tunnel_url and _oc_client is not None:
            return _sandbox, _tunnel_url, _oc_client

        reattached = await _try_reattach()
        if reattached is not None:
            sandbox, url = reattached
        else:
            sandbox, url = await _spawn_sandbox()
            con = _db()
            con.execute(
                "INSERT INTO sandbox_state (id, modal_object_id, tunnel_url, created_at) "
                "VALUES (1, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "modal_object_id = excluded.modal_object_id, "
                "tunnel_url = excluded.tunnel_url, "
                "created_at = excluded.created_at",
                (sandbox.object_id, url, time.time()),
            )
            con.commit()
            con.close()

        client = httpx.AsyncClient(base_url=url, timeout=600.0)
        _sandbox, _tunnel_url, _oc_client = sandbox, url, client
        return sandbox, url, client


# ─── per-user opencode session ───────────────────────────────────────────────

async def _get_or_create_user_session(
    user_id: str, client: httpx.AsyncClient
) -> str:
    con = _db()
    row = con.execute(
        "SELECT opencode_session_id FROM user_sessions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    con.close()

    if row is not None:
        r = await client.get("/session")
        r.raise_for_status()
        live_ids = {s["id"] for s in r.json()}
        if row["opencode_session_id"] in live_ids:
            return row["opencode_session_id"]

    # opencode 1.14.x rejects empty bodies on POST /session — send `{}`.
    r = await client.post("/session", json={})
    r.raise_for_status()
    fresh_id = r.json()["id"]
    con = _db()
    con.execute(
        "INSERT INTO user_sessions (user_id, opencode_session_id, created_at) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "opencode_session_id = excluded.opencode_session_id, "
        "created_at = excluded.created_at",
        (user_id, fresh_id, time.time()),
    )
    con.commit()
    con.close()
    return fresh_id


# ─── persistence ─────────────────────────────────────────────────────────────

def _persist_message(
    user_id: str,
    role: str,
    content: str,
    parts: Optional[list],
    opencode_message_id: Optional[str] = None,
) -> str:
    mid = str(uuid.uuid4())
    con = _db()
    con.execute(
        "INSERT INTO messages (id, user_id, role, content, parts_json, "
        "opencode_message_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            mid,
            user_id,
            role,
            content,
            json.dumps(parts) if parts is not None else None,
            opencode_message_id,
            time.time(),
        ),
    )
    con.commit()
    con.close()
    return mid


# ─── streaming helpers ───────────────────────────────────────────────────────

def _sse(event: str, data: Any) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _event_session_id(evt: dict) -> Optional[str]:
    """Pull the session id off any opencode event shape we care about."""
    props = evt.get("properties") or {}
    if not isinstance(props, dict):
        return None
    if isinstance(props.get("sessionID"), str):
        return props["sessionID"]
    part = props.get("part") or {}
    if isinstance(part, dict) and isinstance(part.get("sessionID"), str):
        return part["sessionID"]
    info = props.get("info") or {}
    if isinstance(info, dict):
        if isinstance(info.get("sessionID"), str):
            return info["sessionID"]
        # session.updated info uses `id` for the session itself.
        if isinstance(info.get("id"), str) and info["id"].startswith("ses_"):
            return info["id"]
    return None


def _event_for_session(
    evt: dict, opencode_session_id: str, parts_by_id: dict[str, dict]
) -> Optional[str]:
    """Filter + serialize one opencode event for the SSE response.

    Returns the SSE-formatted string to forward, or None to skip. Mutates
    `parts_by_id` so the caller can assemble the final assistant message
    from accumulated part state when the chat POST returns.
    """
    etype = evt.get("type")
    if not isinstance(etype, str):
        return None
    if _event_session_id(evt) != opencode_session_id:
        return None

    props = evt.get("properties") or {}
    part = props.get("part") if isinstance(props, dict) else None
    if etype == "message.part.updated" and isinstance(part, dict):
        pid = part.get("id") or str(uuid.uuid4())
        parts_by_id[pid] = part
    elif etype == "message.part.removed" and isinstance(part, dict):
        parts_by_id.pop(part.get("id", ""), None)

    return _sse(etype, props if isinstance(props, dict) else {})


# ─── FastAPI ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_: FastAPI):
    _init_db()
    yield


app = FastAPI(lifespan=lifespan, title="omoi-os chat (modal+opencode)")


class ChatRequest(BaseModel):
    text: str


@app.post("/chat/{user_id}")
async def chat(user_id: str, body: ChatRequest):
    if not body.text.strip():
        raise HTTPException(400, "text is required")

    _, _, client = await _get_sandbox()
    opencode_session_id = await _get_or_create_user_session(user_id, client)

    user_message_id = _persist_message(user_id, "user", body.text, parts=None)

    async def stream() -> AsyncIterator[str]:
        parts_by_id: dict[str, dict] = {}
        # Inbound events from opencode's global /event SSE stream; the
        # event-reader task pushes filtered/forwardable lines onto this queue,
        # the generator drains it.
        event_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        async def _read_events() -> None:
            try:
                async with aconnect_sse(client, "GET", "/event") as ev_source:
                    async for sse_evt in ev_source.aiter_sse():
                        try:
                            evt = json.loads(sse_evt.data)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        forwarded = _event_for_session(
                            evt, opencode_session_id, parts_by_id
                        )
                        if forwarded is not None:
                            await event_queue.put(forwarded)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await event_queue.put(_sse("event.error", {"error": str(exc)}))

        async def _send_chat() -> dict:
            r = await client.post(
                f"/session/{opencode_session_id}/message",
                json={
                    "providerID": OPENCODE_PROVIDER,
                    "modelID": OPENCODE_MODEL,
                    "parts": [{"type": "text", "text": body.text}],
                },
                timeout=600.0,
            )
            r.raise_for_status()
            return r.json()

        # Start the event reader first so we don't miss the first delta.
        reader_task = asyncio.create_task(_read_events())
        # Tiny grace so the SSE handshake is established before the message POST.
        await asyncio.sleep(0.05)
        chat_task = asyncio.create_task(_send_chat())

        yield _sse(
            "chat.started",
            {
                "user_id": user_id,
                "user_message_id": user_message_id,
                "opencode_session_id": opencode_session_id,
            },
        )

        try:
            while True:
                getter = asyncio.create_task(event_queue.get())
                done, _pending = await asyncio.wait(
                    {getter, chat_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if getter in done:
                    yield getter.result()
                    if chat_task.done():
                        # Drain whatever's already buffered, then exit.
                        while not event_queue.empty():
                            yield event_queue.get_nowait()
                        break
                else:
                    getter.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await getter
                    # Give the event reader one last beat to flush any final
                    # `session.idle` / `message.updated` for the turn.
                    await asyncio.sleep(0.2)
                    while not event_queue.empty():
                        yield event_queue.get_nowait()
                    break

            try:
                final = await chat_task
            except Exception as exc:  # noqa: BLE001
                yield _sse("error", {"error": str(exc)})
                return

            assistant_message_id = (final.get("info") or {}).get("id")
            # Prefer parts the server returned with the final body — they're
            # authoritative. Fall back to the streamed accumulator if not.
            final_parts = final.get("parts") or [
                p
                for p in parts_by_id.values()
                if p.get("messageID") == assistant_message_id
            ]
            assistant_text = "\n".join(
                p.get("text", "")
                for p in final_parts
                if isinstance(p, dict) and p.get("type") == "text" and p.get("text")
            ).strip()

            stored_id = _persist_message(
                user_id,
                "assistant",
                assistant_text,
                parts=final_parts,
                opencode_message_id=assistant_message_id,
            )
            yield _sse(
                "done",
                {
                    "stored_message_id": stored_id,
                    "opencode_message_id": assistant_message_id,
                    "tool_call_count": sum(
                        1
                        for p in final_parts
                        if isinstance(p, dict) and p.get("type") == "tool"
                    ),
                },
            )
        finally:
            reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await reader_task
            if not chat_task.done():
                chat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await chat_task

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/history/{user_id}")
async def history(user_id: str):
    con = _db()
    rows = con.execute(
        "SELECT id, role, content, parts_json, opencode_message_id, created_at "
        "FROM messages WHERE user_id = ? ORDER BY created_at",
        (user_id,),
    ).fetchall()
    con.close()
    return [
        {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "parts": json.loads(r["parts_json"]) if r["parts_json"] else None,
            "opencode_message_id": r["opencode_message_id"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.get("/healthz")
async def healthz():
    return {
        "ok": _sandbox is not None,
        "tunnel_url": _tunnel_url,
        "modal_object_id": getattr(_sandbox, "object_id", None),
    }


# ─── main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "chat_app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8765")),
        reload=False,
    )
