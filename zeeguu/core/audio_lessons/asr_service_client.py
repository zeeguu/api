import os
import logging

import requests


logger = logging.getLogger(__name__)

DEFAULT_ASR_SERVICE_TIMEOUT = float(os.environ.get("ASR_SERVICE_TIMEOUT", "30"))
LOCAL_DEV_ASR_SERVICE_URLS = "da=http://127.0.0.1:5002"


class ASRServiceError(RuntimeError):
    """Base exception for dedicated ASR worker failures."""


class ASRServiceNotConfigured(ASRServiceError):
    """Raised when no ASR worker is configured for a language."""


class ASRServiceRequestError(ASRServiceError):
    """Raised when an ASR worker request fails."""


def parse_asr_service_urls(raw_value):
    """
    Parse a mapping like:

        da=http://asr,de=http://asr

    into a dict keyed by language code.
    """
    mapping = {}

    if not raw_value:
        return mapping

    for entry in raw_value.replace("\n", ",").replace(";", ",").split(","):
        entry = entry.strip()
        if not entry:
            continue

        if "=" not in entry:
            logger.warning("Ignoring invalid ASR service mapping entry: %s", entry)
            continue

        language_code, service_url = entry.split("=", 1)
        language_code = language_code.strip().casefold()
        service_url = service_url.strip().rstrip("/")

        if not language_code or not service_url:
            logger.warning("Ignoring incomplete ASR service mapping entry: %s", entry)
            continue

        mapping[language_code] = service_url

    return mapping


def in_development_context():
    """Return True when local dev defaults should be enabled."""
    flask_env = os.environ.get("FLASK_ENV", "").strip().casefold()
    return flask_env == "development"


def configured_asr_service_urls():
    """Return configured worker URLs, using localhost fallback only in development."""
    raw_value = os.environ.get("ASR_SERVICE_URLS", "")

    if not raw_value and in_development_context():
        raw_value = LOCAL_DEV_ASR_SERVICE_URLS

    return parse_asr_service_urls(raw_value)


def get_asr_service_url(language_code, service_url_map=None):
    if not language_code:
        return None

    service_url_map = service_url_map or configured_asr_service_urls()
    return service_url_map.get(str(language_code).casefold())


def transcribe_with_asr_worker(
    audio_bytes,
    filename,
    content_type,
    language_code,
    service_url_map=None,
    timeout=None,
):
    service_url = get_asr_service_url(language_code, service_url_map=service_url_map)
    if not service_url:
        raise ASRServiceNotConfigured(
            f"No ASR worker configured for language '{language_code}'"
        )

    files = {
        "file": (
            filename or "recording.webm",
            audio_bytes,
            content_type or "application/octet-stream",
        )
    }
    data = {"language_code": language_code or ""}

    try:
        response = requests.post(
            f"{service_url}/transcribe",
            files=files,
            data=data,
            timeout=timeout or DEFAULT_ASR_SERVICE_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise ASRServiceRequestError(
            f"ASR worker request failed for language '{language_code}': {exc}"
        ) from exc
