from __future__ import annotations

from datetime import datetime
from typing import Optional

import boto3

from .config import get_config
from .logging_utils import log_event


class ObjectStorageClient:
    def __init__(self) -> None:
        self.cfg = get_config()
        self._client = boto3.client(
            "s3",
            endpoint_url=self.cfg.object_storage_endpoint,
            aws_access_key_id=self.cfg.object_storage_access_key_id,
            aws_secret_access_key=self.cfg.object_storage_secret_access_key,
            region_name=self.cfg.object_storage_region,
        )

    @staticmethod
    def _normalize_prefix(storage_prefix: str) -> str:
        return str(storage_prefix).strip().strip("/")

    def _build_object_key(self, storage_prefix: str, doc_uuid: str) -> str:
        prefix = self._normalize_prefix(storage_prefix)
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        filename = f"{doc_uuid}_{timestamp}.html"
        if prefix:
            return f"{prefix}/html/{filename}"
        return f"html/{filename}"

    def upload_document_html(self, storage_prefix: str, doc_uuid: str, html: str) -> Optional[str]:
        bucket = self.cfg.object_storage_bucket
        if not bucket:
            log_event("object_storage_upload", {"status": "error", "message": "OBJECT_STORAGE_BUCKET is empty"})
            return None
        object_key = self._build_object_key(storage_prefix, doc_uuid)
        try:
            self._client.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=html.encode("utf-8"),
                ContentType="text/html; charset=utf-8",
            )
            log_event(
                "object_storage_upload",
                {"status": "ok", "doc_uuid": doc_uuid, "path": object_key},
            )
            return object_key
        except Exception as exc:
            log_event(
                "object_storage_upload",
                {
                    "status": "error",
                    "doc_uuid": doc_uuid,
                    "path": object_key,
                    "message": str(exc),
                    "exception_type": type(exc).__name__,
                },
            )
            return None
