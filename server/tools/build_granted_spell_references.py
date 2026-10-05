"""Offline reference closure for native649 grants (no class/spell whitelist).

Run before ExportGrantedSpellEffectTrees and repeat with --extra exported JSON
until no new references. Native reference slopes are checked as zero;
unknown grant references at runtime remain explicitly rejected by effect lookup.
"""
import argparse, gzip, json
from pathlib import Path
from wakfu_server.combat_parameters import parameter_value
from wakfu_server.paths import DATA_ROOT


def references(extra=None):
    tables = [json.loads((DATA_ROOT / "spell-effect-trees.json").read_text())]
    with gzip.open(DATA_ROOT / "combat-state-definitions.json.gz", "rt") as stream:
        tables.append(json.load(stream))
    if extra:
        tables.append(json.loads(Path(extra).read_text()))
    with gzip.open(DATA_ROOT / "native-spell-casting.json.gz", "rt") as stream:
        installed = set(json.load(stream)["spells"])
    result = set()
    for table in tables:
        for effect in table["effects"].values():
            if effect["effect_class"] != 649:
                continue
            if effect["parameters"][5] != 0:
                raise ValueError(
                    "Scaled native grant reference needs exhaustive level export"
                )
            ref = parameter_value(effect["parameters"], 2, 0)
            if str(ref) in installed:
                result.add(ref)
    return sorted(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--extra")
    args = parser.parse_args()
    refs = references(args.extra)
    Path(args.output).write_text("\n".join(map(str, refs)))
    print(f"{len(refs)} installed native grant references")
