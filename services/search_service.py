import json
from pathlib import Path


class SearchService:
    """Loads and filters threat intelligence records from the local JSON store."""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)

    def load_threats(self):
        with (self.data_dir / "threats.json").open(encoding="utf-8") as data_file:
            return json.load(data_file)

    def search(self, query="", severity="", status="", source=""):
        query = query.strip().lower()
        filters = {
            "severity": severity.strip().lower(),
            "status": status.strip().lower(),
            "source": source.strip().lower(),
        }

        results = []
        for threat in self.load_threats():
            searchable_text = " ".join(
                str(threat.get(field, ""))
                for field in ("title", "category", "source", "description")
            ).lower()
            if query and query not in searchable_text:
                continue
            if any(filters[field] and str(threat.get(field, "")).lower() != filters[field] for field in filters):
                continue
            results.append(threat)
        return results
