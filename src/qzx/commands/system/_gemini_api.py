"""Google Gemini HTTP request helpers for explainFileWithGemini."""

from __future__ import annotations


def call_gemini_api(command, model_endpoint, api_key, model, prompt):
    """Send a bounded prompt and return sanitized Gemini response metadata."""
    url = "{}/{}:generateContent".format(model_endpoint, model)
    payload = _generation_payload(prompt)
    try:
        response = command._http_client.post(
            url,
            headers=command._request_headers(api_key),
            json=payload,
            timeout=30,
        )
    except Exception as exc:
        return command._failure(
            "gemini_request_failed",
            "The Gemini content-generation request failed.",
            "Check connectivity and retry the reviewed request.",
            details={"cause": type(exc).__name__},
        )
    if response.status_code != 200:
        return command._failure(
            "gemini_api_error",
            "Gemini rejected the content-generation request.",
            (
                "Check the selected model, API-key permissions, billing, "
                "quota, request size, and Gemini service status."
            ),
            details={"http_status": response.status_code},
        )
    return _parsed_generation_response(command, response)


def _generation_payload(prompt):
    return {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 1024,
        },
    }


def _parsed_generation_response(command, response):
    try:
        document = response.json()
        text = document["candidates"][0]["content"]["parts"][0]["text"]
    except (TypeError, ValueError, KeyError, IndexError):
        return command._failure(
            "invalid_gemini_response",
            "Gemini returned no usable text explanation.",
            "Retry later or inspect the selected model in Google AI Studio.",
        )
    if not isinstance(text, str) or not text.strip():
        return command._failure(
            "empty_gemini_response",
            "Gemini returned an empty text explanation.",
            "Retry later or choose another compatible model.",
        )
    usage = document.get("usageMetadata", {})
    return {
        "success": True,
        "text": text.strip(),
        "usage": usage if isinstance(usage, dict) else {},
    }
