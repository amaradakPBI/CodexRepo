from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

import streamlit as st
import streamlit.components.v1 as components

from chatbot.adapters import AdapterError, get_adapter
from chatbot.attachments import AttachmentPayload, build_attachment_context, parse_uploads
from chatbot.config import SYSTEM_PROMPT_PRESETS, load_config
from chatbot.models import (
    Conversation,
    Message,
    MessageUsage,
    derive_title,
    generate_id,
    utc_now_iso,
)
from chatbot.storage import ConversationStore, conversation_to_markdown
from chatbot.telemetry import build_logger, log_event, sanitize_text
from chatbot.ui_text import TEXT


REPO_ROOT = Path(__file__).resolve().parent
CONFIG = load_config(REPO_ROOT)
STORE = ConversationStore(CONFIG.storage_dir)
LOGGER = build_logger(CONFIG.log_file, CONFIG.log_level)

st.set_page_config(
    page_title=TEXT["app_title"],
    page_icon="💬",
    layout="wide",
)


def init_state() -> None:
    if "conversations" not in st.session_state:
        st.session_state.conversations = {
            conversation.id: conversation for conversation in STORE.load_all()
        }
    if "current_id" not in st.session_state:
        existing_ids = list(st.session_state.conversations.keys())
        if existing_ids:
            st.session_state.current_id = existing_ids[0]
        else:
            create_new_conversation()
    if "run" not in st.session_state:
        st.session_state.run = None
    if "last_submit_at" not in st.session_state:
        st.session_state.last_submit_at = 0.0
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = SYSTEM_PROMPT_PRESETS["General Assistant"]
    if "font_scale" not in st.session_state:
        st.session_state.font_scale = 1.0
    if "status_message" not in st.session_state:
        st.session_state.status_message = ""


def current_conversation() -> Conversation:
    return st.session_state.conversations[st.session_state.current_id]


def save_conversation(conversation: Conversation) -> None:
    conversation.updated_at = utc_now_iso()
    st.session_state.conversations[conversation.id] = conversation
    if CONFIG.persist_to_disk:
        STORE.save(conversation)


def create_new_conversation() -> None:
    conversation = Conversation.create(
        provider=CONFIG.provider,
        model=CONFIG.default_model,
        parameters={
            "temperature": CONFIG.default_temperature,
            "max_tokens": CONFIG.max_tokens,
        },
        system_prompt=SYSTEM_PROMPT_PRESETS["General Assistant"],
    )
    st.session_state.conversations = getattr(st.session_state, "conversations", {})
    st.session_state.conversations[conversation.id] = conversation
    st.session_state.current_id = conversation.id
    save_conversation(conversation)


def provider_ready(provider: str) -> tuple[bool, str | None]:
    adapter = get_adapter(
        provider=provider,
        openai_api_key=CONFIG.openai_api_key,
        anthropic_api_key=CONFIG.anthropic_api_key,
        api_base=CONFIG.api_base,
        azure_endpoint=CONFIG.azure_endpoint,
        azure_api_key=CONFIG.azure_api_key,
        azure_api_version=CONFIG.azure_api_version,
    )
    return adapter.check_ready()


