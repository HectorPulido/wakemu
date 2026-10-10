"""Prepare native teleport configurations offline without installing runtime rows."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_native_teleport_configuration import build
from prepare_native_physical_candidates import normalized_roster


def main():
    root = Path(".runtime/local")
    load = lambda p: json.loads(Path(p).read_text())
    compositions = load(
        "docs/reports/dungeons/AUTOMATIC-TELEPORT-COMPOSITION-COVERAGE.json"
    )["records"]
    inventory = load("docs/reports/dungeons/inventory.json")["records"]
    bases = load(
        root / "methodwakfu-dungeons/local-policy-configs-all87/configurations.json"
    )["configurations"]
    transports = load(
        root
        / "methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
    )
    output = root / "native-teleport-complete-candidates"
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for row in compositions:
        if row["status"] != "roster_candidate_prepared":
            continue
        result = dict(key=row["key"], name=row["name"], route=row["route"])
        try:
            native = next(r for r in inventory if r["key"] == row["key"])
            base = next(b for b in bases if b["route"]["key"] == row["route"])
            topology = load(
                root / "native-teleport-topology-candidates" / (row["route"] + ".json")
            )
            config = build(
                base,
                topology,
                normalized_roster(row["roster_candidate"], native),
                transports,
                version=base["version"] + 1,
            )
            path = output / (row["route"] + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            result.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=len(topology["rooms"]),
                boss_mechanic_status="not_proved",
                activation_readiness="requires_full_postgres_lifecycle_and_review",
            )
        except (ValueError, KeyError, StopIteration) as error:
            result.update(
                status="unsupported", reason=str(error) or type(error).__name__
            )
        records.append(result)
    report = dict(
        scope="Offline native teleport configuration preparation; no activation",
        records=records,
    )
    Path(
        "docs/reports/dungeons/AUTOMATIC-TELEPORT-COMPLETE-CANDIDATES.json"
    ).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
