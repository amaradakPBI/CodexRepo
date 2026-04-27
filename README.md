# CodexRepo

Streamlit chatbot UI built from the PRD for token streaming, provider switching, session history, attachments, telemetry, and export workflows.

## What is included

- Real-time streaming chat UI with provider, model, temperature, and max-token controls
- Editable system prompt with presets and optional context injection
- Sidebar conversation list with rename, clear, delete, JSON export, and Markdown export
- Attachment support for `.txt`, `.md`, and small `.pdf` files with text extraction metadata
- Structured telemetry logging with latency, token, provider, model, error, retry, regenerate, and export tracking
- Local JSON transcript persistence under `data/conversations/`
- Provider adapters for OpenAI-compatible, Azure OpenAI, Anthropic, and custom OpenAI-compatible endpoints

## Project layout

- `app.py`: main Streamlit application
- `chatbot/`: adapters, storage, telemetry, attachment parsing, and data models
- `tests/`: small utility tests for storage and attachment handling

## Local run

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

2. Set the provider configuration you want to use:

   ```bash
   export PROVIDER=openai
   export OPENAI_API_KEY=your_key_here
   export DEFAULT_MODEL=gpt-4o-mini
   export STREAMING_ENABLED=true
   ```

   For custom OpenAI-compatible servers, also set:

   ```bash
   export PROVIDER=custom
   export API_BASE=http://localhost:8000/v1
   ```

   For Azure OpenAI:

   ```bash
   export PROVIDER=azure
   export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
   export AZURE_OPENAI_API_KEY=your_key_here
   export AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

   For Anthropic:

   ```bash
   export PROVIDER=anthropic
   export ANTHROPIC_API_KEY=your_key_here
   ```

3. Start the app on localhost:

   ```bash
   streamlit run app.py --server.address localhost --server.port 8501
   ```

4. Run tests:

   ```bash
   python -m pytest -q tests
   ```

## Notes

- The app intentionally avoids storing API keys in conversation history or telemetry logs.
- Conversation files are written only if `PERSIST_TO_DISK` is not disabled.
- This container could not install `streamlit`, `openai`, `anthropic`, or `pytest` because outbound package downloads were blocked, so local runtime verification here was limited to Python syntax compilation.
