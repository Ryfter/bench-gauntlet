from gauntlet.models import CaseResult
from gauntlet.scorecard import aggregate_cell


def _r(score, passed, method="exact"):
    return CaseResult(case_id="x", method=method, score=score, passed=passed)


def test_aggregate_quality_and_pass_rate():
    results = [_r(1.0, True), _r(0.0, False), _r(0.5, True)]
    cell = aggregate_cell(
        model="gemma3:1b", target="wraith2-ollama", box="RTX 2070 Super laptop",
        context=8192, capability="extract-json", results=results,
        latency_p50_s=2.0, tokens_per_s=40.0,
    )
    assert cell.cases == 3
    assert cell.pass_rate == 2 / 3
    assert abs(cell.quality - 0.5) < 1e-9   # mean of scored: (1+0+0.5)/3
    assert cell.errors == 0


def test_aggregate_excludes_unscored_from_quality_but_counts_case():
    results = [_r(1.0, True), _r(None, False, method="judge")]
    cell = aggregate_cell(
        model="m", target="t", box="b", context=8192, capability="c", results=results,
    )
    assert cell.cases == 2
    assert cell.quality == 1.0          # only the scored case counts toward quality
    assert cell.pass_rate == 0.5        # passed / total cases


def test_aggregate_all_unscored_yields_none_quality():
    results = [_r(None, False, method="judge")]
    cell = aggregate_cell(model="m", target="t", box="b", context=1, capability="c",
                          results=results)
    assert cell.quality is None
