from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_id() -> str:
    return str(uuid.uuid4())


def derive_title(text: str, fallback: str = "Untitled conversation") -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return fallback
    return cleaned[:60] + ("..." if len(cleaned) > 60 else "")


@dataclass
class AttachmentMeta:
    name: str
    mime_type: str
    size_bytes: int
    chars: int


@dataclass
class MessageUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class Message:
    id: str
    role: str
    content: str
    created_at: str
    attachments: list[AttachmentMeta] = field(default_factory=list)
    usage: MessageUsage | None = None
    error: str | None = None
    stopped: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.usage is None:
            payload["usage"] = None
        return payload


@dataclass
class ConversationMetrics:
    avg_latency_ms: float = 0.0
    avg_ttfb_ms: float = 0.0
    errors: int = 0
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    retries: int = 0
    regenerations: int = 0
    exports: int = 0
    cancel_count: int = 0


@dataclass
class Conversation:
    id: str
    title: str
    created_at: str
    updated_at: str
    provider: str
    model: str
    parameters: dict[str, Any]
    system_prompt: str
    turns: list[Message] = field(default_factory=list)
    metrics: ConversationMetrics = field(default_factory=ConversationMetrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "provider": self.provider,
            "model": self.model,
            "parameters": self.parameters,
            "system_prompt": self.system_prompt,
            "turns": [turn.to_dict() for turn in self.turns],
            "metrics": asdict(self.metrics),
        }

    @classmethod
    def create(
        cls,
        *,
        provider: str,
        model: str,
        parameters: dict[str, Any],
        system_prompt: str,
        title: str = "Untitled conversation",
    ) -> "Conversation":
        now = utc_now_iso()
        return cls(
            id=generate_id(),
            title=title,
            created_at=now,
            updated_at=now,
            provider=provider,
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Conversation":
        turns = []
        for turn in payload.get("turns", []):
            attachments = [
                AttachmentMeta(**attachment)
                for attachment in turn.get("attachments", [])
            ]
            usage = turn.get("usage")
            turns.append(
                Message(
                    id=turn["id"],
                    role=turn["role"],
                    content=turn.get("content", ""),
                    created_at=turn.get("created_at", utc_now_iso()),
                    attachments=attachments,
                    usage=MessageUsage(**usage) if usage else None,
                    error=turn.get("error"),
                    stopped=turn.get("stopped", False),
                    meta=turn.get("meta", {}),
                )
            )
        metrics = ConversationMetrics(**payload.get("metrics", {}))
        return cls(
            id=payload["id"],
            title=payload.get("title", "Untitled conversation"),
            created_at=payload.get("created_at", utc_now_iso()),
            updated_at=payload.get("updated_at", utc_now_iso()),
            provider=payload.get("provider", "openai"),
            model=payload.get("model", ""),
            parameters=payload.get("parameters", {}),
            system_prompt=payload.get("system_prompt", ""),
            turns=turns,
            metrics=metrics,
        )
