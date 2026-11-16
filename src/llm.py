"""Extract text-only symptom candidates with a local Ollama model.

The model never receives questionnaires, report metadata, or reference answers.
This client makes one request: failures are recorded by callers, not replaced by
rules or fabricated empty results. See https://docs.ollama.com/api/chat and
https://docs.ollama.com/capabilities/structured-outputs for the API contract.
"""

from __future__ import annotations

import hashlib
from http.client import HTTPException
import ipaddress
import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import ValidationError

from src.schema import CandidateBatch


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "extraction.txt"


class ExtractionError(RuntimeError):
    """A failed extraction, with an explicit machine-readable failure code."""

    def __init__(self, code: str, message: str, *, raw_response: str | None = None):
        super().__init__(message)
        self.code = code
        self.raw_response = raw_response


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Local requests must not inherit a machine's HTTP proxy or follow redirects.
urlopen = build_opener(ProxyHandler({}), _NoRedirect()).open


def _chat_url(base_url: str) -> str:
    """Require a loopback server for this explicitly local-only prototype."""
    if not isinstance(base_url, str):
        raise ExtractionError("invalid_config", "base_url must be a loopback HTTP(S) URL.")
    try:
        parsed = urlsplit(base_url)
        hostname = parsed.hostname
        parsed.port  # Validate malformed or out-of-range ports before connecting.
        is_loopback = hostname == "localhost"
        if hostname and not is_loopback:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError as exc:
        raise ExtractionError("invalid_config", "base_url must be a loopback HTTP(S) URL.") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not is_loopback
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ExtractionError(
            "invalid_config",
            "base_url must be a loopback HTTP(S) origin without credentials, a path, or query parameters.",
        )
    return f"{parsed.scheme}://{parsed.netloc}/api/chat"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_candidates(
    text: str,
    *,
    model: str,
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 120.0,
) -> dict:
    """Return validated candidates, run metadata, and exact assistant content.

    This validates structure only. Evidence checks and deterministic normalization
    belong to the next pipeline stage. No network request is retried automatically.
    """
    if not isinstance(text, str):
        raise ExtractionError("invalid_input", "Patient text must be a string.")
    if not isinstance(model, str) or not model.strip():
        raise ExtractionError("invalid_config", "model must be a nonempty model name.")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ExtractionError("invalid_config", "timeout must be a positive finite number of seconds.")
    endpoint = _chat_url(base_url)
    schema = CandidateBatch.model_json_schema()
    prompt = PROMPT_PATH.read_text(encoding="utf-8").rstrip()
    system_message = prompt + "\n\nOutput JSON schema:\n" + json.dumps(schema, sort_keys=True)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": json.dumps({"patient_text": text}, ensure_ascii=False)},
        ],
        "stream": False,
        "format": schema,
        "options": {"temperature": 0},
    }
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        raise ExtractionError(
            "http_error",
            f"Ollama returned HTTP {exc.code}. Check the local server and installed model; redirects are disabled.",
        ) from exc
    except (URLError, TimeoutError, OSError, HTTPException) as exc:
        raise ExtractionError(
            "network_error",
            "Could not complete the local Ollama request. Check that the server is running and the timeout is sufficient.",
        ) from exc
    try:
        api_response = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ExtractionError("invalid_api_response", "Ollama returned an invalid JSON response envelope.") from exc
    if not isinstance(api_response, dict):
        raise ExtractionError("invalid_api_response", "Ollama response envelope must be a JSON object.")
    if api_response.get("error"):
        raise ExtractionError("server_error", "Ollama reported an error instead of an extraction.")
    message = api_response.get("message")
    raw_response = message.get("content") if isinstance(message, dict) else None
    if not isinstance(raw_response, str):
        raw_response = None
    if api_response.get("refusal") or (isinstance(message, dict) and message.get("refusal")):
        raise ExtractionError("refusal", "The model refused the extraction request.", raw_response=raw_response)
    if api_response.get("done") is not True or api_response.get("done_reason") in {"length", "max_tokens"}:
        raise ExtractionError(
            "truncated_response",
            "Ollama did not finish the extraction; partial candidates were not accepted.",
            raw_response=raw_response,
        )
    if raw_response is None or not raw_response.strip():
        raise ExtractionError("missing_content", "Ollama returned no assistant text for extraction.")
    try:
        json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ExtractionError(
            "invalid_json", "Assistant content is not valid JSON.", raw_response=raw_response
        ) from exc
    try:
        batch = CandidateBatch.model_validate_json(raw_response)
    except ValidationError as exc:
        # Do not include Pydantic's input-value dump in the exception message.
        raise ExtractionError(
            "invalid_schema",
            "Assistant JSON does not match the candidate schema.",
            raw_response=raw_response,
        ) from exc
    return {
        "candidates": batch.model_dump(mode="json")["candidates"],
        "metadata": {
            "backend": "ollama",
            "model": api_response.get("model", model),
            "requested_model": model,
            "prompt_sha256": _sha256(system_message),
            "response_sha256": _sha256(raw_response),
            "done_reason": api_response.get("done_reason"),
            "prompt_eval_count": api_response.get("prompt_eval_count"),
            "eval_count": api_response.get("eval_count"),
            "total_duration_ns": api_response.get("total_duration"),
        },
        "raw_response": raw_response,
    }
