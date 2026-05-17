import json
import logging
import os
from typing import Any

from .config import get_config


def setup_logging() -> None:
    cfg = get_config()
    log_dir = os.path.dirname(cfg.log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(cfg.log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    for noisy in ("urllib3", "playwright", "botocore", "boto3", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(event: str, payload: dict[str, Any]) -> None:
    logger = logging.getLogger("kad-parser-doc")
    cfg = get_config()
    if cfg.debug:
        logger.debug("%s %s", event, json.dumps(payload, ensure_ascii=False))
        return
    compact_keys = (
        "job_uuid",
        "doc_id",
        "doc_uuid",
        "status",
        "message",
        "ok",
        "success",
        "path",
        "url",
        "exception_type",
    )
    compact = {k: payload.get(k) for k in compact_keys if k in payload}
    logger.info("%s %s", event, json.dumps(compact, ensure_ascii=False))

