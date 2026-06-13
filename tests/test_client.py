import httpx
import pytest

from gauntlet import errors
from gauntlet.client import ChatResult, OpenAIClient


def _client(handler) -> OpenAIClient:
    transport = httpx.MockTransport(handler)
    return OpenAIClient(base_url="http://box:1234", transport=transport)


def test_chat_sends_openai_payload_and_parses_text():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        import json
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"completion_tokens": 5},
        })

    res = _client(handler).chat(model="m1", prompt="hi", max_tokens=16)
    assert seen["url"] == "http://box:1234/v1/chat/completions"
    assert seen["body"]["model"] == "m1"
    assert seen["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert isinstance(res, ChatResult)
    assert res.text == "hello"
    assert res.completion_tokens == 5
    assert res.latency_s >= 0


def test_unreachable_raises_typed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(errors.Unreachable):
        _client(handler).chat(model="m1", prompt="hi")


def test_embeddings_parses_vectors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    vecs = _client(handler).embeddings(model="e1", inputs=["x"])
    assert vecs == [[0.1, 0.2, 0.3]]
