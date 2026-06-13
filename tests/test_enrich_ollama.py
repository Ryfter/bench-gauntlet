import json
from pathlib import Path

from gauntlet.enrich.ollama import parse_ollama

FIX = Path(__file__).parent / "fixtures" / "ollama_tags.json"


def test_parse_ollama_extracts_metadata():
    payload = json.loads(FIX.read_text(encoding="utf-8"))
    by_id = {m.id: m for m in parse_ollama(payload)}

    g = by_id["gemma3:1b"]
    assert g.size_bytes == 815319791
    assert g.quant == "Q4_K_M"
    assert g.params == "999.89M"
    # Ollama /api/tags does not advertise context or capabilities -> None.
    assert g.max_context is None
    assert g.vision is None
