from pathlib import Path

from calculator.storage import CalculatorStore, HistoryEntry, SettingsState


def test_store_round_trip(tmp_path: Path):
    store = CalculatorStore(tmp_path)
    entry = HistoryEntry(
        id="1",
        timestamp="2026-04-28T00:00:00+00:00",
        mode="Scientific",
        expression="2 + 2",
        result="4",
        angle_unit="Degree",
        display_format="Decimal",
        base="DEC",
    )
    store.save_history([entry])
    store.save_settings(SettingsState())
    store.save_memory({"registers": {"M": 3.0}, "variables": {"x": 4.0}, "ans": 4.0})

    assert store.load_history()[0].result == "4"
    assert store.load_settings().default_mode == "Scientific"
    assert store.load_memory()["variables"]["x"] == 4.0
