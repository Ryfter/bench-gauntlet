import httpx

from gauntlet.battery import Battery, Case
from gauntlet.client import OpenAIClient
from gauntlet.runner import run_cell


def _client(reply_text):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": reply_text}}],
            "usage": {"completion_tokens": 7},
        })
    return OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))


def test_run_cell_scores_deterministic_cases(tmp_path):
    (tmp_path / "p.txt").write_text("write a commit message", encoding="utf-8")
    battery = Battery(capability="commit-msg",
                      cases=[Case(id="c1", scoring="conventional-commit", prompt_file="p.txt")])
    cell = run_cell(_client("feat: add the thing"), model="gemma3:1b", target="box-b",
                    box="RTX 2070 Super laptop", context=4096, battery=battery, base_dir=tmp_path)
    assert cell.capability == "commit-msg"
    assert cell.quality == 1.0
    assert cell.pass_rate == 1.0
    assert cell.cases == 1
    assert cell.errors == 0
    assert cell.tokens_per_s is not None and cell.tokens_per_s > 0


def test_run_cell_unreachable_marks_errored_cell(tmp_path):
    (tmp_path / "p.txt").write_text("hi", encoding="utf-8")
    def handler(request):
        raise httpx.ConnectError("refused")
    client = OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))
    battery = Battery(capability="commit-msg",
                      cases=[Case(id="c1", scoring="exact", expect="x", prompt_file="p.txt")])
    cell = run_cell(client, model="gemma3:1b", target="box-b", box="laptop",
                    context=4096, battery=battery, base_dir=tmp_path)
    assert cell.errors == 1
    assert cell.quality is None          # nothing scored
    assert cell.cases == 1


def test_run_cell_judge_uses_eligible_pool(tmp_path):
    (tmp_path / "p.txt").write_text("summarize", encoding="utf-8")
    # model under test is gemma3; judge pool offers a different family -> judged.
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        if "strict grader" in body:
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"score":0.8,"passed":true}'}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "some summary"}}],
                                         "usage": {"completion_tokens": 5}})
    client = OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))
    battery = Battery(capability="summarize",
                      cases=[Case(id="c1", scoring="judge", rubric="grade it", prompt_file="p.txt")])
    cell = run_cell(client, model="gemma3:1b", target="box-b", box="laptop", context=4096,
                    battery=battery, base_dir=tmp_path, judge_pool=[("dolphin3:8b", "dolphin3")])
    assert cell.quality == 0.8
    assert cell.judge == "dolphin3:8b"


def test_run_cell_no_eligible_judge_marks_unscored(tmp_path):
    (tmp_path / "p.txt").write_text("summarize", encoding="utf-8")
    battery = Battery(capability="summarize",
                      cases=[Case(id="c1", scoring="judge", rubric="grade it", prompt_file="p.txt")])
    cell = run_cell(_client("some summary"), model="gemma3:1b", target="box-b", box="laptop",
                    context=4096, battery=battery, base_dir=tmp_path,
                    judge_pool=[("gemma3:27b", "gemma3")])  # same family only
    assert cell.quality is None          # unscored, never silently 0
    assert cell.pass_rate == 0.0
    assert cell.cases == 1
