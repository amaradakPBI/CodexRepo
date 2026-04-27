"""UI text kept in one place to make later localization straightforward."""

TEXT = {
    "app_title": "Streamlit Chatbot UI",
    "app_subtitle": "Real-time token streaming with pluggable providers",
    "chat_placeholder": "Send a message",
    "empty_state_title": "Start a conversation",
    "empty_state_body": (
        "Pick a provider in the sidebar, adjust the prompt controls, and try one of the quick prompts."
    ),
    "provider_setup_title": "Provider setup required",
    "provider_setup_body": (
        "Set the provider environment variables in a local shell or Streamlit secrets before sending a message."
    ),
    "quick_prompts": [
        "Summarize the latest dashboard anomaly in plain English.",
        "Explain this SQL query and suggest two optimizations.",
        "Turn these notes into a concise support handoff.",
    ],
}
