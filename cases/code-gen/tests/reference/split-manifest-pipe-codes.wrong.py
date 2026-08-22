def split_manifest_codes(raw: str) -> list[str]:
    # strips segments but keeps empty fields from doubled/edge pipes
    return [p.strip() for p in raw.split("|")]
