# Battery authoring pipeline

How the 108-case `code-gen` battery was built, and how to extend it.

Cases are drafted by a cheap fleet model (Grok via `/baton:fleet`) and then
**machine-validated before they can land**. That is what makes delegating the
drafting safe: a case only enters the battery if the harness can prove it
discriminates, so quality never rests on trusting the drafting model.

## Flow

```
run_batch.ps1      draft N cases for one dimension  ->  batch-*.json
ingest_cases.py    validate, then write case files  ->  cases/code-gen/
gen_yaml.py        regenerate the battery from the registry
discrimination.py  prove the axis still spreads
```

## 1. Draft a batch

```powershell
./scripts/battery-authoring/run_batch.ps1 `
    -Dimension "adversarial-correctness" `
    -Tiers "T1,T2,T3,T4" `
    -Brief  "What this batch should probe." `
    -Out    "batch-new.json"
```

`grok_contract.md` is the authoring contract prepended to every request: output
shape, the mandatory `check(ns)` idiom, tier definitions, and the
anti-contamination rules. Edit it there, not per-batch. `drive_wave1.ps1` and
`drive_wave2.ps1` show fanning several dimensions out at once (cap concurrency
around 3 — the provider slows sharply beyond that).

## 2. Validate and ingest

```bash
.venv/Scripts/python scripts/battery-authoring/ingest_cases.py batch-new.json           # dry run
.venv/Scripts/python scripts/battery-authoring/ingest_cases.py batch-new.json --apply
```

A case is rejected unless **all** of these hold:

- the reference solution scores exactly `1.0` — the asserts are satisfiable
- the deliberately-wrong solution scores `< 1.0` — the asserts have teeth
- no hidden-test line leaks into the prompt (`test-authoring` exempt)
- the id and prompt name no memorised classic
- `check(ns)` is defined, the tier is valid, no field is empty

Five of 113 drafted cases were rejected in the original build: three whose
reference could not satisfy its own asserts, one whose wrong solution still
scored 1.0. Both directions matter — an unsatisfiable case scores every model
0.0 and a toothless one scores every model 1.0. Both look like data.

## 3. Regenerate and verify

```bash
.venv/Scripts/python scripts/battery-authoring/gen_yaml.py        # rebuild batteries/code-gen.yaml
.venv/Scripts/python -m pytest tests/test_case_validation.py      # every case re-proves itself
.venv/Scripts/python scripts/battery-authoring/discrimination.py  # score spread across quality levels
```

`gen_yaml.py` rebuilds the battery from `cases/code-gen/registry.json`, so the
registry is the source of truth — edit that, not the YAML.

Watch the tier mix as you add. The target is roughly T1 15% / T2 35% / T3 35% /
T4 15%: the fleet is 1B–30B local models, and a battery that saturates at either
end discriminates nothing. See `batteries/README.md` for the ladder and the
twelve dimensions.

## Canaries

Every hidden-test file carries a deterministic `GAUNTLET-CANARY-<hex>` marker.
New cases need one — regenerate with:

```python
from gauntlet.scoring.execute import canary_for, CANARY_RE
```

prepending `# {canary_for(case_id)}` to any tests file lacking one. See
`docs/2026-07-25-benchmark-integrity-threat-model.md`.

## Red team

`tests/redteam/` holds the cheat corpus and both attack runners. Re-run them
after any change to the sandbox guard:

```bash
.venv/Scripts/python tests/redteam/run_redteam.py tests/redteam/cheat-corpus.json
.venv/Scripts/python tests/redteam/run_targeted.py
```
