from __future__ import annotations

import json
import time

import httpx
from pydantic import BaseModel

from gauntlet import errors


class ChatResult(BaseModel):
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_s: float = 0.0
    ttft_s: float | None = None  # time to first token; populated via SSE streaming


class OpenAIClient:
    """The ONLY component that performs HTTP. Everything else is pure logic."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 120.0,
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
        start = time.monotonic()
        try:
            with self._http.stream("POST", "/v1/chat/completions", json=payload) as resp:
                resp.raise_for_status()
                ttft_s: float | None = None
                chunks: list[str] = []
                usage: dict = {}
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
        latency = time.monotonic() - start
        return ChatResult(
            text="".join(chunks),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_s=latency,
            ttft_s=ttft_s,
        )

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