def build_messages(
    conversation: Conversation,
    *,
    system_prompt: str,
    include_context: bool,
    context_text: str,
    attachments: list[AttachmentPayload],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    system_content = system_prompt.strip()
    if include_context:
        extra_context = []
        if context_text.strip():
            extra_context.append(context_text.strip())
        attachment_context = build_attachment_context(attachments)
        if attachment_context:
            extra_context.append(attachment_context)
        if extra_context:
            system_content = (
                f"{system_content}\n\nContext:\n" + "\n\n".join(extra_context)
                if system_content
                else "\n\n".join(extra_context)
            )
    if system_content:
        messages.append({"role": "system", "content": system_content})
    for turn in conversation.turns:
        if turn.role == "assistant" and turn.meta.get("status") == "streaming":
            continue
        messages.append({"role": turn.role, "content": turn.content})
    return messages


def start_generation(
    *,
    prompt: str,
    provider: str,
    model: str,
    temperature: float,
    max_tokens: int,
    system_prompt: str,
    include_context: bool,
    context_text: str,
    attachments: list[AttachmentPayload],
    retry_kind: str | None = None,
) -> None:
    conversation = current_conversation()
    conversation.provider = provider
    conversation.model = model
    conversation.parameters = {"temperature": temperature, "max_tokens": max_tokens}
    conversation.system_prompt = system_prompt
    if prompt:
        user_turn = Message(
            id=generate_id(),
            role="user",
            content=prompt,
            created_at=utc_now_iso(),
            attachments=[payload.meta for payload in attachments],
        )
        conversation.turns.append(user_turn)
        if conversation.title == "Untitled conversation":
            conversation.title = derive_title(prompt)
    elif retry_kind == "retry":
        conversation.metrics.retries += 1
    elif retry_kind == "regenerate":
        conversation.metrics.regenerations += 1

    assistant_turn = Message(
        id=generate_id(),
        role="assistant",
        content="",
        created_at=utc_now_iso(),
        meta={"status": "streaming"},
    )
    conversation.turns.append(assistant_turn)
    save_conversation(conversation)

    cancel_event = Event()
    queue: Queue = Queue()
    adapter = get_adapter(
        provider=provider,
        openai_api_key=CONFIG.openai_api_key,
        anthropic_api_key=CONFIG.anthropic_api_key,
        api_base=CONFIG.api_base,
        azure_endpoint=CONFIG.azure_endpoint,
        azure_api_key=CONFIG.azure_api_key,
        azure_api_version=CONFIG.azure_api_version,
    )
    messages = build_messages(
        conversation,
        system_prompt=system_prompt,
        include_context=include_context,
        context_text=context_text,
        attachments=attachments,
    )

    def worker() -> None:
        start_time = time.perf_counter()
        first_token_at = None
        output_chunks: list[str] = []
        try:
            for chunk in adapter.stream(
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
                output_chunks.append(chunk)
                queue.put({"type": "chunk", "text": chunk})
            if cancel_event.is_set():
                prompt_tokens = sum(len(message.get("content", "").split()) for message in messages)
                completion_tokens = len("".join(output_chunks).split())
                queue.put(
                    {
                        "type": "stopped",
                        "text": "".join(output_chunks),
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens,
                        },
                    }
                )
                return
            end_time = time.perf_counter()
            prompt_tokens = sum(len(message.get("content", "").split()) for message in messages)
            completion_tokens = len("".join(output_chunks).split())
            queue.put(
                {
                    "type": "done",
                    "text": "".join(output_chunks),
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                    },
                    "latency_ms": (end_time - start_time) * 1000,
                    "ttfb_ms": ((first_token_at or end_time) - start_time) * 1000,
                    "started_at": start_time,
                }
            )
        except Exception as exc:  # pragma: no cover - runtime safety
            queue.put({"type": "error", "message": sanitize_text(str(exc))})

    thread = Thread(target=worker, daemon=True)
    thread.start()
    st.session_state.run = {
        "thread": thread,
        "queue": queue,
        "cancel_event": cancel_event,
        "conversation_id": conversation.id,
        "assistant_turn_id": assistant_turn.id,
        "provider": provider,
        "model": model,
        "started_at": time.perf_counter(),
        "attachments": [asdict(payload.meta) for payload in attachments],
    }
    st.session_state.status_message = "Generating response..."


def stop_generation() -> None:
    run = st.session_state.get("run")
    if run:
        run["cancel_event"].set()
        st.session_state.status_message = "Stopping..."


