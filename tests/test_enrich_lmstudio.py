import json
from pathlib import Path

from gauntlet.enrich import ModelMeta
from gauntlet.enrich.lmstudio import parse_lmstudio

FIX = Path(__file__).parent / "fixtures" / "lmstudio_models.json"


def test_parse_lmstudio_extracts_metadata():
    payload = json.loads(FIX.read_text(encoding="utf-8"))
    metas = parse_lmstudio(payload)
    by_id = {m.id: m for m in metas}

    assert isinstance(by_id["google/gemma-4-31b"], ModelMeta)
    g4 = by_id["google/gemma-4-31b"]
    assert g4.max_context == 32768
    assert g4.quant == "Q4_K_M"
    assert g4.size_bytes == 18500000000
    assert g4.params == "31B"
    assert g4.vision is False
    assert g4.tool_use is True
    assert g4.loaded is False

    g3 = by_id["gemma-3-12b-it-heretic"]
    assert g3.vision is True
    assert g3.max_context == 131072
