"""Deterministic class-only native state domain, including typed owned dependencies."""
import gzip
import argparse, gzip, hashlib, json
from pathlib import Path


def build(root):
    report = root / "docs/reports/combat-inventory"
    graph = report / "class-native-mechanic-graph-20261007.json"
    data = json.load(open(graph, "rt"))
    states = {
        int(key.split(":")[1]) for key in data["nodes"] if key.startswith("state:")
    }
    areas = {int(key.split(":")[1]) for key in data["nodes"] if key.startswith("area:")}
    sources = {
        str(graph.relative_to(root)): hashlib.sha256(graph.read_bytes()).hexdigest()
    }
    for name in (
        "class-captured-native-typed-closure-20261008.jsonl.gz",
        "class-triggered426-native-typed-closure-20261008.jsonl.gz",
        "class-morph933-native-typed-closure-20261008.jsonl.gz",
    ):
        path = report / name
        sources[str(path.relative_to(root))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        with gzip.open(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                if row["kind"] == "state":
                    states.add(row["reference"])
                elif row["kind"] == "area":
                    areas.add(row["reference"])
    # Follow only actual class-reachable area roots, including their existing
    # native ordered group descendants. Do not seed all installed areas.
    area_path = root / "server/protocol/native-effect-areas.json"
    tree_path = root / "server/protocol/native-area-effect-trees.json"
    definitions = json.loads(area_path.read_text())["areas"]
    effects = json.load(open(tree_path, "rt"))["effects"]
    for path in (area_path, tree_path):
        sources[str(path.relative_to(root))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    edges = []
    for area in sorted(areas):
        row = definitions.get(str(area))
        if row is None:
            continue  # No native area roots are fabricated for absent source.
        queue = list(row["effect_ids"])
        seen = set()
        while queue:
            reference = queue.pop()
            if reference in seen:
                continue
            seen.add(reference)
            effect = effects.get(str(reference))
            if effect is None:
                continue
            queue.extend(effect.get("children") or [])
            if effect["effect_class"] != 304:
                continue
            samples = effect.get("parameters_by_level")
            if not isinstance(samples, list):
                raise ValueError("Missing native area304 state-reference samples")
            references = {sample[0] for sample in samples if sample}
            if any(type(value) is not int or value <= 0 for value in references):
                raise ValueError("Invalid native area304 state reference")
            states.update(references)
            edges.extend(
                dict(
                    area_reference=area,
                    effect_reference=reference,
                    state_reference=value,
                )
                for value in sorted(references)
            )
    # The production area catalog also supplies seven observed non-sentinel
    # eWu chance roots absent from the older typed class graph. Keep these
    # explicit callback dependencies rather than seeding general NPC spells.
    chance_edges = []
    for reference, effect in effects.items():
        if effect["effect_class"] != 304 or len(effect.get("parameters", [])) < 6:
            continue
        samples = effect.get("parameters_by_level")
        if not isinstance(samples, list):
            raise ValueError("Missing original area state chance samples")
        if not any(len(sample) >= 3 and sample[2] != -1 for sample in samples):
            continue
        references = {sample[0] for sample in samples if sample}
        if any(type(value) is not int or value <= 0 for value in references):
            raise ValueError("Invalid native area chance state reference")
        states.update(references)
        chance_edges.extend(
            dict(
                effect_reference=int(reference),
                state_reference=value,
                source="published native-area-effect-trees eWu non-sentinel chance",
            )
            for value in sorted(references)
        )
    return dict(
        schema="native-class-state-resistance-seeds-v1",
        state_ids=sorted(states),
        scope="18 class native graph and explicit captured/triggered426/morph933 dependencies",
        source_hashes=sources,
        area_state_reference_edges=edges,
        observed_area_chance_state_edges=chance_edges,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    args.output.write_text(json.dumps(build(root), indent=2) + "\n")
