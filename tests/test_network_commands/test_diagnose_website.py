"""Focused product-contract tests for diagnoseWebsite."""

from qzx.commands.network.diagnose_website import DiagnoseWebsiteCommand


class RecordingProbe:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


class RaisingProbe:
    def __init__(self, message="probe exploded"):
        self.message = message
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise RuntimeError(self.message)


class FailingIfCalledProbe:
    def execute(self, *args, **kwargs):  # pragma: no cover - failure explains itself
        raise AssertionError("Probe should not have been called")


def _dns_ok():
    return {
        "success": True,
        "domain": "example.com",
        "records": {"A": ["203.0.113.10"], "AAAA": [], "CNAME": []},
        "record_status": {"A": "resolved"},
        "message": "DNS ok",
    }


def _tls_ok(days=120):
    return {
        "success": True,
        "host": "example.com",
        "port": 443,
        "is_valid": True,
        "days_remaining": days,
        "message": "TLS ok",
    }


def _http_ok(status=200):
    return {
        "success": True,
        "url": "https://example.com",
        "is_online": True,
        "status_code": status,
        "response_time_ms": 42.0,
        "message": "HTTP ok",
    }


def _command(dns=None, tls=None, http=None):
    return DiagnoseWebsiteCommand(
        dns_command=dns or RecordingProbe(_dns_ok()),
        tls_command=tls or RecordingProbe(_tls_ok()),
        http_command=http or RecordingProbe(_http_ok()),
    )


def test_diagnose_website_healthy_one_command_contract():
    dns = RecordingProbe(_dns_ok())
    tls = RecordingProbe(_tls_ok())
    http = RecordingProbe(_http_ok())
    command = _command(dns=dns, tls=tls, http=http)

    result = command.execute("example.com")

    assert result["success"] is True
    assert result["overall_status"] == "healthy"
    assert result["healthy"] is True
    assert result["partial"] is False
    assert result["primary_issue_layer"] is None
    assert result["probe_status"] == {
        "dns": "healthy",
        "tls": "healthy",
        "http": "healthy",
    }
    assert result["read_only"] is True
    assert result["network_requests"] is True
    assert result["related_commands"] == [
        "checkDns",
        "checkSslCertificate",
        "checkUrlStatus",
    ]
    assert dns.calls == [(('example.com',), {})]
    assert tls.calls == [(('example.com', 443), {})]
    assert http.calls == [(('https://example.com', 10.0), {})]
    assert "Overall: HEALTHY" in result["report"]


def test_diagnose_website_nxdomain_stops_downstream_noise():
    dns = RecordingProbe(
        {
            "success": False,
            "error_code": "dns_name_not_found",
            "message": "DNS name does not exist.",
        }
    )
    command = _command(
        dns=dns,
        tls=FailingIfCalledProbe(),
        http=FailingIfCalledProbe(),
    )

    result = command.execute("missing.example")

    assert result["success"] is True
    assert result["overall_status"] == "unhealthy"
    assert result["primary_issue_layer"] == "dns"
    assert result["probe_status"] == {
        "dns": "unhealthy",
        "tls": "skipped",
        "http": "skipped",
    }
    assert result["tls"] is None
    assert result["http"] is None
    assert "upstream of both TLS and HTTP" in result["recommendations"][0]["reason"]


def test_diagnose_website_keeps_useful_evidence_when_dns_probe_itself_fails():
    dns = RecordingProbe(
        {
            "success": False,
            "error_code": "dns_resolver_unavailable",
            "message": "Resolver unavailable.",
        }
    )
    command = _command(dns=dns)

    result = command.execute("example.com")

    assert result["success"] is True
    assert result["overall_status"] == "partial"
    assert result["partial"] is True
    assert result["primary_issue_layer"] == "diagnostic"
    assert result["probe_status"] == {
        "dns": "failed",
        "tls": "healthy",
        "http": "healthy",
    }
    assert any("local resolver" in item["action"] for item in result["recommendations"])


