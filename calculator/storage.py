from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class HistoryEntry:
    id: str
    timestamp: str
    mode: str
    expression: str
    result: str
    angle_unit: str
    display_format: str
    base: str
    variables_snapshot: dict[str, float] = field(default_factory=dict)
    formula: str | None = None


@dataclass
class SettingsState:
    theme: str = "System"
    default_mode: str = "Scientific"
    angle_unit: str = "Degree"
    precision: int = 10
    word_size: int = 64
    display_format: str = "Decimal"


class CalculatorStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.history_path = self.root / "history.json"
        self.settings_path = self.root / "settings.json"
        self.memory_path = self.root / "memory.json"

    def load_history(self) -> list[HistoryEntry]:
        if not self.history_path.exists():
            return []
        payload = json.loads(self.history_path.read_text(encoding="utf-8"))
        return [HistoryEntry(**entry) for entry in payload]

    def save_history(self, entries: list[HistoryEntry]) -> None:
        payload = [asdict(entry) for entry in entries]
        self.history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_settings(self) -> SettingsState:
        if not self.settings_path.exists():
            return SettingsState()
        payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        return SettingsState(**payload)

    def save_settings(self, settings: SettingsState) -> None:
        self.settings_path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")

    def load_memory(self) -> dict[str, object]:
        if not self.memory_path.exists():
            return {"registers": {"M": 0.0}, "variables": {}, "ans": 0.0}
        return json.loads(self.memory_path.read_text(encoding="utf-8"))

    def save_memory(self, memory: dict[str, object]) -> None:
        self.memory_path.write_text(json.dumps(memory, indent=2), encoding="utf-8")
