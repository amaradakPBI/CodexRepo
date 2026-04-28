from __future__ import annotations

import uuid
from pathlib import Path

import streamlit as st

from calculator import (
    CalculatorEngine,
    CalculatorStore,
    HistoryEntry,
    SettingsState,
    constant_search,
    convert_value,
    display_in_bases,
)
from calculator.exports import history_to_json, history_to_pdf, history_to_text
from calculator.storage import utc_now_iso


REPO_ROOT = Path(__file__).resolve().parent
DATA_ROOT = REPO_ROOT / "data"
EXPORT_ROOT = DATA_ROOT / "exports"
STORE = CalculatorStore(DATA_ROOT)
ENGINE = CalculatorEngine()


st.set_page_config(page_title="Scientific Calculator", page_icon="🧮", layout="wide")


def init_state() -> None:
    if "history" not in st.session_state:
        st.session_state.history = STORE.load_history()
    if "settings" not in st.session_state:
        st.session_state.settings = STORE.load_settings()
    if "memory" not in st.session_state:
        st.session_state.memory = STORE.load_memory()
    if "expression" not in st.session_state:
        st.session_state.expression = ""
    if "result_text" not in st.session_state:
        st.session_state.result_text = "0"
    if "status_message" not in st.session_state:
        st.session_state.status_message = ""
    if "copied_result" not in st.session_state:
        st.session_state.copied_result = ""


def persist() -> None:
    STORE.save_history(st.session_state.history)
    STORE.save_settings(st.session_state.settings)
    STORE.save_memory(st.session_state.memory)


def insert_token(token: str) -> None:
    st.session_state.expression += token


def set_expression(value: str) -> None:
    st.session_state.expression = value


def clear_expression() -> None:
    st.session_state.expression = ""
    st.session_state.status_message = ""


def clear_all() -> None:
    clear_expression()
    st.session_state.memory["registers"]["M"] = 0.0
    st.session_state.memory["variables"] = {}
    st.session_state.memory["ans"] = 0.0
    st.session_state.result_text = "0"
    persist()


def commit_history(result) -> None:
    entry = HistoryEntry(
        id=str(uuid.uuid4()),
        timestamp=utc_now_iso(),
        mode=st.session_state.settings.default_mode,
        expression=result.expression,
        result=result.display,
        angle_unit=st.session_state.settings.angle_unit,
        display_format=st.session_state.settings.display_format,
        base=result.base,
        variables_snapshot=dict(st.session_state.memory["variables"]),
        formula=result.formula,
    )
    st.session_state.history.insert(0, entry)
    st.session_state.history = st.session_state.history[:500]
    st.session_state.memory["ans"] = result.result
    if result.assigned_variable:
        st.session_state.memory["variables"][result.assigned_variable] = float(result.result)
    st.session_state.result_text = result.display
    st.session_state.status_message = "Calculation saved to history."
    persist()


def evaluate_current_expression() -> None:
    try:
        result = ENGINE.evaluate(
            st.session_state.expression,
            mode=st.session_state.settings.default_mode,
            angle_unit=st.session_state.settings.angle_unit,
            precision=st.session_state.settings.precision,
            display_format=st.session_state.settings.display_format,
            word_size=st.session_state.settings.word_size,
            variables=st.session_state.memory["variables"],
            ans=st.session_state.memory["ans"],
        )
    except Exception as exc:
        st.session_state.status_message = f"Error: {exc}"
        return
    commit_history(result)


def update_memory(operation: str) -> None:
    current = st.session_state.memory["registers"]["M"]
    last = float(st.session_state.memory.get("ans", 0.0))
    if operation == "M+":
        st.session_state.memory["registers"]["M"] = current + last
    elif operation == "M-":
        st.session_state.memory["registers"]["M"] = current - last
    elif operation == "MR":
        insert_token(str(st.session_state.memory["registers"]["M"]))
    elif operation == "MC":
        st.session_state.memory["registers"]["M"] = 0.0
    persist()


