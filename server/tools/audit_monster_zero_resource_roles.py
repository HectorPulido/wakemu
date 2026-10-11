"""Classify sparse native descriptors from explicit summon edges, offline only.

A sparse descriptor is not proof of an object, beta, or unusable monster.
This report never changes activation/resource values or excludes inventory rows.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def load(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as source:
        return json.load(source)


def classify(monsters, effect_documents, property_rows):
    incoming = {}
    for source, document in effect_documents:
        effects = document.get("effects", {})
        hits = {}
        for identity, effect in effects.items():
            parameters = effect.get("parameters", [])
            if effect.get("effect_class") == 307 and parameters:
                reference = parameters[0]
                if reference == int(reference) and reference > 0:
                    hits[int(identity)] = int(reference)
        for spell_id, spell in document.get("spells", {}).items():
            todo = [root for level in spell.get("levels", []) for root in level[2]]
            seen = set()
            while todo:
                identity = int(todo.pop())
                if identity in seen:
                    continue
                seen.add(identity)
                if identity in hits:
                    edge = dict(
                        source=source,
                        spell_id=int(spell_id),
                        effect_id=identity,
                        family=307,
                        parameters=effects[str(identity)]["parameters"],
                    )
                    bucket = incoming.setdefault(hits[identity], [])
                    if edge not in bucket:
                        bucket.append(edge)
                todo.extend(effects.get(str(identity), {}).get("children", []))
    symbols = {row["id"]: row["symbol"] for row in property_rows}
    rows = []
    for monster in monsters:
        raw = monster["raw_native"]
        sparse = raw["ckP"] == 1 and raw["ckQ"] == 0
        edges = incoming.get(monster["ref"], [])
        role = (
            (
                "summon_referenced_sparse_descriptor"
                if edges
                else "sparse_descriptor_role_unproven"
            )
            if sparse
            else "nonzero_descriptor_resources"
        )
        rows.append(
            dict(
                reference=monster["ref"],
                classification=role,
                native_hp_base=raw["ckP"],
                native_ap_base=raw["ckQ"],
                native_mp_base=raw["ckR"],
                fight_properties=[
                    dict(id=i, symbol=symbols.get(i))
                    for i in monster["fight_properties"]
                ],
                incoming_summon_edges=edges,
                excluded=False,
                resources_changed=False,
                creator_resource_derivation="requires_actual_parent_effect_execution",
            )
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monsters", type=Path, required=True)
    parser.add_argument("--effects", type=Path, action="append", required=True)
    parser.add_argument("--properties", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.monsters, *args.effects, args.properties]
    rows = classify(
        load(args.monsters)["monsters"],
        [(str(path), load(path)) for path in args.effects],
        load(args.properties)["properties"],
    )
    receipt = dict(
        schema="native-monster-zero-resource-roles-v1",
        offline=True,
        source_sha256={
            str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
        },
        rows=rows,
    )
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    counts = {}
    for row in rows:
        key = row["classification"]
        counts[key] = counts.get(key, 0) + 1
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
