from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from .config import get_config
from .logging_utils import setup_logging
from .state_manager import StateManager
from .ymq_consumer import YmqConsumer

setup_logging()
cfg = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state_manager = StateManager()
    app.state.state_manager = state_manager
    app.state.consumer_task = None
    if cfg.ymq_enabled:
        consumer = YmqConsumer(state_manager=state_manager)
        app.state.consumer_task = asyncio.create_task(consumer.run_forever())
    yield
    consumer_task = app.state.consumer_task
    if consumer_task is not None:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)


@app.get("/api/ping")
async def ping():
    return {"message": "pong", "ymq_enabled": cfg.ymq_enabled}


@app.get("/api/status")
async def api_status(
    request: Request,
    authorization: str | None = Header(default=None),
):
    if cfg.status_bearer_token is None:
        raise HTTPException(status_code=500, detail="STATUS_BEARER_TOKEN is not configured")
    if authorization is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=403, detail="Forbidden")
    token = authorization[len(prefix):].strip()
    expected = cfg.status_bearer_token
    if len(token) != len(expected):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Forbidden")
    state_manager: StateManager = request.app.state.state_manager
    return {
        "is_running": state_manager.is_running(),
        "current_task_id": state_manager.get_current_task_id(),
    }
