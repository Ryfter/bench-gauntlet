"""Refuse to run against an endpoint that is not serving.

The failure this prevents is silent and expensive. Opening the LM Studio desktop
app stops its headless server, but `lms load` keeps working because that talks
to the app, not the server. So VRAM fills, the indicator shows a model resident,
and every request is refused instantly. On 2026-07-26 that burned 223 cases
across two models in about twenty minutes and wrote twelve unscored cells that
looked, at a glance, like the models had been measured and failed.
"""
from __future__ import annotations

import httpx
import pytest

from gauntlet.client import OpenAIClient


def _client(handler) -> OpenAIClient:
    return OpenAIClient(base_url="http://203.0.113.7:1234",
                        transport=httpx.MockTransport(handler))


def test_ping_is_true_when_the_endpoint_serves_models():
    client = _client(lambda _r: httpx.Response(200, json={"data": []}))
    assert client.ping() is True
    client.close()


def test_ping_is_false_when_the_connection_is_refused():
    """The exact shape of a stopped LM Studio server."""
    def refuse(_request):
        raise httpx.ConnectError("actively refused it")

    client = _client(refuse)
    assert client.ping() is False
    client.close()


def test_ping_is_false_on_a_server_error():
    client = _client(lambda _r: httpx.Response(503))
    assert client.ping() is False
    client.close()


def test_ping_is_false_on_timeout():
    def hang(_request):
        raise httpx.ReadTimeout("too slow")

    client = _client(hang)
    assert client.ping() is False
    client.close()


def test_ping_never_raises():
    """Called on the run's critical path, so it reports rather than throws --
    the caller decides what a dead endpoint means."""
    def explode(_request):
        raise httpx.RemoteProtocolError("peer closed connection")

    client = _client(explode)
    assert client.ping() is False
    client.close()


@pytest.mark.parametrize("status", [200, 201])
def test_only_a_2xx_with_a_body_counts_as_serving(status):
    client = _client(lambda _r: httpx.Response(status, json={"data": []}))
    assert client.ping() is (status == 200)
    client.close()
