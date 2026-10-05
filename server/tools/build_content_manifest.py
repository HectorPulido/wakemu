"""Record reproducible catalog fingerprints without upgrading evidence claims.

Run from any directory. Source declarations are copied verbatim from each
catalog, not inferred from a filename or treated as independent verification.
"""
import hashlib
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGS = {
    "monsters.json": "monsters",
    "monster-encyclopedia.json.gz": "monsters",
    "spells.json": "spells",
    "native-transports.json": None,
    "native-transport-objects.json": None,
    "native-map-objects.json": None,
    "native-generic-teleporters.json": None,
    "interactive-actions.json": None,
    "item-equipment-rules.json": "items",
    "item-equipment-effects.json": "items",
    "rii-test-arena.json": None,
    "combat-maps/index.json": None,
    "forced-transitions/index.json": None,
    "combat-los/index.json": None,
    "item-stack-rules.json": "items",
    "item-action-rules.json": "items",
    "inventory-bag-rules.json": None,
    "item-healing-rules.json": "items",
    "world-maps.json": "routes",
    "spell-costs.json": None,
    "level-xp.json": None,
    "seed-actions.json": None,
    "plant-resources.json": None,
    "ecology-regions.json": None,
    "planting-maps/index.json": None,
    "planting-grounds.json": None,
    "profession-actions.json": None,
}


def manifest():
    entries = []
    for filename, collection in sorted(CATALOGS.items()):
        raw = (ROOT / "protocol" / filename).read_bytes()
        data = json.loads(gzip.decompress(raw) if filename.endswith(".gz") else raw)
        entry = dict(
            path="protocol/" + filename,
            sha256=hashlib.sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        if isinstance(data, dict):
            entry["declared_provenance"] = {
                key: data[key]
                for key in ("source", "jar_sha256", "bdata_sha256", "limits")
                if key in data
            }
        if isinstance(data, list):
            entry["records"] = len(data)
        elif collection is not None:
            entry["records"] = len(data[collection])
        entries.append(entry)
    return dict(schema_version=1, catalogs=entries)


if __name__ == "__main__":
    destination = ROOT / "protocol" / "content-manifest.json"
    destination.write_text(json.dumps(manifest(), ensure_ascii=False, indent=2) + "\n")
    print("Wrote", destination.relative_to(ROOT))
