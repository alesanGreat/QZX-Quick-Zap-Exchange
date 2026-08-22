"""Deterministic TLS certificate tests for checkSslCertificate."""

import ssl
from datetime import datetime, timedelta, timezone

from qzx.commands.network.check_ssl_certificate import CheckSslCertificateCommand


class CertificateBackedCheckSslCertificateCommand(CheckSslCertificateCommand):
    """Run certificate analysis against deterministic certificate evidence."""

    def __init__(self, certificate):
        super().__init__()
        self.certificate = certificate

    def _connect(self, *_args, **_kwargs):
        return (
            self.certificate,
            ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256),
            "TLSv1.3",
        )


class TestCheckSslCertificateCommand:
    def setup_method(self):
        self.command = CheckSslCertificateCommand()

    def test_empty_host(self):
        result = self.command.execute("")

        assert result["success"] is False
        assert "must not be empty" in result["error"]

    def test_invalid_port_type(self):
        result = self.command.execute("example.com", "not_a_port")

        assert result["success"] is False
        assert "Port must be an integer" in result["error"]

    def test_tls_context_requires_tls_1_2_for_both_trust_modes(self):
        verified = self.command._create_tls_context()
        diagnostic = self.command._create_unverified_tls_context()

        assert verified.minimum_version is ssl.TLSVersion.TLSv1_2
        assert verified.check_hostname is True
        assert verified.verify_mode is ssl.CERT_REQUIRED
        assert diagnostic.minimum_version is ssl.TLSVersion.TLSv1_2
        assert diagnostic.check_hostname is False
        assert diagnostic.verify_mode is ssl.CERT_NONE

    @staticmethod
    def _certificate(*, host, not_before, not_after):
        return {
            "notBefore": not_before.strftime("%b %d %H:%M:%S %Y GMT"),
            "notAfter": not_after.strftime("%b %d %H:%M:%S %Y GMT"),
            "subject": ((("commonName", host),),),
            "issuer": ((("commonName", "QZX Test CA"),),),
            "subjectAltName": (("DNS", host),),
        }

    def test_trusted_certificate_is_valid(self):
        now = datetime.now(timezone.utc)
        certificate = self._certificate(
            host="example.com",
            not_before=now - timedelta(days=1),
            not_after=now + timedelta(days=30),
        )
        command = CertificateBackedCheckSslCertificateCommand(certificate)

        result = command.execute("example.com", 443)

        assert result["success"] is True
        assert result["host"] == "example.com"
        assert result["port"] == 443
        assert result["is_valid"] is True
        assert result["chain_trusted"] is True
        assert result["is_expired"] is False
        assert result["hostname_match"] is True
        assert result["days_remaining"] > 0
        assert result["subject"]
        assert result["issuer"]
        assert result["ssl_version"]
        assert result["cipher_suite"]
        assert "VALID" in result["message"]

    def test_expired_certificate_is_reported_without_external_network(
        self,
    ):
        now = datetime.now(timezone.utc)
        certificate = self._certificate(
            host="expired.example",
            not_before=now - timedelta(days=60),
            not_after=now - timedelta(days=30),
        )
        command = CertificateBackedCheckSslCertificateCommand(certificate)

        result = command.execute("expired.example", 443)

        assert result["success"] is True
        assert result["chain_trusted"] is True
        assert result["is_valid"] is False
        assert result["is_expired"] is True
        assert result["days_remaining"] < 0
        assert "EXPIRED" in result["message"]
