from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event
from typing import Iterable


class AdapterError(RuntimeError):
    """Raised for adapter configuration or runtime errors."""


@dataclass
class StreamResult:
    text: str
    usage: dict[str, int]
    ttfb_ms: float
    latency_ms: float


class BaseAdapter:
    provider_name = "base"

    def check_ready(self) -> tuple[bool, str | None]:
        return True, None

    def stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        cancel_event: Event,
    ) -> Iterable[str]:
        raise NotImplementedError

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        cancel_event: Event,
    ) -> StreamResult:
        start = time.perf_counter()
        first_token_at = None
        chunks: list[str] = []
        for chunk in self.stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            cancel_event=cancel_event,
        ):
            if cancel_event.is_set():
                break
            if first_token_at is None:
                first_token_at = time.perf_counter()
            chunks.append(chunk)
        end = time.perf_counter()
        prompt_tokens = sum(len(message.get("content", "").split()) for message in messages)
        completion_tokens = max(len("".join(chunks).split()), 0)
        return StreamResult(
            text="".join(chunks),
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            ttfb_ms=((first_token_at or end) - start) * 1000,
            latency_ms=(end - start) * 1000,
        )


class OpenAICompatibleAdapter(BaseAdapter):
    provider_name = "openai-compatible"

    def __init__(self, api_key: str | None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url

    def check_ready(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "Missing OPENAI_API_KEY or API_KEY."
        return True, None

    def stream(self, *, messages, model, temperature, max_tokens, cancel_event):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AdapterError("The openai package is not installed.") from exc
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in response:
            if cancel_event.is_set():
                break
            delta = ""
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta


class AzureOpenAIAdapter(OpenAICompatibleAdapter):
    provider_name = "azure"

    def __init__(self, api_key: str | None, endpoint: str | None, api_version: str | None) -> None:
        super().__init__(api_key=api_key, base_url=None)
        self.endpoint = endpoint
        self.api_version = api_version

    def check_ready(self) -> tuple[bool, str | None]:
        if not self.api_key or not self.endpoint:
            return False, "Missing AZURE_OPENAI_API_KEY/API_KEY or AZURE_OPENAI_ENDPOINT."
        return True, None

    def stream(self, *, messages, model, temperature, max_tokens, cancel_event):
        try:
            from openai import AzureOpenAI
        except ImportError as exc:
            raise AdapterError("The openai package is not installed.") from exc
        client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.api_version,
        )
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in response:
            if cancel_event.is_set():
                break
            delta = ""
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta


class AnthropicAdapter(BaseAdapter):
    provider_name = "anthropic"

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    def check_ready(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "Missing ANTHROPIC_API_KEY or API_KEY."
        return True, None

    def stream(self, *, messages, model, temperature, max_tokens, cancel_event):
        try:
            import anthropic
        except ImportError as exc:
            raise AdapterError("The anthropic package is not installed.") from exc
        client = anthropic.Anthropic(api_key=self.api_key)
        system = next((message["content"] for message in messages if message["role"] == "system"), "")
        conversation_messages = [m for m in messages if m["role"] != "system"]
        with client.messages.stream(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system=system,
            messages=conversation_messages,
        ) as stream:
            for text in stream.text_stream:
                if cancel_event.is_set():
                    break
                yield text


def get_adapter(
    *,
    provider: str,
    openai_api_key: str | None,
    anthropic_api_key: str | None,
    api_base: str | None,
    azure_endpoint: str | None,
    azure_api_key: str | None,
    azure_api_version: str | None,
) -> BaseAdapter:
    provider = provider.lower()
    if provider == "openai":
        return OpenAICompatibleAdapter(api_key=openai_api_key, base_url=api_base)
    if provider == "custom":
        return OpenAICompatibleAdapter(api_key=openai_api_key, base_url=api_base)
    if provider == "azure":
        return AzureOpenAIAdapter(
            api_key=azure_api_key,
            endpoint=azure_endpoint,
            api_version=azure_api_version,
        )
    if provider == "anthropic":
        return AnthropicAdapter(api_key=anthropic_api_key)
    raise AdapterError(f"Unsupported provider: {provider}")
