from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import boto3
from pydantic import ValidationError

from .config import get_config
from .core_client import CoreClient
from .doc_text_service import BrowserManager, DocTextService
from .logging_utils import log_event
from .models import QueueDocTask

logger = logging.getLogger("kad-parser-doc.ymq")


class YmqConsumer:
    def __init__(self) -> None:
        self.cfg = get_config()
        self.core = CoreClient()
        self.browser = BrowserManager()
        self.doc_service = DocTextService(self.browser)
        self._client = boto3.client(
            "sqs",
            endpoint_url=self.cfg.ymq_endpoint_url,
            aws_access_key_id=self.cfg.ymq_access_key_id,
            aws_secret_access_key=self.cfg.ymq_secret_access_key,
            region_name=self.cfg.ymq_region,
        )

    async def _receive_one(self) -> Optional[dict[str, Any]]:
        response = await asyncio.to_thread(
            self._client.receive_message,
            QueueUrl=self.cfg.ymq_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=self.cfg.ymq_wait_time_seconds,
            VisibilityTimeout=self.cfg.ymq_visibility_timeout,
        )
        messages = response.get("Messages") or []
        if not messages:
            return None
        return messages[0]

    async def _delete(self, receipt_handle: str) -> None:
        await asyncio.to_thread(
            self._client.delete_message,
            QueueUrl=self.cfg.ymq_queue_url,
            ReceiptHandle=receipt_handle,
        )

    async def _change_visibility(self, receipt_handle: str) -> None:
        await asyncio.to_thread(
            self._client.change_message_visibility,
            QueueUrl=self.cfg.ymq_queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=self.cfg.ymq_visibility_timeout,
        )

    async def _visibility_extender(self, receipt_handle: str, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await asyncio.sleep(max(10, self.cfg.visibility_refresh_seconds))
            if stop_event.is_set():
                return
            try:
                await self._change_visibility(receipt_handle)
                log_event("visibility_extended", {"status": "ok"})
            except Exception as exc:
                logger.warning("ChangeMessageVisibility failed: %s", exc)

    def _parse_body(self, raw_body: str) -> QueueDocTask:
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            logger.exception("Invalid YMQ JSON body: raw_body=%s", raw_body)
            raise
        if not isinstance(body, dict):
            raise ValueError("YMQ message body must be object")
        return QueueDocTask(**body)

    async def _process_message(self, message: dict[str, Any]) -> None:
        receipt = message.get("ReceiptHandle")
        if not receipt:
            raise RuntimeError("Message has no ReceiptHandle")

        task = self._parse_body(message.get("Body") or "{}")
        stop_event = asyncio.Event()
        extender_task = asyncio.create_task(self._visibility_extender(receipt, stop_event))
        try:
            fetch_result = await asyncio.to_thread(self.doc_service.fetch_document_text, task)
        finally:
            stop_event.set()
            extender_task.cancel()
            try:
                await extender_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        if fetch_result.ok and fetch_result.text_base64:
            success_payload: dict[str, Any] = {
                "job_uuid": task.job_uuid,
                "doc_id": task.doc_id,
                "doc_uuid": task.doc_uuid,
                "text_base64": fetch_result.text_base64,
                "start_ip": fetch_result.start_ip,
                "service_id": self.cfg.service_id,
            }
            notified = self.core.notify_document_text(success_payload, require_success=True)
            if notified:
                await self._delete(receipt)
                log_event(
                    "ymq_message_deleted",
                    {
                        "job_uuid": task.job_uuid,
                        "doc_id": task.doc_id,
                        "doc_uuid": task.doc_uuid,
                        "status": "ok",
                    },
                )
                return
            error_payload = {
                "job_uuid": task.job_uuid,
                "doc_id": task.doc_id,
                "doc_uuid": task.doc_uuid,
                "status": "error",
                "message": "CORE не подтвердил success=true для document-text",
                "start_ip": fetch_result.start_ip,
                "service_id": self.cfg.service_id,
            }
            self.core.notify_document_text(error_payload, require_success=False)
            return

        error_payload = {
            "job_uuid": task.job_uuid,
            "doc_id": task.doc_id,
            "doc_uuid": task.doc_uuid,
            "status": "error",
            "message": fetch_result.message or "Не удалось получить текст документа",
            "start_ip": fetch_result.start_ip,
            "service_id": self.cfg.service_id,
        }
        self.core.notify_document_text(error_payload, require_success=False)

    async def run_forever(self) -> None:
        log_event("consumer_started", {"status": "ok"})
        while True:
            try:
                message = await self._receive_one()
                if not message:
                    self.browser.close_browser()
                    continue
                await self._process_message(message)
            except asyncio.CancelledError:
                raise
            except ValidationError as exc:
                logger.error("YMQ message validation error: %s", exc)
                await asyncio.sleep(2)
            except Exception as exc:
                logger.exception("Consumer loop error: %s", exc)
                await asyncio.sleep(2)

