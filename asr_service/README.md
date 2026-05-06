# ASR Service

This directory contains one implementation of Zeeguu's ASR worker contract.
The main API treats the worker as a black box:

```http
POST /transcribe
```

Form fields:

- `file`: audio upload
- `language_code`: requested transcription language

Response:

```json
{
  "success": true,
  "transcription": "det var godt"
}
```

The current worker loads `nvidia/parakeet-rnnt-110m-da-dk` for Danish, but the
HTTP contract is intentionally generic. A future Whisper, Faster-Whisper, or
cloud-backed worker should preserve the same request and response shape.

## Main API Configuration

The API routes transcription requests to one default backend, with optional
per-language overrides:

```env
ASR_SERVICE_URL=http://asr
ASR_LANGUAGE_OVERRIDES=da=http://asr-da
ASR_SERVICE_TIMEOUT=30
```

Most deployments should only set `ASR_SERVICE_URL`. Use
`ASR_LANGUAGE_OVERRIDES` only when a specific language needs a different
backend.

In local Flask debug mode, the API falls back to
`http://127.0.0.1:5002` when no ASR URL is configured. Production does not use a
localhost fallback.

## Worker Configuration

The worker listens on `ASR_SERVICE_PORT` in containers. The Docker image defaults
to port `80`; direct local `python app.py` development can continue to use
`ASR_SERVICE_PORT=5002`.

Supported languages are declared with:

```env
ASR_SUPPORTED_LANGUAGES=da
```

Use a comma-separated list for a multilingual worker, or `*` for a worker that
accepts all language codes.
