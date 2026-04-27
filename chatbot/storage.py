from __future__ import annotations

import json
from pathlib import Path

from chatbot.models import Conversation


class ConversationStore:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, conversation_id: str) -> Path:
        return self.storage_dir / f"{conversation_id}.json"

    def save(self, conversation: Conversation) -> Path:
        path = self.path_for(conversation.id)
        path.write_text(json.dumps(conversation.to_dict(), indent=2), encoding="utf-8")
        return path

    def load_all(self) -> list[Conversation]:
        conversations: list[Conversation] = []
        for path in sorted(self.storage_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            conversations.append(Conversation.from_dict(payload))
        return conversations

    def delete(self, conversation_id: str) -> None:
        path = self.path_for(conversation_id)
        if path.exists():
            path.unlink()


def conversation_to_markdown(conversation: Conversation) -> str:
    lines = [
        f"# {conversation.title}",
        "",
        f"- Conversation ID: `{conversation.id}`",
        f"- Created: {conversation.created_at}",
        f"- Updated: {conversation.updated_at}",
        f"- Provider: {conversation.provider}",
        f"- Model: {conversation.model}",
        f"- Temperature: {conversation.parameters.get('temperature', '')}",
        f"- Max tokens: {conversation.parameters.get('max_tokens', '')}",
        "",
        "## System Prompt",
        "",
        conversation.system_prompt or "_None_",
        "",
        "## Transcript",
        "",
    ]
    for turn in conversation.turns:
        lines.append(f"### {turn.role.title()} ({turn.created_at})")
        lines.append("")
        lines.append(turn.content or "_No content_")
        lines.append("")
        if turn.attachments:
            lines.append("Attachments:")
            for attachment in turn.attachments:
                lines.append(
                    f"- {attachment.name} ({attachment.size_bytes} bytes, {attachment.chars} chars)"
                )
            lines.append("")
        if turn.usage:
            lines.append(
                f"Usage: prompt={turn.usage.prompt_tokens}, completion={turn.usage.completion_tokens}, total={turn.usage.total_tokens}"
            )
            lines.append("")
    return "\n".join(lines)
