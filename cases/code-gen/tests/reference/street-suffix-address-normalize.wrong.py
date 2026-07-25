def expand_suffix(token: str) -> str:
    if token == "":
        return ""
    mapping = {
        "st": "Street",
        "str": "Street",
        "street": "Street",
        "rd": "Road",
        "road": "Road",
        "ave": "Avenue",
        "av": "Avenue",
        "avenue": "Avenue",
        "blvd": "Boulevard",
        "boulevard": "Boulevard",
        "ln": "Lane",
        "lane": "Lane",
    }
    return mapping.get(token, token)

def normalize_address(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    parts = line.split()
    return " ".join(expand_suffix(p) for p in parts)
