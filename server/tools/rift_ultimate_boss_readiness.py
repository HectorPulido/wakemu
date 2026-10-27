"""Classify a bounded original Ultimate boss inventory without loading catalogs.

This audit proves finite source prerequisites, never encounter execution or
that dungeon-specific mechanics work on a Rift map. It consumes the exporter
artifact and does not import the runtime factory, connect to a database or
alter activation policy.
"""
import argparse
import hashlib
import json
from pathlib import Path


def classify(inventory):
    rows = inventory["rows"]
    if len(rows) != 29 or len({row["reference"] for row in rows}) != 29:
        raise ValueError("Expected the exact 29 distinct Ultimate pool references")
    result = []
    for row in rows:
        abilities = row["original_abilities"]
        original_ids = {entry["spell_id"] for entry in abilities}
        activation = row.get("activation_policy_row")
        props = row["native_properties"]
        physical = (
            type(row["physical_radius"]) is int
            and row["physical_radius"] >= 0
            and type(row["native_los_height"]) is int
            and row["native_los_height"] >= 0
            and row["hp_curve"]["base"] > 0
            and 1 <= row["minimum_level"] <= row["maximum_level"]
        )
        triples = row["initial_state_triples"]
        activation_exact = (
            isinstance(activation, dict)
            and activation.get("min_level") == row["minimum_level"]
            and activation.get("max_level") == row["maximum_level"]
            and set(activation.get("spell_ids", ())) == original_ids
            and activation.get("initial_state_triples") == triples
            and len(triples) % 3 == 0
            and all(type(value) is int for value in triples)
        )
        tables = all(
            entry["casting_present"] and entry["effect_tree_present"] and entry["roots"]
            for entry in abilities
        )
        result.append(
            dict(
                reference=row["reference"],
                name=row["name"],
                rifts=row["rifts"],
                original_level_range=[row["minimum_level"], row["maximum_level"]],
                physical_source_valid=physical,
                physical_radius=row["physical_radius"],
                native_los_height=row["native_los_height"],
                activation_source_exact=activation_exact,
                initial_state_triples=triples,
                ability_count=len(abilities),
                original_casting_and_root_tables_present=bool(tables),
                world_properties=props["world_properties"],
                fight_properties=props["fight_properties"],
                world_property43=43 in props["world_properties"],
                fight_property43=43 in props["fight_properties"],
                spell_conditions=[
                    dict(spell_id=entry["spell_id"], criterion=entry["cast_criterion"])
                    for entry in abilities
                    if entry["cast_criterion"]
                ],
                component_status="NOT_EXECUTED",
                pending=[
                    "Full spell, initial-state and internally triggered dependency closure",
                    "Native geometry/room/world-property predicates in executable descendants",
                    "Actual owned constructor, innate events, AI and paid ability component",
                    "Source-specific summon/phase lifecycle on accepted wave clearance",
                ],
            )
        )
    return dict(
        scope="BOUNDED_SOURCE_PREREQUISITES_NOT_FULL_BOSS_QUALIFICATION",
        source_revision=inventory["revision"],
        rows=result,
        counts=dict(
            pool_references=len(result),
            physical_source_valid=sum(row["physical_source_valid"] for row in result),
            activation_source_exact=sum(
                row["activation_source_exact"] for row in result
            ),
            casting_and_root_tables_present=sum(
                row["original_casting_and_root_tables_present"] for row in result
            ),
            world_property43=sum(row["world_property43"] for row in result),
            executed_components=0,
        ),
        notes=[
            "A root table is not the complete executable effect dependency closure.",
            "World and fight properties are distinct native namespaces.",
            "No actor, map, phase, spell or policy is modified by this audit.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.inventory.read_bytes()
    result = classify(json.loads(raw))
    result["inventory_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
