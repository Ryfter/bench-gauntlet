import csv
import io
import datetime

def rank_ready_parcels(csv_text: str, as_of: str) -> list[str]:
    as_of_dt = datetime.datetime.strptime(as_of, "%Y-%m-%dT%H:%M:%S")
    reader = csv.DictReader(io.StringIO(csv_text))
    items = []
    if reader.fieldnames is None:
        return []
    for row in reader:
        try:
            tracking = (row.get("tracking") or "").strip()
            if not tracking:
                continue
            zone = int(str(row["zone"]).strip())
            ready = datetime.datetime.strptime(
                str(row["ready_at"]).strip(), "%Y-%m-%dT%H:%M:%S"
            )
            weight = float(str(row["weight"]).strip())
            if weight <= 0:
                continue
            if ready >= as_of_dt:
                continue
            items.append((zone, weight, tracking))
        except (KeyError, TypeError, ValueError):
            continue
    items.sort()
    return [tracking for _, __, tracking in items]
