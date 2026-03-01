from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_config
from .logging_utils import setup_logging
from .ymq_consumer import YmqConsumer

setup_logging()
cfg = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.consumer_task = None
    if cfg.ymq_enabled:
        consumer = YmqConsumer()
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

