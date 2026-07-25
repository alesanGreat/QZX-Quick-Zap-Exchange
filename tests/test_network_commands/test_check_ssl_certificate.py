"""Real TLS certificate tests for checkSslCertificate."""

from qzx.commands.network.check_ssl_certificate import CheckSslCertificateCommand


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

    def test_example_com_certificate_is_really_trusted(self):
        result = self.command.execute("example.com", 443)

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

    def test_expired_badssl_certificate_is_really_expired(self):
        result = self.command.execute("expired.badssl.com", 443)

        assert result["success"] is True
        assert result["chain_trusted"] is False
        assert result["is_valid"] is False
        assert result["is_expired"] is True
        assert result["days_remaining"] < 0
        assert "EXPIRED" in result["message"]
