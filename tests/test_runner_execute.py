import httpx

from gauntlet.battery import Battery, Case
from gauntlet.config import Box, GauntletConfig, ModelProfile, Target
from gauntlet.runner import RunPaths, execute_plan, read_completed
from tests.helpers import sse


def _cfg():
    return GauntletConfig(
        targets=[Target(name="box-b", base_url="http://w:1", box="box-b")],
        boxes=[Box(id="box-b", hardware="RTX 2070 Super laptop", vram_gb=8, usage_class="broad")],
        models=[ModelProfile(target="box-b", id="gemma3:1b", context=4096)],
    )


def _batteries(tmp_path):
    (tmp_path / "p.txt").write_text("go", encoding="utf-8")
    return [Battery(capability="commit-msg",
                    cases=[Case(id="c1", scoring="conventional-commit", prompt_file="p.txt")])]


def _client_factory(text):
    def make(base_url, api_key=None):
        def handler(request):
            return httpx.Response(200, text=sse(text, completion_tokens=4))
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url, transport=httpx.MockTransport(handler))
    return make


def test_execute_plan_runs_all_cells_and_checkpoints(tmp_path):
    paths = RunPaths(tmp_path / "run-1")
    cells = execute_plan(_cfg(), _batteries(tmp_path), paths, base_dir=tmp_path,
                         client_factory=_client_factory("feat: x"))
    assert len(cells) == 1
    assert cells[0].quality == 1.0
    # checkpoint written
    assert read_completed(paths) == {("box-b", "gemma3:1b", 4096, "commit-msg")}


def test_execute_plan_resume_skips_completed(tmp_path):
    paths = RunPaths(tmp_path / "run-2")
    # first run completes the only cell
    execute_plan(_cfg(), _batteries(tmp_path), paths, base_dir=tmp_path,
                 client_factory=_client_factory("feat: x"))
    # second run with a client that would FAIL if called — proves the cell is skipped
    def exploding_factory(base_url, api_key=None):
        def handler(request):
            raise AssertionError("should not be called on resume")
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url, transport=httpx.MockTransport(handler))
    cells = execute_plan(_cfg(), _batteries(tmp_path), paths, base_dir=tmp_path,
                         client_factory=exploding_factory, resume=True)
    assert cells == []   # nothing left to do


def test_execute_plan_unreachable_target_continues(tmp_path):
    def dead_factory(base_url, api_key=None):
        def handler(request):
            raise httpx.ConnectError("refused")
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url, transport=httpx.MockTransport(handler))
    paths = RunPaths(tmp_path / "run-3")
    cells = execute_plan(_cfg(), _batteries(tmp_path), paths, base_dir=tmp_path,
                         client_factory=dead_factory)
    assert len(cells) == 1
    assert cells[0].errors == 1     # errored, but run produced the cell and did not abort
