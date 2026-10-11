"""Verified append-only native source supplements; no ownership policy changes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_COMPONENTS = (
    "trees",
    "states",
    "area-effects",
    "areas",
    "monsters",
    "casting",
    "level-zero",
    "zero-effect-definitions",
)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_inputs(bundle):
    """Match current source bytes against the original extraction provenance."""
    bundle = Path(bundle).resolve()
    provenance_path = bundle / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    inputs = {ROOT / "client/lib/wakfu-client.jar": provenance["client_jar_sha256"]}
    inputs.update(
        {
            ROOT / "client/contents/bdata" / name: value
            for name, value in provenance["binary_archives"].items()
        }
    )
    inputs.update(
        {
            bundle
            / (name + ".json.gz"): provenance["bundle_documents"][name + ".json.gz"]
            for name in BUNDLE_COMPONENTS
        }
    )
    actual = {str(path): sha256_file(path) for path in inputs}
    if any(actual[str(path)] != expected for path, expected in inputs.items()):
        raise ValueError("Supplement inputs differ from sealed native extraction")
    actual[str(provenance_path)] = sha256_file(provenance_path)
    actual[str(ROOT / "sniffer/java/ExportGrantedSpellEffectTrees.java")] = sha256_file(
        ROOT / "sniffer/java/ExportGrantedSpellEffectTrees.java"
    )
    actual[str(ROOT / "server/tools/convert_spell_effect_trees.py")] = sha256_file(
        ROOT / "server/tools/convert_spell_effect_trees.py"
    )
    return actual


def validate_supplement_domains(document):
    spells, casting = document["spells"], document["casting"]
    if set(spells) != set(casting) or not 1 <= len(spells) <= 16:
        raise ValueError("Invalid bounded supplement spell identities")
    domains = {}
    for reference, spell in spells.items():
        maximum = casting[reference]["maximum_level"]
        if type(maximum) is not int or not 1 <= maximum <= 32767:
            raise ValueError("Invalid native supplement maximum level")
        if (
            len(spell["levels"]) != maximum
            or len(casting[reference]["costs"]) != maximum
        ):
            raise ValueError("Incomplete native supplement spell or cost domain")
        if spell["levels"] != casting[reference]["levels"]:
            raise ValueError("Supplement roots or ranges differ from sealed casting")
        roots = {str(effect) for level in spell["levels"] for effect in level[2]}
        if roots - document["effects"].keys():
            raise ValueError("Missing native supplement root effect")
        domains[reference] = dict(
            spell_levels=[1, maximum],
            cost_levels=[1, maximum],
            evaluated_effect_parameter_levels_by_effect={
                effect: [1, len(row.get("parameters_by_level", []))]
                for effect, row in document["effects"].items()
            },
            effect_parameters_above_200_qualified=False,
            level_zero_qualified=False,
        )
    return domains


def verify_spell_supplement(directory, bundle):
    """Reject changed source, changed artifacts, domains and conflicting identity."""
    directory = Path(directory).resolve()
    receipt = json.loads((directory / "source-receipt.json").read_text())
    if receipt.get("schema") != "native-spell-supplement-receipt-v1":
        raise ValueError("Unknown native spell supplement receipt")
    if receipt["source_sha256"] != source_inputs(bundle):
        raise ValueError("Native spell supplement source receipt changed")
    if "supplement.json" not in receipt["output_sha256"]:
        raise ValueError("Missing native supplement artifact checksum")
    for filename, expected in receipt["output_sha256"].items():
        if (
            Path(filename).name != filename
            or sha256_file(directory / filename) != expected
        ):
            raise ValueError("Native spell supplement artifact changed")
    document = json.loads((directory / "supplement.json").read_text())
    if validate_supplement_domains(document) != receipt["domains"]:
        raise ValueError("Native spell supplement domain receipt changed")
    return document


def merge_dependency_supplement(tables, document):
    """Append typed source records, rejecting replacement of every existing row."""
    from export_monster_summon_dependencies import compact

    result = {kind: dict(rows) for kind, rows in tables.items()}
    for kind, rows in compact(document).items():
        destination = result.setdefault(kind, {})
        for reference, row in rows.items():
            if reference in destination and destination[reference] != row:
                raise ValueError(
                    "Conflicting native spell supplement identity "
                    + kind
                    + ":"
                    + reference
                )
            if reference not in destination:
                destination[reference] = deepcopy(row)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    args = parser.parse_args()
    document = verify_spell_supplement(args.supplement, args.bundle)
    print(
        json.dumps(dict(verified=True, domains=validate_supplement_domains(document)))
    )
