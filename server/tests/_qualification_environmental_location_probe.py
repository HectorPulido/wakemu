"""Read-only observation of exact original location joins."""
import json
from pathlib import Path
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT

p = Path(".runtime/parallel-readiness-20261021/environmental-location-probe.json")
documents = {}
for name in (
    "territory-protector-bonuses.json",
    "monster-encyclopedia.json",
    "territory-map-cells.json",
):
    data = native_catalog.load(DATA_ROOT / name)
    section = (
        data["territories"] if name != "territory-map-cells.json" else data["maps"]
    )
    documents[name] = dict(
        keys=list(data),
        count=len(section),
        sample=list(section.items())[:2] if isinstance(section, dict) else section[:2],
    )
p.write_text(json.dumps(documents, indent=2))
