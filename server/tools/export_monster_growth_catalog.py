"""Build level-ranked candidates from installed, exported monster metadata.

Ranks implement the requested local ordering, not an inferred official age
graph. csc contains native world properties, verified through bbo/blj/eGC.
"""
import argparse
import hashlib
import json
from pathlib import Path


def export(monsters_path, resources_path):
    monsters = json.loads(monsters_path.read_text())["monsters"]
    resources = json.loads(resources_path.read_text())
    families = {}
    for resource in resources:
        if resource["monster_resource"]:
            for family in resource["monster_family_ids"]:
                families.setdefault(family, []).append(resource["resource_reference"])
    result = []
    for family, resource_refs in sorted(families.items()):
        members = [row for row in monsters if row["family_id"] == family]
        tiers = []
        for rank, minimum in enumerate(sorted({row["min_level"] for row in members})):
            candidates = sorted(
                (row for row in members if row["min_level"] == minimum),
                key=lambda row: (row["max_level"], row["ref"]),
            )
            tiers.append(
                dict(
                    rank=rank,
                    min_level=minimum,
                    candidates=[
                        dict(
                            reference=row["ref"],
                            min_level=row["min_level"],
                            max_level=row["max_level"],
                            world_properties=row["raw_visual_arrays"]["csc"],
                            boss_classification=(
                                "ultimate_boss"
                                if 49 in row["raw_visual_arrays"]["csc"]
                                else "raid_boss"
                                if 99 in row["raw_visual_arrays"]["csc"]
                                else "boss"
                                if 43 in row["raw_visual_arrays"]["csc"]
                                else "arch"
                                if 45 in row["raw_visual_arrays"]["csc"]
                                else "regular"
                            ),
                        )
                        for row in candidates
                    ],
                )
            )
        result.append(
            dict(
                family_id=family,
                resource_references=sorted(set(resource_refs)),
                tiers=tiers,
                terminal=len(tiers) <= 1,
                missing_catalog=not members,
            )
        )
    return dict(
        schema_version=1,
        ordering="Local policy: distinct native minimum levels; equal levels are alternatives",
        boss_classification="Native csc world properties: BOSS43, ARCH45, ULTIMATE_BOSS49, RAID_BOSS99; no name heuristics",
        source_sha256=dict(
            monsters=hashlib.sha256(monsters_path.read_bytes()).hexdigest(),
            resources=hashlib.sha256(resources_path.read_bytes()).hexdigest(),
        ),
        families=result,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monsters", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(export(args.monsters, args.resources), indent=2, sort_keys=True)
        + "\n"
    )
