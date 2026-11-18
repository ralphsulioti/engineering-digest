import socket

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that opens a network connection."""

    def refuse(_socket: socket.socket, address: object) -> None:
        # pytest.fail raises a BaseException, which code handling network errors won't catch.
        pytest.fail(f"Tests can't use the network (tried to connect to {address})")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


@pytest.fixture(autouse=True)
def no_api_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a real ANTHROPIC_API_KEY in the environment out of the tests."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
