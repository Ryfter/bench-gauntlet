import httpx
import pytest

from gauntlet.client import OpenAIClient
from gauntlet.scoring.judge import parse_verdict, score_with_judge, select_judge


def test_parse_verdict_reads_score_and_passed():
    score, passed = parse_verdict('{"score": 0.8, "passed": true, "reason": "ok"}')
    assert score == 0.8
    assert passed is True


def test_parse_verdict_tolerates_fences_and_prose():
    score, passed = parse_verdict('Here:\n```json\n{"score": 1, "passed": true}\n```')
    assert score == 1.0
    assert passed is True


def test_parse_verdict_clamps_and_derives_passed_from_threshold():
    # passed omitted -> derived from score >= 0.5
    score, passed = parse_verdict('{"score": 0.4}')
    assert score == 0.4
    assert passed is False


def test_parse_verdict_strips_think_tags():
    text = "<think>Let me evaluate... score seems 0.8</think>\n{\"score\": 0.8, \"passed\": true}"
    score, passed = parse_verdict(text)
    assert score == 0.8
    assert passed is True


def test_parse_verdict_strips_think_tags_with_inner_braces():
    text = "<think>I'll use {rubric} carefully to decide {score: high}</think>{\"score\": 0.5}"
    score, passed = parse_verdict(text)
    assert score == 0.5


def test_parse_verdict_bad_json_raises():
    with pytest.raises(ValueError):
        parse_verdict("not a verdict")


def test_select_judge_avoids_same_family():
    candidates = [("gemma3:12b", "gemma3"), ("dolphin3:8b", "llama")]
    assert select_judge(candidates, target_family="gemma3") == "dolphin3:8b"


def test_select_judge_none_when_all_same_family():
    candidates = [("gemma3:12b", "gemma3")]
    assert select_judge(candidates, target_family="gemma3") is None


def test_score_with_judge_calls_model_and_returns_caseresult():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"score": 0.9, "passed": true}'}}],
        })

    client = OpenAIClient(base_url="http://j:1", transport=httpx.MockTransport(handler))
    res = score_with_judge(client, judge_model="dolphin3:8b",
                           rubric="grade completeness", output="some answer", case_id="c1")
    assert res.case_id == "c1"
    assert res.method == "judge"
    assert res.score == 0.9
    assert res.passed is True


def test_score_with_judge_unparseable_marks_unscored():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "garbage"}}]})

    client = OpenAIClient(base_url="http://j:1", transport=httpx.MockTransport(handler))
    res = score_with_judge(client, judge_model="dolphin3:8b",
                           rubric="x", output="y", case_id="c2")
    assert res.score is None       # unscored — never silently 0
    assert res.passed is False
    assert "unscored" in res.detail
