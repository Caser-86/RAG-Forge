from ragforge.config import Settings
from ragforge.generator import OllamaGenerator, OfflineGenerator
from ragforge.models import Chunk, Evidence
from ragforge.grounding import score_calibration_status


class _Client:
    def __init__(self, response: str = "答案 [1]"):
        self.response = response
        self.calls = 0

    def generate(self, model, messages, *, stream=False):
        self.calls += 1
        return self.response


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "generation_backend": "ollama",
        "default_generation_model": "gemma3:4b",
        "allowed_generation_models": ["gemma3:4b"],
        "embedder_backend": "deterministic",
        "embedder_dim": 8,
        "use_rerank": False,
    }
    values.update(overrides)
    return Settings(**values)


def _evidence(score: float | None, *, kind: str | None = None) -> Evidence:
    return Evidence(
        chunk=Chunk(id="c1", doc_id="d1", title="doc", text="可靠证据"),
        rerank_score=score,
        score_kind={"rerank": kind} if kind else {},
    )


def test_empty_evidence_refuses_without_calling_generation():
    client = _Client()
    generator = OllamaGenerator(_settings(), client=client)

    answer = generator.generate("没有资料的问题", [], "trace-empty")

    assert client.calls == 0
    assert answer.refused is True
    assert answer.refusal_reason == "no_evidence"


def test_zero_normalized_rerank_score_is_not_treated_as_unexecuted():
    generator = OfflineGenerator(_settings(refuse_threshold=0.15))

    answer = generator.generate("问题", [_evidence(0.0, kind="normalized")], "trace-zero")

    assert answer.refused is True
    assert answer.refusal_reason == "insufficient_confidence"


def test_negative_raw_rerank_logit_is_not_clipped_to_zero_probability():
    generator = OfflineGenerator(_settings(refuse_threshold=0.15))

    answer = generator.generate("问题", [_evidence(-4.0, kind="cross_encoder_raw")], "trace-logit")

    assert answer.refused is False
    assert answer.refusal_reason is None
    assert answer.grounded is True


def test_model_claiming_insufficient_information_is_refused():
    client = _Client("信息不足，无法回答。[1]")
    generator = OllamaGenerator(_settings(), client=client)

    answer = generator.generate("问题", [_evidence(None)], "trace-self-refuse")

    assert answer.refused is True
    assert answer.refusal_reason == "model_declared_insufficient"


def test_missing_error_code_constraint_is_refused_without_literal_matching_all_words():
    generator = OfflineGenerator(_settings(generation_backend="offline"))

    answer = generator.generate(
        "错误码 E9001 的修复步骤是什么？",
        [_evidence(None)],
        "trace-support",
    )

    assert answer.refused is True
    assert answer.refusal_reason == "insufficient_support"


def test_dense_cosine_and_raw_rerank_have_separate_uncalibrated_semantics():
    evidence = Evidence(
        chunk=Chunk(id="c1", doc_id="d1", title="doc", text="evidence"),
        dense_score=0.95,
        fused_score=0.02,
        rerank_score=-3.0,
        score_kind={"dense": "cosine", "fused": "rrf", "rerank": "cross_encoder_raw"},
    )

    assert score_calibration_status(evidence) == {
        "dense": "dense_cosine_uncalibrated",
        "fused": "rrf_rank_not_confidence",
        "rerank": "rerank_raw_uncalibrated",
    }
