def split_manifest_codes(raw: str) -> list[str]:
    return [p.strip() for p in raw.split("|") if p.strip()]
