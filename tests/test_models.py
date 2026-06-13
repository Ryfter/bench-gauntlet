from gauntlet.models import BaselineGap, CaseResult, Cell, ContextDepth, Scorecard


def test_cell_has_no_base_url_field():
    # Privacy invariant: the contract simply has no field for an endpoint/IP.
    assert "base_url" not in Cell.model_fields
    assert "target" in Cell.model_fields  # hostname label, private-mode only
    assert "box" in Cell.model_fields     # hardware label


def test_case_result_unscored_is_representable():
    r = CaseResult(case_id="x", method="judge", score=None, passed=False, detail="unscored")
    assert r.score is None


def test_scorecard_round_trips():
    sc = Scorecard(
        run={"id": "r1", "date": "2026-06-12", "gauntlet_version": "0.1.0"},
        cells=[
            Cell(model="gemma3:1b", target="wraith2-ollama", box="RTX 2070 Super laptop",
                 context=8192, capability="extract-json", quality=0.91, pass_rate=0.86,
                 latency_p50_s=2.1, tokens_per_s=38.0, judge=None, cases=14, errors=0),
        ],
        context_depth=[ContextDepth(model="gemma3:1b", advertised=131072, effective_90pct=49152)],
        baseline_gaps=[BaselineGap(capability="commit-msg", local_champion="tavernari",
                                   frontier="claude", gap=0.03)],
    )
    again = Scorecard.model_validate(sc.model_dump())
    assert again.cells[0].box == "RTX 2070 Super laptop"
