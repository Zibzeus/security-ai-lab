from app.config import Settings
from app.llm import LLMClient


def test_qwen_no_think_is_added_to_last_user_message() -> None:
    client = LLMClient(Settings(llm_disable_thinking=True))
    messages = [{"role": "user", "content": "Return JSON"}]
    prepared = client.prepare_messages(messages)
    assert prepared[-1]["content"].endswith("/no_think")
    assert messages[-1]["content"] == "Return JSON"


def test_no_think_can_be_overridden_per_call() -> None:
    client = LLMClient(Settings(llm_disable_thinking=True))
    prepared = client.prepare_messages(
        [{"role": "user", "content": "Return report"}],
        disable_thinking=False,
    )
    assert "/no_think" not in prepared[-1]["content"]


def test_thinking_block_is_stripped_before_json_parse() -> None:
    content = '<think>private reasoning</think>\n{"status":"ok"}'
    assert LLMClient.strip_thinking(content) == '{"status":"ok"}'
    assert LLMClient.parse_json(content) == {"status": "ok"}
