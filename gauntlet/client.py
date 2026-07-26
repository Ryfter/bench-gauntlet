from __future__ import annotations

import json
import time

import httpx
from pydantic import BaseModel

from gauntlet import errors, integrity


class ChatResult(BaseModel):
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_s: float = 0.0
    ttft_s: float | None = None  # time to first token; populated via SSE streaming
    # Why generation stopped. "length" means the token budget ran out mid-reply,
    # which for a reasoning model can mean it never reached its answer at all --
    # a fact about our configuration, not about the model.
    finish_reason: str | None = None

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


class OpenAIClient:
    """The ONLY component that performs HTTP. Everything else is pure logic."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        # Per-chunk on a stream, not per-request, so this is the longest silence
        # tolerated rather than a cap on generation. A reasoning model can think
        # for minutes before its first content token; 120s was cutting those off
        # as transport errors, which reads as an unreachable box rather than a
        # slow model.
        timeout: float = 600.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(
            base_url=self.base_url, headers=headers, timeout=timeout, transport=transport
        )

    def chat(self, model: str, prompt: str, max_tokens: int = 512,
             temperature: float = 0.0) -> ChatResult:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        # This is the only place a request is built, so it is the only place
        # the check has to live. A server-side tool or web-search call would be
        # scored as though the model produced it.
        integrity.assert_request_is_tool_free(payload)
        start = time.monotonic()
        try:
            with self._http.stream("POST", "/v1/chat/completions", json=payload) as resp:
                resp.raise_for_status()
                ttft_s: float | None = None
                chunks: list[str] = []
                usage: dict = {}
                finish_reason: str | None = None
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("usage"):
                        usage = obj["usage"]
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    if choices[0].get("finish_reason"):
                        finish_reason = choices[0]["finish_reason"]
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        if ttft_s is None:
                            ttft_s = time.monotonic() - start
                        chunks.append(content)
        except httpx.ConnectError as exc:
            raise errors.Unreachable(f"{self.base_url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise errors.ModelLoadFailed(f"{model}: HTTP {exc.response.status_code}") from exc
        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError,
                httpx.TimeoutException) as exc:
            # The stream died part-way. Opening the LM Studio UI is enough to do
            # this, and it killed a 51-cell run outright. Per the error taxonomy
            # a transport failure is a *cell outcome*, not a reason to abandon
            # hours of completed work -- the runner records it and carries on.
            raise errors.Unreachable(
                f"{self.base_url}: stream interrupted ({type(exc).__name__}: {exc})") from exc
        latency = time.monotonic() - start
        return ChatResult(
            text="".join(chunks),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_s=latency,
            ttft_s=ttft_s,
            finish_reason=finish_reason,
        )

    def ping(self) -> bool:
        """Is the endpoint actually serving? Cheap, no model load.

        Worth a call before a run because the failure it catches is silent and
        expensive: opening the LM Studio desktop app stops its headless server,
        and `lms load` keeps working afterwards because that talks to the app
        rather than the server. So VRAM fills, the indicator shows a model
        resident, and every request is refused. On 2026-07-26 that produced 223
        errored cases and twelve unscored cells before anyone noticed.
        """
        try:
            resp = self._http.get("/v1/models", timeout=15.0)
        except httpx.HTTPError:
            return False
        return resp.status_code == 200

    def embeddings(self, model: str, inputs: list[str]) -> list[list[float]]:
        payload = {"model": model, "input": inputs}
        try:
            resp = self._http.post("/v1/embeddings", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise errors.Unreachable(f"{self.base_url}: {exc}") from exc
        return [row["embedding"] for row in resp.json()["data"]]

    def close(self) -> None:
        self._http.close()
