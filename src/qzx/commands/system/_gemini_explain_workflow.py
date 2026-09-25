"""Orchestration for explainFileWithGemini."""

from __future__ import annotations

from pathlib import Path


def execute_gemini_explanation(
    command,
    file_path,
    sample_size,
    model,
    custom_prompt,
    max_file_size_mb,
    dry_run,
    apply,
):
    """Preview or perform one explicitly authorized Gemini request."""
    model = str(model or "")
    custom_prompt = str(custom_prompt or "")
    validation = command._validate_request(
        file_path,
        sample_size,
        model,
        custom_prompt,
        max_file_size_mb,
        dry_run,
        apply,
    )
    if not validation["success"]:
        return validation
    details = validation["details"]
    if details["dry_run"]:
        return _preview_result(details)
    return _execute_external_request(
        command,
        details,
        custom_prompt,
    )


def _preview_result(details):
    return {
        "success": True,
        "message": (
            "Gemini file-analysis preview is ready. No network request was "
            "made and no file content was shared."
        ),
        "details": details,
        "external_service": details["external_service"],
        "next_step": (
            "Review the target, provider, prompt source, and sample limits; "
            "then use --dry-run false --apply to send it."
        ),
    }


def _execute_external_request(command, details, custom_prompt):
    failure = _external_prerequisite_failure(command)
    if failure is not None:
        return failure

    api_key = command._api_key_provider()
    if not api_key:
        return command._failure(
            "gemini_api_key_missing",
            "No Gemini API key is configured.",
            (
                "Set GEMINI_API_KEY (preferred) or GEMINI_API_TOKEN, then "
                "retry the explicitly authorized command."
            ),
        )

    prepared = command._prepare_sample(
        Path(details["resolved_path"]),
        details["sample_size_characters"],
        details["max_file_size_bytes"],
    )
    if not prepared["success"]:
        return prepared

    model_result = _selected_model(command, api_key, details)
    if not model_result["success"]:
        return model_result
    selected_model = model_result["model"]

    prompt = custom_prompt.strip() or command.DEFAULT_PROMPT
    request_text = "{}\n\n{}".format(prompt, prepared["sample"])
    response = command._call_gemini_api(
        api_key,
        selected_model,
        request_text,
    )
    if not response["success"]:
        return response
    return _success_result(
        details,
        prepared,
        selected_model,
        request_text,
        response,
    )


def _external_prerequisite_failure(command):
    if command._http_client is not None:
        return None
    return command._failure(
        "missing_dependency",
        "The optional HTTP dependency is not installed.",
        "Install the AI extras with 'pip install qzx[ai]'.",
        details={"missing": ["requests"]},
    )


def _selected_model(command, api_key, details):
    models_result = command._list_gemini_models(api_key)
    if not models_result["success"]:
        return models_result
    selected = command._select_model(
        details["requested_model"],
        models_result["models"],
    )
    if selected:
        return {"success": True, "model": selected}
    return command._failure(
        "model_not_available",
        "No compatible Gemini content-generation model was found.",
        (
            "Choose a model returned for this API key that supports "
            "explainFileWithGemini, or retry model auto-selection later."
        ),
        details={
            "requested_model": details["requested_model"] or None,
            "available_models": sorted(
                command._available_model_names(models_result["models"])
            ),
        },
    )


def _success_result(
    details,
    prepared,
    selected_model,
    request_text,
    response,
):
    external_service = {
        "provider": "Google Gemini",
        "endpoint_host": "generativelanguage.googleapis.com",
        "content_shared": True,
        "model": selected_model,
        "source_characters_shared": prepared["source_characters_shared"],
        "request_characters": len(request_text),
        "sample_strategy": prepared["sample_strategy"],
    }
    return {
        "success": True,
        "message": (
            "Google Gemini explained a bounded sample of '{}'. "
            "{} source characters were shared with model {}."
        ).format(
            details["display_path"],
            prepared["source_characters_shared"],
            selected_model,
        ),
        "explanation": response["text"],
        "file_path": details["display_path"],
        "file_size_bytes": prepared["file_size_bytes"],
        "file_sha256": prepared["file_sha256"],
        "sample_size": details["sample_size_characters"],
        "model_used": selected_model,
        "encoding": prepared["encoding"],
        "external_service": external_service,
        "usage": response.get("usage", {}),
        "details": {
            **details,
            "dry_run": False,
            "content_shared": True,
            "external_service": external_service,
        },
    }
