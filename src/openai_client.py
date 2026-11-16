"""Text-only extraction through the OpenAI Responses API.

The client shares the local client's prompt, candidate contract, and failure
type. It sends one request to a fixed HTTPS endpoint without retries, redirects,
or ambient proxies. Gold and questionnaire data never enter this interface.

API contract: https://developers.openai.com/api/docs/guides/structured-outputs
Reference: https://developers.openai.com/api/reference/resources/responses/methods/create
"""

from __future__ import annotations

import hashlib
from http.client import HTTPException
import json
import math
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import ValidationError

from src.llm import ExtractionError, PROMPT_PATH
from src.schema import CandidateBatch


ENDPOINT = "https://api.openai.com/v1/responses"
MAX_OUTPUT_TOKENS = 2048


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


urlopen = build_opener(ProxyHandler({}), _NoRedirect()).open


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _transport_schema(value):
    """Use a conservative strict-output subset; retain full local validation.

    Nonempty string constraints are still present in the shared prompt schema
    and Pydantic validator. The wire schema retains supported patterns, numeric
    bounds, required nullable fields, closed objects, references, and unions.
    """
    if isinstance(value, list):
        return [_transport_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _transport_schema(item) for key, item in value.items()
              if key not in {"title", "minLength", "maxLength"}}
    if "const" in result:
        result["enum"] = [result.pop("const")]
    return result


def _assistant_text(response: dict) -> str:
    output = response.get("output")
    if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
        raise ExtractionError("invalid_api_response", "OpenAI response output must be a list of objects.")
    chunks = []
    for item in output:
        if item.get("type") != "message":
            continue
        if item.get("role") != "assistant":
            continue
        content = item.get("content")
        if not isinstance(content, list) or any(not isinstance(part, dict) for part in content):
            raise ExtractionError("invalid_api_response", "OpenAI assistant content must be a list of objects.")
        if any(part.get("type") == "refusal" for part in content):
            raise ExtractionError("refusal", "The model refused the extraction request.")
        if item.get("status") not in {None, "completed"}:
            raise ExtractionError("truncated_response", "OpenAI returned an unfinished assistant message.")
        for part in content:
            if part.get("type") == "output_text":
                if not isinstance(part.get("text"), str):
                    raise ExtractionError("invalid_api_response", "OpenAI output_text must contain a string.")
                chunks.append(part["text"])
    raw_response = "".join(chunks)
    if not raw_response.strip():
        raise ExtractionError("missing_content", "OpenAI returned no assistant text for extraction.")
    return raw_response


def extract_candidates(
    text: str,
    *,
    model: str,
    api_key: str,
    timeout: float = 120.0,
) -> dict:
    """Return validated candidates, audit metadata, and exact output text.

    The caller supplies credentials; this module never reads a dotenv file or
    environment variable and never logs credentials or server error bodies.
    A failed/incomplete response is never converted to a successful empty batch.
    """
    if not isinstance(text, str):
        raise ExtractionError("invalid_input", "Patient text must be a string.")
    if not isinstance(model, str) or not model.strip():
        raise ExtractionError("invalid_config", "model must be a nonempty model name.")
    if (not isinstance(api_key, str) or not api_key
            or any(ord(character) < 33 or ord(character) > 126 for character in api_key)):
        raise ExtractionError("invalid_config", "An API key without whitespace is required.")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or timeout <= 0):
        raise ExtractionError("invalid_config", "timeout must be a positive finite number of seconds.")

    local_schema = CandidateBatch.model_json_schema()
    schema = _transport_schema(local_schema)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").rstrip()
    system_message = prompt + "\n\nOutput JSON schema:\n" + json.dumps(local_schema, sort_keys=True)
    payload = {
        "model": model,
        "instructions": system_message,
        "input": [{"role": "user", "content": json.dumps({"patient_text": text}, ensure_ascii=False)}],
        "text": {"format": {"type": "json_schema", "name": "symptom_candidates",
                            "schema": schema, "strict": True}},
        "reasoning": {"effort": "none"},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "store": False,
        "stream": False,
    }
    request = Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        status = exc.code
        exc.close()
        if status in {401, 403}:
            raise ExtractionError(
                "authentication_error", f"OpenAI returned HTTP {status}. Check API credentials and project access."
            ) from None
        raise ExtractionError(
            "http_error", f"OpenAI returned HTTP {status}. No retry was attempted; redirects are disabled."
        ) from None
    except (URLError, TimeoutError, OSError, HTTPException):
        raise ExtractionError(
            "network_error", "Could not complete the OpenAI request. Check connectivity and the timeout."
        ) from None

    try:
        api_response = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ExtractionError("invalid_api_response", "OpenAI returned an invalid JSON response envelope.") from None
    if not isinstance(api_response, dict):
        raise ExtractionError("invalid_api_response", "OpenAI response envelope must be a JSON object.")
    if api_response.get("error") is not None or api_response.get("status") == "failed":
        raise ExtractionError("server_error", "OpenAI reported an error instead of an extraction.")
    status = api_response.get("status")
    if status == "incomplete":
        details = api_response.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else None
        code = "truncated_response" if reason == "max_output_tokens" else "incomplete_response"
        raise ExtractionError(code, "OpenAI did not finish the extraction; partial candidates were not accepted.")
    if status in {"queued", "in_progress", "cancelled"}:
        raise ExtractionError("incomplete_response", "OpenAI did not return a completed extraction.")
    if status != "completed":
        raise ExtractionError("invalid_api_response", "OpenAI response is missing a recognized completion status.")
    raw_response = _assistant_text(api_response)
    try:
        json.loads(raw_response)
    except json.JSONDecodeError:
        raise ExtractionError(
            "invalid_json", "Assistant content is not valid JSON.", raw_response=raw_response
        ) from None
    try:
        batch = CandidateBatch.model_validate_json(raw_response)
    except ValidationError:
        raise ExtractionError(
            "invalid_schema", "Assistant JSON does not match the candidate schema.", raw_response=raw_response
        ) from None
    returned_model = api_response.get("model")
    return {
        "candidates": batch.model_dump(mode="json")["candidates"],
        "metadata": {
            "provider": "openai",
            "backend": "openai",
            "requested_model": model,
            "model": returned_model or model,
            "returned_model": returned_model,
            "prompt_sha256": _sha256(system_message),
            "schema_sha256": _sha256(json.dumps(schema, sort_keys=True)),
            "response_sha256": _sha256(raw_response),
            "response_id": api_response.get("id"),
            "status": status,
            "reasoning_effort": "none",
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "usage": api_response.get("usage"),
        },
        "raw_response": raw_response,
    }
