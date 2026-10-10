"""Prepare open one-encounter arenas preserving all reviewed species and counts."""
import json
from pathlib import Path
from prepare_open_boss_dungeons import prepare


def reviewed_roster(native):
    guides = [g for g in native.get("guides", []) if g.get("rooms")]
    if len(guides) != 1 or len(guides[0]["rooms"]) != 1:
        raise ValueError(
            "Requires exactly one reviewed guide encounter; no inferred encounter collapse"
        )
    guide = guides[0]
    if not guide.get("extraction", {}).get("reviewed"):
        raise ValueError("Guide encounter not reviewed")
    pool = {m["ref_id"]: m for m in native["native_species_pool"]}
    result = []
    for m in guide["rooms"][0]["monsters"]:
        if m.get("ref_id") not in pool or m.get("role") not in ("boss", "monster"):
            raise ValueError(
                "Every initial monster needs resolved native identity and reviewed role"
            )
        count = m.get("count")
        if count is None and m["role"] == "boss":
            count = 1  # Explicit local singleton-boss policy, never infer add counts.
        if type(count) is not int or count <= 0:
            raise ValueError("Non-boss initial quantity is unknown")
        n = pool[m["ref_id"]]
        result.append(
            dict(
                name=m["name"],
                ref_id=m["ref_id"],
                role=m["role"],
                count=count,
                native_min_level=n["min_level"],
                native_max_level=n["max_level"],
                guide_min_level=m.get("min_level"),
                guide_max_level=m.get("max_level"),
            )
        )
    if sum(m["role"] == "boss" for m in result) != 1:
        raise ValueError("Requires exactly one reviewed boss identity")
    return result


def main():
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_encounters import enemy_formation

    root = Path(".runtime/local")
    inventory = json.loads(Path("docs/reports/dungeons/inventory.json").read_text())[
        "records"
    ]
    flows = json.loads((root / "all-native-dungeon-flows.json").read_text())["records"]
    bases = json.loads(
        (
            root / "methodwakfu-dungeons/local-policy-configs-all87/configurations.json"
        ).read_text()
    )["configurations"]
    transports = json.loads(
        (
            root
            / "methodwakfu-dungeons/inventory-native-snapshot/native-generic-teleporters.json"
        ).read_text()
    )
    output = root / "reviewed-open-arena-configurations"
    output.mkdir(exist_ok=True)
    records = []
    for flow in flows:
        native = next(n for n in inventory if n["key"] == flow["key"])
        if (
            flow["status"] != "open_geometry_no_separator"
            or native["native"]["type"] == "ULTIMATE_BOSS"
        ):
            continue
        row = dict(key=flow["key"], route=flow["route"]["key"], name=flow["name"])
        try:
            roster = reviewed_roster(native)
            base = next((b for b in bases if b["route"]["key"] == row["route"]), None)
            if base is None:
                raise ValueError("Missing compiled route configuration")
            mid = flow["route"]["start_map_id"]
            geometry = json.loads(
                (
                    root / f"all-native-dungeon-exploration/exploration-{mid}.json"
                ).read_text()
            )
            published = published_geometry(mid)
            combat = dict(
                map_id=mid, cells=list(published.cells), edges=list(published.edges)
            )
            config, placement, sequence = prepare(
                native,
                flow,
                base,
                geometry,
                transports,
                combat,
                enemy_formation,
                reviewed_roster=roster,
            )
            path = output / (row["route"] + ".json")
            path.write_text(json.dumps(config, indent=2) + "\n")
            row.update(
                status="offline_configuration_prepared",
                path=str(path),
                rooms=1,
                placement_validation=placement,
                sequence_validation=sequence,
                reviewed_roster=roster,
                boss_mechanic_status="not_proved",
            )
        except (ValueError, KeyError, FileNotFoundError) as error:
            row.update(status="blocked", reason=str(error))
        records.append(row)
    Path("docs/reports/dungeons/REVIEWED-OPEN-ARENA-CANDIDATES.json").write_text(
        json.dumps(dict(records=records), indent=2) + "\n"
    )
    print(
        json.dumps(
            [(r["name"], r["status"], r.get("reason")) for r in records],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
