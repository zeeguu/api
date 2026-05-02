import os
import logging

import requests


logger = logging.getLogger(__name__)

DEFAULT_ASR_SERVICE_TIMEOUT = float(os.environ.get("ASR_SERVICE_TIMEOUT", "30"))
LOCAL_DEV_ASR_SERVICE_URL = "http://127.0.0.1:5002"


class ASRServiceError(RuntimeError):
    """Base exception for dedicated ASR worker failures."""


class ASRServiceNotConfigured(ASRServiceError):
    """Raised when no ASR worker endpoint is configured."""


class ASRServiceRequestError(ASRServiceError):
    """Raised when an ASR worker request fails."""


def parse_asr_language_overrides(raw_value):
    """
    Parse per-language routing exceptions like:

        da=http://asr-da,de=http://asr-de

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
            logger.warning("Ignoring invalid ASR language override entry: %s", entry)
            continue

        language_code, service_url = entry.split("=", 1)
        language_code = language_code.strip().casefold()
        service_url = service_url.strip().rstrip("/")

        if not language_code or not service_url:
            logger.warning("Ignoring incomplete ASR language override entry: %s", entry)
            continue

        mapping[language_code] = service_url

    return mapping


def in_development_context():
    """Return True when local dev defaults should be enabled."""
    return os.environ.get("FLASK_DEBUG") == "1"


def _clean_service_url(raw_value):
    return (raw_value or "").strip().rstrip("/") or None


def _asr_service_url_from_environment():
    service_url = _clean_service_url(os.environ.get("ASR_SERVICE_URL"))

    if not service_url and in_development_context():
        service_url = LOCAL_DEV_ASR_SERVICE_URL

    return service_url


def _asr_language_overrides_from_environment():
    return parse_asr_language_overrides(os.environ.get("ASR_LANGUAGE_OVERRIDES", ""))


ASR_SERVICE_URL = _asr_service_url_from_environment()
ASR_LANGUAGE_OVERRIDE_MAP = _asr_language_overrides_from_environment()


def configured_asr_service_urls():
    """Return configured worker URLs captured at module import."""
    configured_urls = {}
    if ASR_SERVICE_URL:
        configured_urls["*"] = ASR_SERVICE_URL
    configured_urls.update(ASR_LANGUAGE_OVERRIDE_MAP)
    return configured_urls


def get_asr_service_url(
    language_code,
    service_url=None,
    language_overrides=None,
):
    service_url = (
        ASR_SERVICE_URL
        if service_url is None
        else _clean_service_url(service_url)
    )
    language_overrides = (
        ASR_LANGUAGE_OVERRIDE_MAP
        if language_overrides is None
        else language_overrides
    )

    if language_code:
        language_url = language_overrides.get(str(language_code).casefold())
        if language_url:
            return language_url

    return service_url


def transcribe_with_asr_worker(
    audio_bytes,
    filename,
    content_type,
    language_code,
    service_url=None,
    language_overrides=None,
    timeout=None,
):
    resolved_service_url = get_asr_service_url(
        language_code,
        service_url=service_url,
        language_overrides=language_overrides,
    )
    if not resolved_service_url:
        raise ASRServiceNotConfigured(
            "No ASR worker configured. Set ASR_SERVICE_URL or "
            "ASR_LANGUAGE_OVERRIDES."
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
            f"{resolved_service_url}/transcribe",
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
