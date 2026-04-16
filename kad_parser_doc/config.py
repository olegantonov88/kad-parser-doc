import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _env_optional_int(name: str) -> Optional[int]:
    value = os.getenv(name)
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _log_level_from_env() -> str:
    raw = str(os.getenv("LOG_LEVEL", "")).strip().upper()
    if raw in ("DEBUG", "INFO", "WARNING", "ERROR"):
        return raw
    return "DEBUG" if _env_bool("DEBUG", False) else "INFO"


@dataclass
class AppConfig:
    ras_base_url: str
    core_api_url: str
    core_api_token: str
    service_id: Optional[int]
    headless: bool
    log_file: str
    log_level: str
    debug: bool
    ymq_enabled: bool
    ymq_endpoint_url: str
    ymq_queue_url: str
    ymq_access_key_id: str
    ymq_secret_access_key: str
    ymq_region: str
    ymq_wait_time_seconds: int
    ymq_visibility_timeout: int
    visibility_refresh_seconds: int
    check_ip_enabled: bool
    check_ip_url: str
    check_ip_bearer: str
    object_storage_endpoint: str
    object_storage_bucket: str
    object_storage_access_key_id: str
    object_storage_secret_access_key: str
    object_storage_region: str


def get_config() -> AppConfig:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    default_log_file = os.path.join(project_root, "logs", "parser-doc.log")
    return AppConfig(
        ras_base_url=os.getenv("RAS_BASE_URL", "https://ras.arbitr.ru"),
        core_api_url=os.getenv("CORE_API_URL", "http://localhost:8000"),
        core_api_token=os.getenv("CORE_API_TOKEN", ""),
        service_id=_env_optional_int("SERVICE_ID"),
        headless=_env_bool("HEADLESS", False),
        log_file=os.getenv("LOG_FILE", default_log_file),
        log_level=_log_level_from_env(),
        debug=_env_bool("DEBUG", False),
        ymq_enabled=_env_bool("ENABLE_YMQ", True),
        ymq_endpoint_url=os.getenv("YMQ_ENDPOINT_URL", ""),
        ymq_queue_url=os.getenv("YMQ_QUEUE_URL", ""),
        ymq_access_key_id=os.getenv("YMQ_ACCESS_KEY_ID", ""),
        ymq_secret_access_key=os.getenv("YMQ_SECRET_ACCESS_KEY", ""),
        ymq_region=os.getenv("YMQ_REGION", "ru-central1"),
        ymq_wait_time_seconds=int(os.getenv("YMQ_WAIT_TIME_SECONDS", "20")),
        ymq_visibility_timeout=int(os.getenv("YMQ_VISIBILITY_TIMEOUT", "300")),
        visibility_refresh_seconds=int(os.getenv("VISIBILITY_REFRESH_SECONDS", "180")),
        check_ip_enabled=_env_bool("CHECK_IP_ENABLED", False),
        check_ip_url=os.getenv("CHECK_IP_URL", ""),
        check_ip_bearer=os.getenv("CHECK_IP_BEARER", ""),
        object_storage_endpoint=os.getenv("OBJECT_STORAGE_ENDPOINT", "https://storage.yandexcloud.net"),
        object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET", ""),
        object_storage_access_key_id=os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID", ""),
        object_storage_secret_access_key=os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", ""),
        object_storage_region=os.getenv("OBJECT_STORAGE_REGION", "ru-central1"),
    )

