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


def test_run_context_depth_finds_cutoff():
    import httpx

    from gauntlet.batteries.context_depth import run_context_depth
    from gauntlet.client import OpenAIClient

    # Simulate degradation: the model returns the needle only when the prompt is
    # short (<= 6000 chars). Longer haystacks "lose" it -> accuracy collapses.
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        text = DEFAULT_ANSWER if len(body) <= 6000 else "I could not find it."
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}],
                                         "usage": {"completion_tokens": 5}})
    client = OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))
    cd = run_context_depth(client, model="gemma3:1b", advertised=8192,
                           lengths=[500, 1000, 4000], depths=[0.0, 0.5, 1.0])
    assert cd.model == "gemma3:1b"
    assert cd.advertised == 8192
    # 500 & 1000-token prompts stay under 6000 chars (100% retrieval); 4000 tokens
    # (~16000 chars) collapses -> effective_90pct is the largest passing length.
    assert cd.effective_90pct == 1000
