from app.config import Settings
from app.llm import LLMClient


def test_qwen_no_think_is_added_to_last_user_message() -> None:
    client = LLMClient(Settings(llm_disable_thinking=True))
    messages = [{"role": "user", "content": "Return JSON"}]
    prepared = client.prepare_messages(messages)
    assert prepared[-1]["content"].endswith("/no_think")
    assert messages[-1]["content"] == "Return JSON"