def finalize_run(event: dict) -> None:
    run = st.session_state.get("run")
    if not run:
        return
    conversation = st.session_state.conversations[run["conversation_id"]]
    assistant_turn = next(
        turn for turn in conversation.turns if turn.id == run["assistant_turn_id"]
    )
    if event["type"] == "chunk":
        assistant_turn.content += event["text"]
        assistant_turn.meta["status"] = "streaming"
        save_conversation(conversation)
        return
    if event["type"] == "done":
        assistant_turn.content = event["text"]
        assistant_turn.usage = MessageUsage(**event["usage"])
        assistant_turn.meta["status"] = "done"
        conversation.metrics.requests += 1
        conversation.metrics.prompt_tokens += event["usage"]["prompt_tokens"]
        conversation.metrics.completion_tokens += event["usage"]["completion_tokens"]
        conversation.metrics.total_tokens += event["usage"]["total_tokens"]
        conversation.metrics.avg_latency_ms = (
            (
                (conversation.metrics.avg_latency_ms * (conversation.metrics.requests - 1))
                + event["latency_ms"]
            )
            / conversation.metrics.requests
        )
        conversation.metrics.avg_ttfb_ms = (
            (
                (conversation.metrics.avg_ttfb_ms * (conversation.metrics.requests - 1))
                + event["ttfb_ms"]
            )
            / conversation.metrics.requests
        )
        log_event(
            LOGGER,
            "turn_completed",
            {
                "conversation_id": conversation.id,
                "provider": conversation.provider,
                "model": conversation.model,
                "latency_ms": round(event["latency_ms"], 2),
                "ttfb_ms": round(event["ttfb_ms"], 2),
                "prompt_tokens": event["usage"]["prompt_tokens"],
                "completion_tokens": event["usage"]["completion_tokens"],
                "total_tokens": event["usage"]["total_tokens"],
                "temperature": conversation.parameters["temperature"],
                "max_tokens": conversation.parameters["max_tokens"],
            },
        )
        st.session_state.status_message = "Response completed."
    elif event["type"] == "stopped":
        assistant_turn.content = event["text"]
        assistant_turn.usage = MessageUsage(**event["usage"])
        assistant_turn.stopped = True
        assistant_turn.meta["status"] = "stopped"
        conversation.metrics.cancel_count += 1
        st.session_state.status_message = "Generation stopped."
    elif event["type"] == "error":
        assistant_turn.error = event["message"]
        assistant_turn.content = f"Error: {event['message']}"
        assistant_turn.meta["status"] = "error"
        conversation.metrics.errors += 1
        log_event(
            LOGGER,
            "turn_failed",
            {
                "conversation_id": conversation.id,
                "provider": conversation.provider,
                "model": conversation.model,
                "error": event["message"],
            },
        )
        st.session_state.status_message = "Request failed."
    save_conversation(conversation)
    st.session_state.run = None


def drain_run_events() -> None:
    run = st.session_state.get("run")
    if not run:
        return
    queue = run["queue"]
    while True:
        try:
            event = queue.get_nowait()
        except Empty:
            break
        finalize_run(event)


def render_message(turn: Message) -> None:
    avatar = "🧑" if turn.role == "user" else "🤖"
    with st.chat_message(turn.role, avatar=avatar):
        role_label = "User" if turn.role == "user" else "Assistant"
        columns = st.columns([8, 1])
        columns[0].markdown(f"**{role_label}**")
        columns[1].caption("Copy")
        components.html(
            f"""
            <button
              style="width:100%;padding:0.35rem 0.5rem;border:1px solid #ccc;border-radius:0.4rem;background:#fff;cursor:pointer;"
              onclick="navigator.clipboard.writeText({json.dumps(turn.content)})"
              aria-label="Copy {role_label} message to clipboard"
            >Copy</button>
            """,
            height=44,
        )
        st.markdown(turn.content or "_Thinking..._")
        if turn.attachments:
            chip_text = ", ".join(
                f"{attachment.name} ({attachment.chars} chars)"
                for attachment in turn.attachments
            )
            st.caption(f"Attachments: {chip_text}")
        if turn.usage:
            st.caption(
                "Tokens: "
                f"{turn.usage.prompt_tokens} prompt / "
                f"{turn.usage.completion_tokens} completion / "
                f"{turn.usage.total_tokens} total"
            )
        if turn.stopped:
            st.info("Generation was stopped before completion.")
        if turn.error:
            st.error(turn.error)


