from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class QueueDocTask(BaseModel):
    model_config = ConfigDict(extra="ignore")
    job_uuid: str
    doc_id: int
    doc_uuid: str
    storage_prefix: str


class DocFetchResult(BaseModel):
    ok: bool
    html: Optional[str] = None
    message: Optional[str] = None
    start_ip: Optional[str] = None

