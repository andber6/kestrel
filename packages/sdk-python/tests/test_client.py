"""Tests for the Kestrel SDK client."""

from kestrel import AsyncClient, Client, __version__


class TestClient:
    def test_ar_key_sets_custom_header(self) -> None:
        client = Client(api_key="ks-test-key", provider_key="sk-provider")
        assert client._custom_headers["X-Kestrel-Key"] == "ks-test-key"

    def test_ar_key_uses_provider_key_as_bearer(self) -> None:
        client = Client(api_key="ks-test-key", provider_key="sk-provider")
        assert client.api_key == "sk-provider"

    def test_passthrough_mode_no_custom_header(self) -> None:
        client = Client(api_key="sk-direct-key")
        assert "X-Kestrel-Key" not in client._custom_headers

    def test_passthrough_mode_uses_api_key(self) -> None:
        client = Client(api_key="sk-direct-key")
        assert client.api_key == "sk-direct-key"

    def test_default_base_url(self) -> None:
        client = Client(api_key="sk-test")
        assert "localhost:8080" in str(client.base_url)

    def test_custom_base_url(self) -> None:
        client = Client(
            api_key="sk-test",
            base_url="https://api.usekestrel.io/v1",
        )
        assert "usekestrel.io" in str(client.base_url)

    def test_extra_headers_preserved(self) -> None:
        client = Client(
            api_key="ks-key",
            provider_key="sk-key",
            default_headers={"X-Custom": "value"},
        )
        assert client._custom_headers["X-Custom"] == "value"
        assert client._custom_headers["X-Kestrel-Key"] == "ks-key"


class TestAsyncClient:
    def test_ar_key_sets_custom_header(self) -> None:
        client = AsyncClient(api_key="ks-test-key", provider_key="sk-provider")
        assert client._custom_headers["X-Kestrel-Key"] == "ks-test-key"

    def test_passthrough_mode(self) -> None:
        client = AsyncClient(api_key="sk-direct-key")
        assert "X-Kestrel-Key" not in client._custom_headers
        assert client.api_key == "sk-direct-key"


class TestVersion:
    def test_version_is_set(self) -> None:
        assert __version__ == "0.1.0"
