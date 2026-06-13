from __future__ import annotations

import time

import httpx
from pydantic import BaseModel

from gauntlet import errors


class ChatResult(BaseModel):
    text: str
    completion_tokens: int | None = None
    latency_s: float = 0.0


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
        }
        start = time.monotonic()
        try:
            resp = self._http.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise errors.Unreachable(f"{self.base_url}: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise errors.ModelLoadFailed(f"{model}: HTTP {exc.response.status_code}") from exc
        latency = time.monotonic() - start
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return ChatResult(text=text, completion_tokens=usage.get("completion_tokens"),
                          latency_s=latency)

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
