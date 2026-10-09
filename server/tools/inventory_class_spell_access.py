"""Bulk class spell and native eWn access inventory, without runtime catalogs."""
import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "server/protocol"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(source):
    nodes, grants = {}, {}
    with open(source, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            kind, reference = row["kind"], row["reference"]
            if row.get("status") == "missing" or row.get("error") is not None:
                continue
            edges = []
            if kind == "spell":
                roots = {
                    root
                    for level, values in row["root_samples"].items()
                    if 0 <= int(level) <= 245
                    for root in values
                }
                edges = [("effect", root) for root in sorted(roots)]
            elif kind in ("state", "area"):
                if "raw_roots" not in row:
                    continue
                edges = [("effect", root) for root in row["raw_roots"]]
            elif kind == "effect":
                edges = [("effect", root) for root in row["children_ordered"]]
                edges += sorted(
                    {
                        (item["kind"], item["reference"])
                        for item in row["classified_reference_samples"]
                        if 0 <= item["sample_level"] <= 245
                        and item["reference"] > 0
                        and item["kind"] != "profile"
                    }
                )
                if row["family"] == 649:
                    grants[reference] = dict(
                        effect_reference=reference,
                        native_runner=row["native_runner_class"],
                        criterion_raw=row["criterion_raw"],
                        criterion_native=row["criterion_native"],
                        raw_parameters=row["raw_parameters"],
                        samples=row["samples"],
                        granted_references=sorted(
                            {
                                item["reference"]
                                for item in row["classified_reference_samples"]
                                if 0 <= item["sample_level"] <= 245
                                and item["reference"] > 0
                            }
                        ),
                        native_metadata=row["native_metadata"],
                        minimum_level=row["minimum_level"],
                        maximum_level=row["maximum_level"],
                    )
            nodes[(kind, reference)] = edges
    spells = json.loads((DATA / "spells.json").read_text())["spells"]
    innates = json.loads((DATA / "breed-innate-definitions.json").read_text())
    breeds = defaultdict(list)
    for spell in spells:
        breeds[spell["breed"]].append(("spell", spell["id"]))
    innate_rows = innates.get("breeds", innates.get("definitions", []))
    if isinstance(innate_rows, dict):
        innate_rows = list(innate_rows.values())
    for row in innate_rows:
        breed = row.get("breed", row.get("id"))
        for state in row["innate_states"]:
            breeds[breed].append(("state", state.get("reference", state.get("id"))))
    links, missing = defaultdict(list), set()
    for breed, roots in sorted(breeds.items()):
        queue = deque((node, (node,)) for node in roots)
        seen = set()
        while queue:
            node, path = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            if node not in nodes:
                missing.add(node)
                continue
            if node[0] == "effect" and node[1] in grants:
                links[node[1]].append(
                    dict(breed=breed, path=[list(value) for value in path])
                )
            queue.extend(
                (child, (*path, child)) for child in nodes[node] if child not in seen
            )
    selected = {
        reference: dict(grants[reference], class_paths=links[reference])
        for reference in sorted(links)
    }
    grant_spells = sorted(
        {
            reference
            for row in selected.values()
            for reference in row["granted_references"]
        }
    )
    closure, queue = set(), deque(("spell", reference) for reference in grant_spells)
    while queue:
        node = queue.popleft()
        if node in closure:
            continue
        closure.add(node)
        queue.extend(nodes.get(node, ()))
    return dict(
        schema="native-class-spell-access-v1",
        source_sha256=sha(source),
        inputs={
            name: sha(DATA / name)
            for name in ("spells.json", "breed-innate-definitions.json")
        },
        class_spells=spells,
        grants=selected,
        granted_spell_references=grant_spells,
        effect_reference_closure=sorted(
            reference for kind, reference in closure if kind == "effect"
        ),
        missing_nodes=[list(node) for node in sorted(missing)],
        counts=dict(
            breeds=len(breeds),
            class_spells=len(spells),
            class_grant_effects=len(selected),
            granted_references=len(grant_spells),
        ),
        limitations=[
            "Structural reachability does not execute source criteria or events.",
            "Profile and captured/copied book edges are outside this access inventory.",
            "Raw ordinary spell UIDs and raw granted UIDs retain separate ownership.",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--closure-output", type=Path)
    args = parser.parse_args()
    result = inventory(args.source)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if args.closure_output is not None:
        closure = dict(
            schema="native-class-spell-grant-closure-v1",
            source_sha256=result["source_sha256"],
            inventory_sha256=sha(args.output),
            effect_reference_closure=result["effect_reference_closure"],
            granted_spell_references=result["granted_spell_references"],
            class_grant_effects=sorted(map(int, result["grants"])),
        )
        args.closure_output.write_text(
            json.dumps(closure, sort_keys=True, indent=2) + "\n"
        )
    print(json.dumps(result["counts"], sort_keys=True))
