"""Reference OpenAI-compatible gateway: auth, routing, JSON guard and tracing."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse


MODEL = os.environ.get("SENSIX_MODEL_ID", "gpt-oss-120b")
EXPECTED_KEY = os.environ["SENSIX_GATEWAY_API_KEY"]
UPSTREAMS = tuple(url.rstrip("/") for url in os.environ.get("VLLM_UPSTREAMS", "http://vllm:8000").split(","))
IN_FLIGHT: dict[str, int] = defaultdict(int)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5)) as client:
        app.state.client = client
        yield


app = FastAPI(title="SENSIX OpenAI Gateway", version="0.1.0", lifespan=lifespan)


def require_key(authorization: str | None) -> None:
    if authorization != f"Bearer {EXPECTED_KEY}":
        raise HTTPException(status_code=401, detail={"error": {"message": "Invalid API key", "type": "authentication_error"}})


async def target() -> str:
    """Least-in-flight among healthy upstreams; replace with shared state for multi-node."""
    candidates = sorted(UPSTREAMS, key=lambda upstream: IN_FLIGHT[upstream])
    for upstream in candidates:
        try:
            response = await app.state.client.get(f"{upstream}/health", timeout=2)
            if response.is_success:
                return upstream
        except httpx.HTTPError:
            continue
    raise HTTPException(status_code=503, detail={"error": {"message": "No healthy model worker", "type": "server_error"}})


@app.get("/health")
async def health() -> dict[str, Any]:
    healthy = []
    for upstream in UPSTREAMS:
        try:
            healthy.append((await app.state.client.get(f"{upstream}/health", timeout=2)).is_success)
        except httpx.HTTPError:
            healthy.append(False)
    return {"status": "ok" if any(healthy) else "degraded", "version": "0.1.0", "checks": {"workers": healthy}}


@app.get("/v1/models")
async def models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_key(authorization)
    return {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "sensix"}]}


@app.post("/v1/chat/completions")
async def chat(request: Request, authorization: str | None = Header(default=None)):
    require_key(authorization)
    payload = await request.json()
    payload["model"] = MODEL
    trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
    upstream = await target()
    IN_FLIGHT[upstream] += 1
    started = time.perf_counter()
    headers = {"x-trace-id": trace_id}
    try:
        if payload.get("stream"):
            upstream_request = app.state.client.build_request("POST", f"{upstream}/v1/chat/completions", json=payload, headers=headers)
            upstream_response = await app.state.client.send(upstream_request, stream=True)
            if upstream_response.status_code >= 400:
                body = await upstream_response.aread()
                await upstream_response.aclose()
                return JSONResponse(status_code=upstream_response.status_code, content={"error": {"message": body.decode(errors="replace")[:1000], "type": "upstream_error"}})

            async def sse():
                try:
                    async for chunk in upstream_response.aiter_raw():
                        yield chunk
                finally:
                    await upstream_response.aclose()
                    IN_FLIGHT[upstream] -= 1

            return StreamingResponse(sse(), media_type="text/event-stream", headers={"X-Trace-ID": trace_id, "Cache-Control": "no-cache"})

        response = await app.state.client.post(f"{upstream}/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        return JSONResponse(content=response.json(), headers={"X-Trace-ID": trace_id, "X-Request-Latency-Ms": str(round((time.perf_counter() - started) * 1000))})
    except httpx.HTTPStatusError as error:
        return JSONResponse(status_code=error.response.status_code, content={"error": {"message": "Model upstream rejected the request", "type": "upstream_error", "traceId": trace_id}})
    except httpx.HTTPError:
        return JSONResponse(status_code=502, content={"error": {"message": "Model upstream request failed", "type": "upstream_error", "traceId": trace_id}})
    finally:
        # A successful streaming response releases its own slot when the SSE stream closes.
        # Failed streams never reach that generator and must release here.
        if not payload.get("stream") or "upstream_response" not in locals():
            IN_FLIGHT[upstream] -= 1
