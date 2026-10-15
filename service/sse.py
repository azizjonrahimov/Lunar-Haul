"""Server-Sent Events for GET /v2/runs/{id}/events.

The stream replays every run_events row after Last-Event-ID (or ?after=seq), then follows the table
until a terminal event (done / failed) is seen, polling the database every settings.sse_poll_s and
sending a comment ping every settings.sse_ping_s so proxies keep the connection open. Event ids are
the run_events seq, so a reconnecting EventSource resumes without gaps.

sse-starlette's EventSourceResponse is used when importable (it adds its own ping and handles client
disconnects and server shutdown); otherwise a plain StreamingResponse with text/event-stream.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, Optional

from starlette.responses import StreamingResponse

try:  # optional dependency
    from sse_starlette.sse import EventSourceResponse  # type: ignore
except Exception:  # pragma: no cover - depends on the environment
    EventSourceResponse = None  # type: ignore

TERMINAL = ("done", "failed")
SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def format_event(kind: str, data: Any, event_id: Optional[int] = None) -> str:
    """One SSE frame (text)."""
    payload = data if isinstance(data, str) else json.dumps(data, allow_nan=False, separators=(",", ":"))
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {kind}")
    for ln in payload.splitlines() or [""]:
        lines.append(f"data: {ln}")
    return "\n".join(lines) + "\n\n"


def _run_finished(db, run_id: str) -> bool:
    row = db.get_run(run_id)
    return row is None or row["status"] in TERMINAL


async def run_events(db, run_id: str, after_seq: int, poll_s: float, ping_s: float,
                     max_idle_s: Optional[float] = None) -> AsyncIterator[Dict[str, Any]]:
    """Yields dicts {event, data, id} (or {comment}) for sse-starlette, in run_events order.

    Ends after a terminal event, or (a client resuming after it) when the run is finished and two
    consecutive polls brought nothing new; the worker writes the status before the done/failed event, so
    the second poll catches that last event."""
    seq = int(after_seq)
    idle = 0.0
    since_ping = 0.0
    quiet_after_finish = 0
    while True:
        rows = await asyncio.to_thread(db.events_after, run_id, seq)
        terminal = False
        for r in rows:
            seq = int(r["seq"])
            payload = json.loads(r["payload_json"])
            payload["t"] = r["t"]
            yield {"event": r["kind"], "data": json.dumps(payload, allow_nan=False, separators=(",", ":")), "id": str(seq)}
            if r["kind"] in TERMINAL:
                terminal = True
        if terminal:
            return
        if rows:
            idle = 0.0
            quiet_after_finish = 0
        else:
            idle += poll_s
            if max_idle_s is not None and idle >= max_idle_s:
                return
            if await asyncio.to_thread(_run_finished, db, run_id):
                quiet_after_finish += 1
                if quiet_after_finish >= 2:
                    return
        since_ping += poll_s
        if since_ping >= ping_s:
            since_ping = 0.0
            yield {"comment": "ping"}
        await asyncio.sleep(poll_s)


async def _as_text(gen: AsyncIterator[Dict[str, Any]]) -> AsyncIterator[str]:
    async for item in gen:
        if "comment" in item:
            yield f": {item['comment']}\n\n"
        else:
            yield format_event(item["event"], item["data"], int(item["id"]) if item.get("id") else None)


def sse_response(db, run_id: str, after_seq: int, poll_s: float, ping_s: float, use_sse_starlette: bool = True):
    gen = run_events(db, run_id, after_seq, poll_s, ping_s)
    if use_sse_starlette and EventSourceResponse is not None:
        return EventSourceResponse(gen, ping=int(max(1, ping_s)), headers=dict(SSE_HEADERS))
    return StreamingResponse(_as_text(gen), media_type="text/event-stream", headers=dict(SSE_HEADERS))
