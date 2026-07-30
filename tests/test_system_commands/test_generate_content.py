"""Privacy and API-contract tests for generateContent."""

import json

from qzx.commands.system.generate_content import WonderContentGenCommand


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeGeminiClient:
    def __init__(self, generation_status=200):
        self.calls = []
        self.generation_status = generation_status

    def get(self, url, headers, timeout):
        self.calls.append(("get", url, headers, timeout))
        return FakeResponse(
            200,
            {
                "models": [
                    {
                        "name": "models/gemini-3.5-flash-lite",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-2.5-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ]
            },
        )

    def post(self, url, headers, json, timeout):
        self.calls.append(("post", url, headers, timeout, json))
        if self.generation_status != 200:
            return FakeResponse(
                self.generation_status,
                {"error": {"message": "sensitive upstream diagnostic"}},
            )
        return FakeResponse(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "A concise explanation."}]
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 25,
                    "candidatesTokenCount": 4,
                },
            },
        )


def test_preview_never_reads_credentials_or_contacts_gemini(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("QZX privacy preview", encoding="utf-8")

    def unexpected_key_lookup():
        raise AssertionError("preview must not read Gemini credentials")

    command = WonderContentGenCommand(
        http_client=None,
        api_key_provider=unexpected_key_lookup,
    )

    result = command.execute(target)

    assert result["success"] is True
    assert "No network request was made" in result["message"]
    assert result["details"]["dry_run"] is True
    assert result["details"]["content_shared"] is False
    assert result["external_service"]["provider"] == "Google Gemini"
    assert result["external_service"]["content_shared"] is False


def test_external_request_requires_matching_apply_flags(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("QZX", encoding="utf-8")
    command = WonderContentGenCommand(
        http_client=FakeGeminiClient(),
        api_key_provider=lambda: "fixture-key",
    )

    missing_apply = command.execute(target, dry_run=False, apply=False)
    conflicting = command.execute(target, dry_run=True, apply=True)

    assert missing_apply["error_code"] == "explicit_application_required"
    assert conflicting["error_code"] == "conflicting_application_flags"
    assert command._http_client.calls == []


def test_apply_uses_header_auth_and_reports_bounded_external_sharing(tmp_path):
    target = tmp_path / "source.txt"
    target.write_text("0123456789" * 20, encoding="utf-8")
    client = FakeGeminiClient()
    command = WonderContentGenCommand(
        http_client=client,
        api_key_provider=lambda: "fixture-secret",
    )

    result = command.execute(
        target,
        sample_size=20,
        dry_run=False,
        apply=True,
    )

    assert result["success"] is True
    assert result["explanation"] == "A concise explanation."
    assert result["external_service"]["content_shared"] is True
    assert result["external_service"]["source_characters_shared"] == 60
    assert result["model_used"] == "gemini-3.5-flash-lite"
    assert result["usage"]["promptTokenCount"] == 25
    assert len(result["file_sha256"]) == 64
    assert [call[0] for call in client.calls] == ["get", "post"]
    for call in client.calls:
        assert "fixture-secret" not in call[1]
        assert call[2]["x-goog-api-key"] == "fixture-secret"
    assert "pageSize=1000" in client.calls[0][1]
    generation_payload = client.calls[1][4]
    assert generation_payload["generationConfig"] == {
        "maxOutputTokens": 1024
    }


def test_api_failures_do_not_echo_secret_or_upstream_body(tmp_path):
    target = tmp_path / "source.txt"
    target.write_text("safe fixture text", encoding="utf-8")
    client = FakeGeminiClient(generation_status=403)
    command = WonderContentGenCommand(
        http_client=client,
        api_key_provider=lambda: "fixture-secret",
    )

    result = command.execute(
        target,
        dry_run=False,
        apply=True,
    )
    serialized = json.dumps(result)

    assert result["success"] is False
    assert result["error_code"] == "gemini_api_error"
    assert result["details"]["http_status"] == 403
    assert "fixture-secret" not in serialized
    assert "sensitive upstream diagnostic" not in serialized


def test_invalid_limits_and_binary_files_fail_before_network(tmp_path):
    binary = tmp_path / "payload.bin"
    binary.write_bytes(b"header\x00payload")
    client = FakeGeminiClient()
    command = WonderContentGenCommand(
        http_client=client,
        api_key_provider=lambda: "fixture-key",
    )

    invalid_sample = command.execute(binary, sample_size=9)
    invalid_limit = command.execute(binary, max_file_size_mb=101)
    binary_result = command.execute(
        binary,
        dry_run=False,
        apply=True,
    )

    assert invalid_sample["error_code"] == "invalid_sample_size"
    assert invalid_limit["error_code"] == "invalid_file_size_limit"
    assert binary_result["error_code"] == "binary_file_not_supported"
    assert client.calls == []


def test_execution_logic_emits_no_unstructured_stdout(tmp_path, capsys):
    target = tmp_path / "notes.txt"
    target.write_text("preview", encoding="utf-8")

    result = WonderContentGenCommand().execute(target)
    captured = capsys.readouterr()

    assert result["success"] is True
    assert captured.out == ""
    assert captured.err == ""
