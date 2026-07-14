"""Tests for rate_limit module type safety and behavior."""

from unittest.mock import MagicMock

from api.rate_limit import get_client_ip


class TestGetClientIp:
    """Tests for get_client_ip function."""

    @staticmethod
    def request_with(*, remote: str, forwarded_for: str | None = None):
        request = MagicMock()
        request.client.host = remote
        request.headers.get.return_value = forwarded_for
        return request

    def test_ignores_forwarded_for_by_default(self, monkeypatch):
        monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
        request = self.request_with(remote="203.0.113.10", forwarded_for="1.2.3.4")

        assert get_client_ip(request) == "203.0.113.10"

    def test_uses_address_before_trusted_proxy_hops(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
        request = self.request_with(
            remote="10.0.0.2",
            forwarded_for="198.51.100.99, 203.0.113.20, 10.0.0.1",
        )

        assert get_client_ip(request) == "203.0.113.20"

    def test_falls_back_when_forwarded_chain_is_too_short(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
        request = self.request_with(remote="203.0.113.10", forwarded_for="1.2.3.4")

        assert get_client_ip(request) == "203.0.113.10"

    def test_falls_back_for_invalid_forwarded_address(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
        request = self.request_with(remote="203.0.113.10", forwarded_for="not-an-ip")

        assert get_client_ip(request) == "203.0.113.10"

    def test_falls_back_for_invalid_proxy_configuration(self, monkeypatch):
        monkeypatch.setenv("TRUSTED_PROXY_HOPS", "many")
        request = self.request_with(remote="203.0.113.10", forwarded_for="1.2.3.4")

        assert get_client_ip(request) == "203.0.113.10"
