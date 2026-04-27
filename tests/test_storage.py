from chatbot.models import Conversation, Message, MessageUsage, generate_id, utc_now_iso
from chatbot.storage import ConversationStore, conversation_to_markdown


def test_store_round_trip(tmp_path):
    store = ConversationStore(tmp_path)
    conversation = Conversation.create(
        provider="openai",
        model="gpt-4o-mini",
        parameters={"temperature": 0.7, "max_tokens": 512},
        system_prompt="You are helpful.",
    )
    conversation.turns.append(
        Message(
            id=generate_id(),
            role="assistant",
            content="Hello",
            created_at=utc_now_iso(),
            usage=MessageUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )
    )
    store.save(conversation)

    loaded = store.load_all()
    assert len(loaded) == 1
    assert loaded[0].turns[0].content == "Hello"


def test_markdown_export_contains_metadata():
    conversation = Conversation.create(
        provider="openai",
        model="gpt-4o-mini",
        parameters={"temperature": 0.7, "max_tokens": 512},
        system_prompt="You are helpful.",
    )
    markdown = conversation_to_markdown(conversation)
    assert "# " in markdown
    assert "Provider" in markdown