def test_diagnose_website_identifies_tls_before_http_application_noise():
    tls = RecordingProbe(
        {
            "success": True,
            "host": "example.com",
            "port": 443,
            "is_valid": False,
            "days_remaining": -2,
            "message": "Certificate expired.",
        }
    )
    http = RecordingProbe(
        {
            "success": True,
            "is_online": False,
            "status_detail": "certificate verify failed",
            "message": "HTTPS request failed.",
        }
    )
    result = _command(tls=tls, http=http).execute("example.com")

    assert result["overall_status"] == "unhealthy"
    assert result["primary_issue_layer"] == "tls"
    assert result["probe_status"]["tls"] == "unhealthy"
    assert result["probe_status"]["http"] == "unhealthy"
    assert result["recommendations"][0]["command"] == "qzx checkSslCertificate example.com 443 --json"


def test_diagnose_website_distinguishes_http_4xx_from_server_failure():
    not_found = RecordingProbe(
        {
            "success": True,
            "is_online": False,
            "status_code": 404,
            "message": "HTTP 404",
        }
    )
    result = _command(http=not_found).execute("https://example.com/missing")

    assert result["overall_status"] == "attention"
    assert result["primary_issue_layer"] == "http"
    assert result["probe_status"]["http"] == "attention"
    assert result["url"] == "https://example.com/missing"

    server_error = RecordingProbe(
        {
            "success": True,
            "is_online": False,
            "status_code": 503,
            "message": "HTTP 503",
        }
    )
    result = _command(http=server_error).execute("example.com")
    assert result["overall_status"] == "unhealthy"
    assert result["primary_issue_layer"] == "http"


def test_diagnose_website_treats_unexpected_probe_exception_as_partial_not_site_failure():
    result = _command(dns=RaisingProbe()).execute("example.com")

    assert result["success"] is True
    assert result["overall_status"] == "partial"
    assert result["partial"] is True
    assert result["dns"]["error_code"] == "probe_exception"
    assert result["probe_status"]["dns"] == "failed"


def test_diagnose_website_normalizes_idn_port_path_and_timeout():
    dns = RecordingProbe(_dns_ok())
    tls = RecordingProbe(_tls_ok())
    http = RecordingProbe(_http_ok())
    result = _command(dns=dns, tls=tls, http=http).execute(
        "https://café.example:8443/status",
        timeout="15",
    )

    assert result["host"] == "xn--caf-dma.example"
    assert result["port"] == 8443
    assert result["path"] == "/status"
    assert result["url"] == "https://xn--caf-dma.example:8443/status"
    assert result["timeout_seconds"] == 15.0
    assert dns.calls[0][0] == ("xn--caf-dma.example",)
    assert tls.calls[0][0] == ("xn--caf-dma.example", 8443)
    assert http.calls[0][0] == ("https://xn--caf-dma.example:8443/status", 15.0)


def test_diagnose_website_rejects_ambiguous_or_private_target_components_before_probing():
    command = _command(
        dns=FailingIfCalledProbe(),
        tls=FailingIfCalledProbe(),
        http=FailingIfCalledProbe(),
    )

    cases = {
        "": "invalid_target",
        "http://example.com": "unsupported_scheme",
        "https://user@example.com": "private_target_component",
        "https://example.com/?token=secret": "private_target_component",
        "https://example.com/#debug": "private_target_component",
        "example.com;whoami": "unsafe_target",
        "127.0.0.1": "invalid_target",
        "127.1": "invalid_target",
        "0x7f000001": "invalid_target",
        "https://[::1]": "unsafe_target",
        "https://example.com:70000": "invalid_target",
        "https://example.com/a%20b": "unsafe_target",
    }
    for target, error_code in cases.items():
        result = command.execute(target)
        assert result["success"] is False, target
        assert result["error_code"] == error_code, target


def test_diagnose_website_validates_timeout_before_network_probes():
    command = _command(
        dns=FailingIfCalledProbe(),
        tls=FailingIfCalledProbe(),
        http=FailingIfCalledProbe(),
    )

    assert command.execute("example.com", timeout=0)["error_code"] == "invalid_timeout"
    assert command.execute("example.com", timeout=61)["error_code"] == "invalid_timeout"
    assert command.execute("example.com", timeout="never")["error_code"] == "invalid_timeout"


def test_diagnose_website_warns_before_certificate_expiry():
    result = _command(tls=RecordingProbe(_tls_ok(days=12))).execute("example.com")

    assert result["overall_status"] == "attention"
    assert result["primary_issue_layer"] == "tls"
    assert any("Renew or rotate" in item["action"] for item in result["recommendations"])