def render_sidebar() -> tuple[str, str, float, int, str, bool, str, list[AttachmentPayload]]:
    conversation = current_conversation()
    st.sidebar.title("Settings")
    provider = st.sidebar.selectbox(
        "Provider",
        ["openai", "azure", "anthropic", "custom"],
        index=["openai", "azure", "anthropic", "custom"].index(conversation.provider),
    )
    model = st.sidebar.text_input("Model", value=conversation.model or CONFIG.default_model)
    temperature = st.sidebar.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=float(conversation.parameters.get("temperature", CONFIG.default_temperature)),
        step=0.1,
    )
    max_tokens = st.sidebar.number_input(
        "Max tokens",
        min_value=64,
        max_value=4096,
        value=int(conversation.parameters.get("max_tokens", CONFIG.max_tokens)),
        step=64,
    )
    preset = st.sidebar.selectbox("System prompt preset", list(SYSTEM_PROMPT_PRESETS.keys()))
    if st.sidebar.button("Apply preset"):
        st.session_state.system_prompt = SYSTEM_PROMPT_PRESETS[preset]
    system_prompt = st.sidebar.text_area(
        "System prompt",
        key="system_prompt",
        height=180,
    )
    include_context = st.sidebar.toggle("Include context", value=False)
    context_text = st.sidebar.text_area("Context text", height=120, disabled=not include_context)
    uploaded_files = st.sidebar.file_uploader(
        "Attachments (.txt, .md, .pdf)",
        type=["txt", "md", "pdf"],
        accept_multiple_files=True,
    )
    attachments: list[AttachmentPayload] = []
    if uploaded_files:
        try:
            attachments = parse_uploads(uploaded_files, CONFIG.max_upload_mb)
        except ValueError as exc:
            st.sidebar.error(str(exc))
    if attachments:
        for payload in attachments:
            st.sidebar.caption(
                f"{payload.meta.name}: {payload.meta.size_bytes} bytes, {payload.meta.chars} extracted chars"
            )
    st.sidebar.divider()
    st.sidebar.subheader("Conversations")
    if st.sidebar.button("New conversation", use_container_width=True):
        create_new_conversation()
        st.rerun()
    conversation_ids = list(st.session_state.conversations.keys())
    selected_id = st.sidebar.radio(
        "Conversation list",
        options=conversation_ids,
        format_func=lambda cid: st.session_state.conversations[cid].title,
        index=conversation_ids.index(st.session_state.current_id),
    )
    st.session_state.current_id = selected_id
    rename_value = st.sidebar.text_input("Rename conversation", value=current_conversation().title)
    if st.sidebar.button("Save title", use_container_width=True):
        current_conversation().title = rename_value.strip() or "Untitled conversation"
        save_conversation(current_conversation())
        st.rerun()
    if st.sidebar.button("Clear current conversation", use_container_width=True):
        current_conversation().turns = []
        save_conversation(current_conversation())
        st.rerun()
    if st.sidebar.button("Delete current conversation", use_container_width=True):
        STORE.delete(current_conversation().id)
        del st.session_state.conversations[current_conversation().id]
        if not st.session_state.conversations:
            create_new_conversation()
        else:
            st.session_state.current_id = next(iter(st.session_state.conversations))
        st.rerun()
    export_json = json.dumps(current_conversation().to_dict(), indent=2)
    export_markdown = conversation_to_markdown(current_conversation())
    if st.sidebar.download_button(
        "Export JSON",
        data=export_json.encode("utf-8"),
        file_name=f"{current_conversation().id}.json",
        mime="application/json",
        use_container_width=True,
    ):
        current_conversation().metrics.exports += 1
        save_conversation(current_conversation())
    if st.sidebar.download_button(
        "Export Markdown",
        data=export_markdown.encode("utf-8"),
        file_name=f"{current_conversation().id}.md",
        mime="text/markdown",
        use_container_width=True,
    ):
        current_conversation().metrics.exports += 1
        save_conversation(current_conversation())

    st.sidebar.divider()
    st.sidebar.subheader("Session stats")
    metrics = current_conversation().metrics
    st.sidebar.metric("Requests", metrics.requests)
    st.sidebar.metric("Avg latency", f"{metrics.avg_latency_ms:.0f} ms")
    st.sidebar.metric("Avg TTFB", f"{metrics.avg_ttfb_ms:.0f} ms")
    st.sidebar.metric("Errors", metrics.errors)
    st.sidebar.metric("Tokens", metrics.total_tokens)
    st.sidebar.metric("Exports", metrics.exports)

    st.sidebar.divider()
    st.sidebar.subheader("Accessibility")
    st.session_state.font_scale = st.sidebar.slider(
        "Font size",
        min_value=0.9,
        max_value=1.4,
        value=float(st.session_state.font_scale),
        step=0.05,
    )
    st.sidebar.caption("Live status updates appear in the main pane during generation.")

    st.sidebar.divider()
    st.sidebar.caption(
        "Provider data usage notices: "
        "[OpenAI](https://openai.com/policies), "
        "[Anthropic](https://www.anthropic.com/legal/privacy), "
        "[Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/faq)."
    )
    return provider, model, temperature, int(max_tokens), system_prompt, include_context, context_text, attachments