def export_history(kind: str) -> Path:
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_iso().replace(":", "-")
    if kind == "txt":
        path = EXPORT_ROOT / f"calculator-history-{stamp}.txt"
        path.write_text(history_to_text(st.session_state.history), encoding="utf-8")
        return path
    if kind == "json":
        path = EXPORT_ROOT / f"calculator-history-{stamp}.json"
        path.write_text(history_to_json(st.session_state.history), encoding="utf-8")
        return path
    path = EXPORT_ROOT / f"calculator-history-{stamp}.pdf"
    history_to_pdf(st.session_state.history, path)
    return path


def render_keypad(mode: str) -> None:
    key_rows = {
        "Standard": [["7", "8", "9", "/"], ["4", "5", "6", "*"], ["1", "2", "3", "-"], ["0", ".", "(", ")"]],
        "Scientific": [["sin(", "cos(", "tan(", "ln(", "log("], ["sqrt(", "pow(", "fact(", "npr(", "ncr("], ["7", "8", "9", "/", "^"], ["4", "5", "6", "*", "%"], ["1", "2", "3", "-", "Ans"], ["0", ".", "(", ")", "+"]],
        "Programmer": [["7", "8", "9", "&", "|"], ["4", "5", "6", "^", "~"], ["1", "2", "3", "<<", ">>"], ["0", "0xA", "0xB", "0xC", "0xD"], ["0xE", "0xF", "(", ")", "Ans"]],
    }
    for row in key_rows[mode]:
        columns = st.columns(len(row))
        for index, token in enumerate(row):
            if columns[index].button(token, use_container_width=True, key=f"{mode}-{token}-{index}"):
                insert_token(token)


def render_sidebar() -> None:
    settings: SettingsState = st.session_state.settings
    with st.sidebar:
        st.title("Scientific Calculator")
        settings.default_mode = st.segmented_control(
            "Mode",
            ["Standard", "Scientific", "Programmer"],
            default=settings.default_mode,
        )
        settings.angle_unit = st.segmented_control(
            "Angle",
            ["Degree", "Radian", "Gradian"],
            default=settings.angle_unit,
        )
        settings.display_format = st.selectbox(
            "Display format",
            ["Decimal", "Scientific", "Engineering", "Fraction"],
            index=["Decimal", "Scientific", "Engineering", "Fraction"].index(settings.display_format),
        )
        settings.precision = st.slider("Precision", min_value=0, max_value=15, value=settings.precision)
        settings.word_size = st.select_slider("Word size", options=[8, 16, 32, 64], value=settings.word_size)
        settings.theme = st.selectbox("Theme", ["System", "Light", "Dark"], index=["System", "Light", "Dark"].index(settings.theme))
        st.caption("History, memory, and settings are stored locally under the repo data folder.")

        st.subheader("Memory")
        st.write(f"M = {st.session_state.memory['registers']['M']}")
        mem_cols = st.columns(4)
        for index, operation in enumerate(["M+", "M-", "MR", "MC"]):
            if mem_cols[index].button(operation, use_container_width=True):
                update_memory(operation)

        st.subheader("Constants")
        search_term = st.text_input("Find a constant", key="constant-search")
        for constant in constant_search(search_term)[:8]:
            if st.button(f"{constant.label} ({constant.category})", use_container_width=True, key=f"constant-{constant.key}"):
                insert_token(constant.key)

        st.subheader("Unit converter")
        converter_categories = ["Length", "Mass", "Temperature", "Time", "Speed", "Energy", "Pressure", "Data Storage", "Angle"]
        category = st.selectbox("Category", converter_categories)
        defaults = {
            "Length": ("cm", "in"),
            "Mass": ("lb", "kg"),
            "Temperature": ("c", "f"),
            "Time": ("min", "s"),
            "Speed": ("kmph", "mph"),
            "Energy": ("j", "kj"),
            "Pressure": ("pa", "bar"),
            "Data Storage": ("mb", "gb"),
            "Angle": ("deg", "rad"),
        }
        from_unit, to_unit = defaults[category]
        value = st.number_input("Value", value=100.0)
        unit_choices = {
            "Length": ["mm", "cm", "m", "km", "in", "ft", "yd", "mi"],
            "Mass": ["g", "kg", "oz", "lb"],
            "Temperature": ["c", "f", "k"],
            "Time": ["s", "min", "h", "day"],
            "Speed": ["mps", "kmph", "mph"],
            "Energy": ["j", "kj", "wh"],
            "Pressure": ["pa", "kpa", "bar"],
            "Data Storage": ["b", "kb", "mb", "gb"],
            "Angle": ["deg", "rad", "grad"],
        }
        from_unit = st.selectbox("From", unit_choices[category], index=unit_choices[category].index(from_unit))
        to_unit = st.selectbox("To", unit_choices[category], index=unit_choices[category].index(to_unit))
        if st.button("Convert", use_container_width=True):
            converted, _, formula = convert_value(value, from_unit, to_unit)
            st.session_state.status_message = f"{value} {from_unit} = {converted:.6g} {to_unit} | {formula}"

        st.subheader("Export")
        for kind in ["txt", "pdf", "json"]:
            path = export_history(kind) if st.button(f"Export {kind.upper()}", use_container_width=True, key=f"export-{kind}") else None
            if path:
                st.session_state.status_message = f"Saved {path.name}"

        persist()


