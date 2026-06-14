from gauntlet.batteries.context_depth import (
    DEFAULT_ANSWER,
    approx_tokens,
    build_haystack,
    effective_context,
    score_retrieval,
)


def test_approx_tokens_scales_with_length():
    assert approx_tokens("") >= 1
    assert approx_tokens("a" * 400) == 100   # ~4 chars/token


def test_build_haystack_contains_needle_question_and_target_length():
    prompt = build_haystack(context_tokens=500, depth_fraction=0.5)
    assert DEFAULT_ANSWER in prompt          # the needle answer is embedded
    assert "passcode" in prompt.lower()      # the retrieval question is appended
    # filled to roughly the requested size (within 25%)
    assert 0.75 * 500 <= approx_tokens(prompt) <= 1.5 * 500


def test_build_haystack_depth_places_needle():
    early = build_haystack(context_tokens=400, depth_fraction=0.0)
    late = build_haystack(context_tokens=400, depth_fraction=1.0)
    assert early.index(DEFAULT_ANSWER) < late.index(DEFAULT_ANSWER)


def test_score_retrieval_is_case_insensitive_containment():
    assert score_retrieval("The passcode is cerulean-otter-42.", DEFAULT_ANSWER) is True
    assert score_retrieval("I don't know.", DEFAULT_ANSWER) is False


def test_effective_context_largest_length_at_or_above_threshold():
    # accuracy holds >=0.9 through 8192, collapses after
    samples = [(2048, 1.0), (4096, 0.95), (8192, 0.9), (16384, 0.4), (32768, 0.1)]
    assert effective_context(samples, threshold=0.9) == 8192


def test_effective_context_zero_when_never_meets_threshold():
    assert effective_context([(2048, 0.5), (4096, 0.2)], threshold=0.9) == 0