@st.fragment(run_every="500ms")
def render_transcript() -> None:
    drain_run_events()
    conversation = current_conversation()
    for turn in conversation.turns:
        render_message(turn)
    run = st.session_state.get("run")
    if run and run["conversation_id"] == conversation.id:
        active_text = next(
            (turn.content for turn in conversation.turns if turn.id == run["assistant_turn_id"]),
            "",
        )
        elapsed_seconds = max(time.perf_counter() - run["started_at"], 0.001)
        token_rate = len(active_text.split()) / elapsed_seconds
        st.status(
            f"{st.session_state.status_message or 'Generating...'} "
            f"Approx. {token_rate:.1f} tokens/sec",
            expanded=False,
        )
        if st.button("Stop generation", key="stop-generation", use_container_width=True):
            stop_generation()


def retry_last(kind: str) -> None:
    conversation = current_conversation()
    if st.session_state.get("run"):
        st.warning("Wait for the current response to finish or stop it first.")
        return
    last_user = next((turn for turn in reversed(conversation.turns) if turn.role == "user"), None)
    if not last_user:
        st.warning("There is no user message to retry yet.")
        return
    if conversation.turns and conversation.turns[-1].role == "assistant":
        conversation.turns.pop()
    save_conversation(conversation)
    sidebar_values = st.session_state.get("_sidebar_values")
    if not sidebar_values:
        return
    start_generation(
        prompt="",
        provider=sidebar_values["provider"],
        model=sidebar_values["model"],
        temperature=sidebar_values["temperature"],
        max_tokens=sidebar_values["max_tokens"],
        system_prompt=sidebar_values["system_prompt"],
        include_context=sidebar_values["include_context"],
        context_text=sidebar_values["context_text"],
        attachments=[],
        retry_kind=kind,
    )
    st.rerun()


def main() -> None:
    init_state()
    st.markdown(
        f"""
        <style>
        :root {{ --font-scale: {st.session_state.font_scale}; }}
        .stApp {{
            font-size: calc(1rem * var(--font-scale));
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    provider, model, temperature, max_tokens, system_prompt, include_context, context_text, attachments = render_sidebar()
    st.session_state["_sidebar_values"] = {
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt,
        "include_context": include_context,
        "context_text": context_text,
    }
    ready, readiness_message = provider_ready(provider)

    title_col, badge_col = st.columns([4, 1])
    title_col.title(TEXT["app_title"])
    title_col.caption(TEXT["app_subtitle"])
    badge_col.metric("Model", model)

    if st.session_state.status_message:
        st.caption(st.session_state.status_message)

    if not current_conversation().turns:
        st.info(TEXT["empty_state_title"])
        st.write(TEXT["empty_state_body"])
        for prompt in TEXT["quick_prompts"]:
            if st.button(prompt, key=f"quick-{prompt}", use_container_width=True):
                if not ready:
                    st.warning(readiness_message or TEXT["provider_setup_body"])
                    break
                start_generation(
                    prompt=prompt,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    include_context=include_context,
                    context_text=context_text,
                    attachments=[],
                )
                st.rerun()

    if not ready:
        with st.expander(TEXT["provider_setup_title"], expanded=True):
            st.write(TEXT["provider_setup_body"])
            st.code(
                "\n".join(
                    [
                        "PROVIDER=openai|azure|anthropic|custom",
                        "DEFAULT_MODEL=gpt-4o-mini",
                        "STREAMING_ENABLED=true",
                        "OPENAI_API_KEY=...",
                        "API_BASE=https://api.openai.com/v1  # optional for custom servers",
                        "AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com",
                        "AZURE_OPENAI_API_VERSION=2024-02-15-preview",
                        "ANTHROPIC_API_KEY=...",
                    ]
                )
            )

    render_transcript()

    action_cols = st.columns([1, 1, 1])
    if action_cols[0].button("Retry last", use_container_width=True):
        retry_last("retry")
    if action_cols[1].button("Regenerate", use_container_width=True):
        retry_last("regenerate")
    token_counter = sum(len(turn.content) for turn in current_conversation().turns)
    action_cols[2].metric("Characters", token_counter)

    prompt = st.chat_input(TEXT["chat_placeholder"], disabled=not ready or bool(st.session_state.get("run")))
    if prompt:
        now_ms = time.time() * 1000
        if now_ms - st.session_state.last_submit_at < CONFIG.min_submit_interval_ms:
            st.warning("Please wait a moment before sending another message.")
            return
        st.session_state.last_submit_at = now_ms
        try:
            start_generation(
                prompt=prompt,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                include_context=include_context,
                context_text=context_text,
                attachments=attachments,
            )
            st.rerun()
        except (AdapterError, ValueError) as exc:
            st.error(str(exc))


if __name__ == "__main__":
    main()