def render_history() -> None:
    st.subheader("History")
    if not st.session_state.history:
        st.info("Your calculation history will appear here. Start calculating!")
        return
    for index, entry in enumerate(st.session_state.history[:20]):
        cols = st.columns([6, 2, 1])
        if cols[0].button(f"{entry.expression} = {entry.result}", use_container_width=True, key=f"history-load-{entry.id}"):
            set_expression(entry.expression)
        cols[1].caption(entry.timestamp.replace("T", " "))
        if cols[2].button("Del", key=f"history-delete-{entry.id}"):
            del st.session_state.history[index]
            persist()
            st.rerun()
    if st.button("Clear history", use_container_width=False):
        st.session_state.history = []
        persist()
        st.rerun()


def render_programmer_view() -> None:
    try:
        value = int(float(st.session_state.memory.get("ans", 0.0)))
    except Exception:
        value = 0
    st.subheader("Programmer Bases")
    bases = display_in_bases(value, st.session_state.settings.word_size)
    columns = st.columns(4)
    for index, (base, rendered) in enumerate(bases.items()):
        columns[index].metric(base, rendered)


init_state()
render_sidebar()

st.title("Scientific Calculator")
st.caption("Standard, scientific, and programmer modes with local history, constants, conversion, and export.")

display_cols = st.columns([5, 1, 1, 1])
expression = display_cols[0].text_input("Expression", value=st.session_state.expression, key="expression-input")
st.session_state.expression = expression
if display_cols[1].button("⌫", use_container_width=True):
    st.session_state.expression = st.session_state.expression[:-1]
if display_cols[2].button("C", use_container_width=True):
    clear_expression()
if display_cols[3].button("AC", use_container_width=True):
    clear_all()

st.code(st.session_state.result_text, language=None)
if st.session_state.status_message:
    st.caption(st.session_state.status_message)

action_cols = st.columns([2, 2, 2, 3])
if action_cols[0].button("=", use_container_width=True):
    evaluate_current_expression()
if action_cols[1].button("Insert Ans", use_container_width=True):
    insert_token("Ans")
if action_cols[2].button("Copy result", use_container_width=True):
    st.session_state.copied_result = st.session_state.result_text
    st.session_state.status_message = f"Copied result: {st.session_state.copied_result}"
action_cols[3].caption("Inline conversion example: 150 lb to kg")

render_keypad(st.session_state.settings.default_mode)
if st.session_state.settings.default_mode == "Programmer":
    render_programmer_view()
render_history()
