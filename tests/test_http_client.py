from collections.abc import Generator

import httpx
import pytest

import src.http_client as _http_client_mod
from src.http_client import get_http_client


@pytest.fixture(autouse=True)
def reset_http_client() -> Generator[None, None, None]:
    """Ensure the module-level singleton is None before and after each test."""
    _http_client_mod._http_client = None
    yield
    _http_client_mod._http_client = None


def test_get_http_client_raises_before_initialization() -> None:
    """get_http_client() must raise RuntimeError when called before lifespan."""
    with pytest.raises(RuntimeError, match="HTTP client is not initialized"):
        get_http_client()


def test_get_http_client_returns_instance_after_initialization() -> None:
    """get_http_client() returns the AsyncClient once the singleton is set."""
    fake_client = httpx.AsyncClient()
    _http_client_mod._http_client = fake_client

    result = get_http_client()

    assert result is fake_client


def test_get_http_client_is_singleton() -> None:
    """Multiple calls to get_http_client() return the exact same instance."""
    fake_client = httpx.AsyncClient()
    _http_client_mod._http_client = fake_client

    first = get_http_client()
    second = get_http_client()

    assert first is second


@pytest.mark.parametrize("value", [None])
def test_get_http_client_raises_when_reset_to_none(value: None) -> None:
    """After the singleton is cleared, get_http_client() raises RuntimeError again."""
    _http_client_mod._http_client = httpx.AsyncClient()
    _http_client_mod._http_client = value

    with pytest.raises(RuntimeError, match="HTTP client is not initialized"):
        get_http_client()
