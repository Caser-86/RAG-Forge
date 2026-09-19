from ragforge.config import Settings
from ragforge.query_rewriter import QueryRewriter


class _Client:
    def __init__(self, response: str = "BGE-M3 E9001 配置"):
        self.response = response
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def generate(self, model, messages, *, stream=False):
        self.calls.append((model, messages))
        return self.response


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "embedder_backend": "deterministic",
        "embedder_dim": 8,
        "generation_backend": "offline",
        "rewrite_enabled": False,
        "rewrite_model": "qwen3:0.6b",
        "rewrite_max_chars": 200,
        "rewrite_history_max_messages": 4,
    }
    values.update(overrides)
    return Settings(**values)


def test_rewrite_off_does_not_call_utility_model():
    client = _Client()
    rewriter = QueryRewriter(_settings(), client=client)

    assert rewriter.rewrite("原问题", [{"role": "user", "content": "上一轮"}]) == "原问题"
    assert client.calls == []
    assert rewriter.last_result.fallback is True
    assert rewriter.last_result.reason == "disabled"


def test_rewrite_uses_fixed_utility_model_and_returns_one_query():
    client = _Client("BGE-M3 E9001 配置")
    rewriter = QueryRewriter(_settings(rewrite_enabled=True), client=client)

    result = rewriter.rewrite("请查 BGE-M3 的 E9001 配置", [])

    assert result == "BGE-M3 E9001 配置"
    assert client.calls[0][0] == "qwen3:0.6b"
    assert rewriter.last_result.fallback is False


def test_rewrite_preserves_critical_error_code_and_version_or_falls_back():
    client = _Client("只保留了产品名")
    rewriter = QueryRewriter(_settings(rewrite_enabled=True), client=client)

    result = rewriter.rewrite("请查 RAG-Forge v2 的错误码 E9001", [])

    assert result == "请查 RAG-Forge v2 的错误码 E9001"
    assert rewriter.last_result.reason == "critical_token_dropped"


def test_invalid_utility_outputs_fall_back_without_being_used_as_query():
    for response, reason in (
        ("", "empty_output"),
        ("<think>secret reasoning</think> BGE-M3", "think_output"),
        ("<query>BGE-M3</query>", "structured_output"),
        ("RAG-Forge error code 0", "new_numeric_fact"),
        ("BGE-M3 1024", "new_numeric_fact"),
        ("原问题中的关键限定未提供，无法确认", "prompt_leak"),
        ("第一段\n第二段", "multi_line_output"),
        ("x" * 201, "too_long"),
    ):
        rewriter = QueryRewriter(
            _settings(rewrite_enabled=True),
            client=_Client(response),
        )
        result = rewriter.rewrite("BGE-M3", [])

        assert result == "BGE-M3"
        assert rewriter.last_result.fallback is True
        assert rewriter.last_result.reason == reason


def test_history_is_bounded_before_utility_call():
    client = _Client("BGE-M3 配置")
    rewriter = QueryRewriter(_settings(rewrite_enabled=True), client=client)
    history = [{"role": "user", "content": str(index)} for index in range(20)]

    rewriter.rewrite("BGE-M3", history)

    user_message = client.calls[0][1][1]["content"]
    assert "19" in user_message
    assert "0" not in user_message
