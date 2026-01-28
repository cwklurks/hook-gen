"""Tests for rate_limit module type safety and behavior."""

from unittest.mock import MagicMock

from api.rate_limit import get_client_ip


class TestGetClientIp:
    """Tests for get_client_ip function."""

    def test_returns_forwarded_for_first_ip(self):
        request = MagicMock()
        request.headers.get.return_value = "1.2.3.4, 5.6.7.8"
        result = get_client_ip(request)
        assert result == "1.2.3.4"
        assert isinstance(result, str)

    def test_returns_forwarded_for_single_ip(self):
        request = MagicMock()
        request.headers.get.return_value = "10.0.0.1"
        result = get_client_ip(request)
        assert result == "10.0.0.1"
        assert isinstance(result, str)

    def test_strips_whitespace_from_forwarded_for(self):
        request = MagicMock()
        request.headers.get.return_value = "  1.2.3.4 , 5.6.7.8"
        result = get_client_ip(request)
        assert result == "1.2.3.4"

    def test_falls_back_to_remote_address_when_no_forwarded_for(self):
        request = MagicMock()
        request.headers.get.return_value = None
        result = get_client_ip(request)
        # get_remote_address returns Any, but get_client_ip wraps it in str()
        assert isinstance(result, str)

    def test_return_type_is_always_str(self):
        """Verify the return type is str in all code paths (type safety fix)."""
        # With X-Forwarded-For header
        request = MagicMock()
        request.headers.get.return_value = "192.168.1.1"
        assert type(get_client_ip(request)) is str

        # Without X-Forwarded-For header
        request.headers.get.return_value = None
        assert type(get_client_ip(request)) is str
