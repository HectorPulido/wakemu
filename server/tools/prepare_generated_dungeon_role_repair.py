"""Prepare immutable boss-aware replacements for generated roster fields.

This offline command does not install configurations, alter existing runs, or
change native topology. Known guide slots and complete rooms are preserved.
"""
import argparse
import copy
import json
from pathlib import Path

from wakfu_server.dungeon_local_roster_policy import draft
from wakfu_server.dungeon_runtime_config import canonical_hash, prepare_configuration


def prepare(configuration, native_monsters, *, version=None):
    if version is not None and (
        type(version) is not int or version <= configuration["version"]
    ):
        raise ValueError("Repair version must advance the frozen configuration")
    original = configuration["compiled_plan"]
    generated = original.get("generated_fields", [])
    rooms = original["rooms"]
    if (
        original.get("policy_mode") != "generated_native_species_policy"
        or original.get("official") is not False
        or len(generated) != len(rooms)
        or {row["order"] for row in generated} != {room["order"] for room in rooms}
    ):
        raise ValueError("Repair requires explicit generated local room provenance")
    quantities = {
        room["order"]: sum(monster["count"] for monster in room["monsters"])
        for room in rooms
    }
    references = sorted(
        {monster["ref_id"] for room in rooms for monster in room["monsters"]}
    )
    source = copy.deepcopy(original)
    source["document_sha256"] = original["original_guide_document_sha256"]
    source["rooms"] = []
    for room in rooms:
        provenance = next(row for row in generated if row["order"] == room["order"])
        fields = {row["monster_index"]: row for row in provenance.get("fields", [])}
        if any(
            type(index) is not int or not 0 <= index < len(room["monsters"])
            for index in fields
        ):
            raise ValueError("Generated monster provenance index is invalid")
        restored = []
        for index, monster in enumerate(room["monsters"]):
            if index not in fields:
                restored.append(copy.deepcopy(monster))
            elif fields[index].get("original_monster") is not None:
                restored.append(copy.deepcopy(fields[index]["original_monster"]))
        source["rooms"].append(
            dict(
                order=room["order"],
                monsters=restored,
                diagnostics=["incomplete_guide_composition"]
                if provenance["policy_applied"]
                else [],
            )
        )
    definition = dict(id=original["definition_id"], type="DUNGEON", raw_cno=references)
    if original.get("identity_policy") == "local_legacy_map_registry":
        if (
            original.get("species_pool_provenance")
            != "guide_verified_native_references"
        ):
            raise ValueError("Legacy roster lacks reviewed species provenance")
        definition = dict(
            id=original["definition_id"],
            type="DUNGEON",
            policy_mode="local_legacy_map_registry",
            native_definition_id=None,
            local_species_pool=references,
            species_pool_provenance="guide_verified_native_references",
        )
    prepared = draft(
        source,
        definition,
        native_monsters,
        capacity=max(quantities.values()),
        generation_target=max(quantities.values()),
        generation_targets=quantities,
    )
    for original_room, repaired_room in zip(rooms, prepared["rooms"]):
        if sum(monster["count"] for monster in repaired_room["monsters"]) != sum(
            monster["count"] for monster in original_room["monsters"]
        ):
            raise ValueError("Repair would alter existing room quantities")
    plan = copy.deepcopy(original)
    plan["document_sha256"] = canonical_hash(prepared)
    plan["rooms"] = [
        dict(order=room["order"], monsters=room["monsters"], diagnostics=[])
        for room in prepared["rooms"]
    ]
    plan["generated_fields"] = [
        dict(
            order=room["order"],
            policy_applied=room["policy_applied"],
            fields=room["generated_fields"],
        )
        for room in prepared["rooms"]
    ]
    candidate = prepare_configuration(
        plan,
        configuration["topology"],
        configuration["route"],
        version=configuration["version"] + 1 if version is None else version,
        provenance=configuration["provenance"],
    )
    if candidate["topology"] != configuration["topology"]:
        raise ValueError("Role repair changed native topology")
    return candidate, dict(
        original_sha256=canonical_hash(configuration),
        candidate_sha256=canonical_hash(candidate),
        topology_unchanged=True,
        installed=False,
        existing_runs_changed=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--native-monsters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate, receipt = prepare(
        json.loads(args.configuration.read_text()),
        json.loads(args.native_monsters.read_text())["monsters"],
    )
    with args.output.open("x") as destination:
        json.dump(candidate, destination, indent=2)
        destination.write("\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
