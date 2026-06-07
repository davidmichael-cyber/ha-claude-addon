"""Claude Bridge — FastAPI proxy between Home Assistant and OpenClaw.

Surfaces:
  GET  /                       Lovelace panel (chat UI)
  GET  /health                 Liveness check
  GET  /v1/models              OpenAI-compat model list
  POST /v1/chat/completions    HA context-enriched proxy to OpenClaw
  POST /ask                    Simple prompt→text for HA automations
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from ha_context import get_ha_context

log = logging.getLogger(__name__)

# Supervisor writes add-on config to /data/options.json
_opts: dict = {}
_opts_path = Path("/data/options.json")
if _opts_path.exists():
    try:
        _opts = json.loads(_opts_path.read_text())
    except Exception:
        pass

OPENCLAW_URL = (_opts.get("openclaw_url") or os.environ.get("OPENCLAW_URL", "http://100.84.106.76:18789")).rstrip("/")
OPENCLAW_TOKEN = _opts.get("openclaw_token") or os.environ.get("OPENCLAW_TOKEN", "")
HA_API_URL = os.environ.get("HA_API_URL", "http://supervisor/core")
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN", "")
PORT = int(os.environ.get("PORT", 7123))

PANEL_HTML = Path(__file__).parent / "static" / "index.html"

app = FastAPI(title="Claude Bridge", version="1.0.0", docs_url=None, redoc_url=None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _openclaw_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {OPENCLAW_TOKEN}",
        "Content-Type": "application/json",
    }


async def _inject_ha_context(messages: list[dict]) -> list[dict]:
    context = None
    try:
        context = await get_ha_context(HA_API_URL, HA_TOKEN)
    except Exception as exc:
        log.warning("HA context fetch failed: %s", exc)

    ha_block = (
        "You are Nova, running inside Home Assistant for David and Ramsey at unit #1017.\n"
        "You have full access to control this home via your existing HA tools.\n"
    )
    if context:
        ha_block += f"\nCurrent home state:\n{context}\n"

    out = list(messages)
    if out and out[0].get("role") == "system":
        out[0] = {**out[0], "content": ha_block + "\n" + out[0]["content"]}
    else:
        out.insert(0, {"role": "system", "content": ha_block})
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"ok": True, "openclaw": OPENCLAW_URL}


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [{"id": "nova", "object": "model", "created": 0, "owned_by": "openclaw"}],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body: dict = await request.json()
    body["messages"] = await _inject_ha_context(body.get("messages", []))
    body.setdefault("user", "ha-nova")  # stable session routing in OpenClaw

    streaming = body.get("stream", False)

    async with httpx.AsyncClient(timeout=120) as client:
        if streaming:
            async def _stream():
                async with client.stream(
                    "POST",
                    f"{OPENCLAW_URL}/v1/chat/completions",
                    json=body,
                    headers=_openclaw_headers(),
                ) as r:
                    async for chunk in r.aiter_bytes():
                        yield chunk

            return StreamingResponse(_stream(), media_type="text/event-stream")

        resp = await client.post(
            f"{OPENCLAW_URL}/v1/chat/completions",
            json=body,
            headers=_openclaw_headers(),
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type="application/json",
    )


@app.post("/ask")
async def ask(request: Request):
    """Automation-friendly endpoint. POST {prompt: str} → {response: str}."""
    body: dict = await request.json()
    prompt: str = (body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "prompt is required"}, status_code=400)

    messages = await _inject_ha_context([{"role": "user", "content": prompt}])
    payload = {
        "model": "nova",
        "messages": messages,
        "user": "ha-nova",
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{OPENCLAW_URL}/v1/chat/completions",
            json=payload,
            headers=_openclaw_headers(),
        )

    data: dict = resp.json()
    text: str = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return {"response": text}


@app.get("/", response_class=HTMLResponse)
@app.get("/panel", response_class=HTMLResponse)
async def panel():
    return HTMLResponse(PANEL_HTML.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    uvicorn.run(app, host="0.0.0.0", port=PORT)
