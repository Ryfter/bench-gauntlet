import json

import httpx
import pytest

from gauntlet import errors, integrity
from gauntlet.client import ChatResult, OpenAIClient
from tests.helpers import sse


def _client(handler) -> OpenAIClient:
    transport = httpx.MockTransport(handler)
    return OpenAIClient(base_url="http://box:1234", transport=transport)


def test_chat_sends_openai_payload_and_parses_text():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, text=sse("hello", prompt_tokens=3, completion_tokens=5))

    res = _client(handler).chat(model="m1", prompt="hi", max_tokens=16)
    assert seen["url"] == "http://box:1234/v1/chat/completions"
    assert seen["body"]["model"] == "m1"
    assert seen["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert seen["body"]["stream"] is True
    assert seen["body"]["stream_options"] == {"include_usage": True}
    assert isinstance(res, ChatResult)
    assert res.text == "hello"
    assert res.completion_tokens == 5
    assert res.prompt_tokens == 3
    assert res.latency_s >= 0


def test_chat_captures_ttft_and_assembles_chunks():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=sse("tok1", " tok2", prompt_tokens=4, completion_tokens=2))

    res = _client(handler).chat(model="m1", prompt="hi")
    assert res.text == "tok1 tok2"
    assert res.ttft_s is not None
    assert res.ttft_s >= 0


def test_chat_no_content_chunks_yields_empty_text_no_ttft():
    def handler(request: httpx.Request) -> httpx.Response:
        # Final chunk only — no content delta
        body = (
            'data: {"choices": [{"delta": {}, "finish_reason": "stop"}], '
            '"usage": {"prompt_tokens": 2, "completion_tokens": 0}}\n'
            'data: [DONE]\n'
        )
        return httpx.Response(200, text=body)

    res = _client(handler).chat(model="m1", prompt="hi")
    assert res.text == ""
    assert res.ttft_s is None
    assert res.completion_tokens == 0


def test_chat_rejects_server_injected_tool_use():
    def handler(request: httpx.Request) -> httpx.Response:
        body = ('data: {"choices":[{"delta":{"content":"answer",'
                '"tool_calls":[{"id":"1"}]},"finish_reason":"tool_calls"}]}\n'
                'data: [DONE]\n')
        return httpx.Response(200, text=body)
    with pytest.raises(integrity.IntegrityError, match="tool use"):
        _client(handler).chat(model="m1", prompt="hi")


@pytest.mark.parametrize("body", [
    '{"choices":[{"message":{"content":"hello"}}]}',
    'data: not-json\ndata: [DONE]\n',
])
def test_chat_rejects_non_sse_or_malformed_200(body):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)
    with pytest.raises(errors.Unreachable, match="malformed chat stream"):
        _client(handler).chat(model="m1", prompt="hi")


def test_unreachable_raises_typed_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(errors.Unreachable) as caught:
        _client(handler).chat(model="m1", prompt="hi")
    assert "http://box:1234" not in str(caught.value)
    assert "refused" not in str(caught.value)


def test_embeddings_parses_vectors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    vecs = _client(handler).embeddings(model="e1", inputs=["x"])
    assert vecs == [[0.1, 0.2, 0.3]]


@pytest.mark.parametrize("response", [
    httpx.Response(500),
    httpx.Response(200, text="not-json"),
    httpx.Response(200, json={"unexpected": []}),
    httpx.Response(200, json={"data": [{}]}),
])
def test_embeddings_translate_status_and_protocol_failures(response):
    def handler(request: httpx.Request) -> httpx.Response:
        return response
    with pytest.raises(errors.Unreachable):
        _client(handler).embeddings(model="e1", inputs=["x"])


def test_frontier_client_requires_a_nonblank_key():
    from gauntlet.cli import _frontier_client

    with pytest.raises(errors.GauntletError, match="key"):
        _frontier_client("http://203.0.113.10/v1", api_key=None)
    with pytest.raises(errors.GauntletError, match="key"):
        _frontier_client("http://203.0.113.10/v1", api_key="   ")


def test_openai_client_require_key_propagates_stripped_value():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, text=sse("ok"))

    client = OpenAIClient(
        base_url="http://box:1234",
        api_key="  sk-test  ",
        require_key=True,
        transport=httpx.MockTransport(handler),
    )
    client.chat(model="m", prompt="hi")
    assert seen["authorization"] == "Bearer sk-test"
