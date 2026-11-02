"""Stage source-bound locale roster corrections without changing live state.

Only explicitly generated rosters can be reconstructed from their retained
original guide fields. Reviewed explicit configurations remain unchanged.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import zipfile

from wakfu_server.dungeon_local_roster_policy import draft
from wakfu_server.dungeon_runtime_config import canonical_hash, prepare_configuration


def native_locale_monsters(monsters, archive):
    """Read original content.7 IDs; never alter or execute client artifacts."""
    archive = Path(archive)
    with zipfile.ZipFile(archive) as source:
        raw = source.read("texts_fr.properties")
    names = {}
    for line in raw.decode("utf8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.startswith("content.7."):
            reference = int(key.removeprefix("content.7."))
            if reference in names:
                raise ValueError("Duplicate native French monster reference")
            names[reference] = value
    return [dict(monster, name_fr=names.get(monster["ref"])) for monster in monsters], {
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "text_sha256": hashlib.sha256(raw).hexdigest(),
        "key_namespace": "content.7.<native reference>",
        "client_modified": False,
    }


def generated_source(configuration):
    plan = configuration["compiled_plan"]
    mode = plan.get("policy_mode")
    return mode == "generated_native_species_policy" or (
        mode
        in ("explicit_dev_native_physical_rooms", "explicit_dev_native_teleport_rooms")
        and plan.get("roster_policy_evidence", {}).get("policy_mode")
        == "generated_native_species_policy"
        and plan.get("local_policy", "").startswith(
            "Preserve complete rooms and known quantities; fill unresolved slots"
        )
    )


def restore_guide_plan(configuration):
    original = configuration["compiled_plan"]
    if (
        not generated_source(configuration)
        or original.get("official") is not False
        or original.get("reviewed_official") is not False
    ):
        raise ValueError("Only explicit nonofficial generated rosters can be repaired")
    provenance = original.get("generated_fields", [])
    if (
        len(provenance) != len(original["rooms"])
        or {row["order"] for row in provenance}
        != {room["order"] for room in original["rooms"]}
        or not original.get("original_guide_document_sha256")
    ):
        raise ValueError(
            "Original guide identity or ordered field provenance is absent"
        )
    source = copy.deepcopy(original)
    source["document_sha256"] = original["original_guide_document_sha256"]
    source["rooms"] = []
    for room in original["rooms"]:
        saved = next(row for row in provenance if row["order"] == room["order"])
        fields = {row["monster_index"]: row for row in saved.get("fields", [])}
        if len(fields) != len(saved.get("fields", [])) or any(
            type(index) is not int or not 0 <= index < len(room["monsters"])
            for index in fields
        ):
            raise ValueError("Original guide field indices are inconsistent")
        restored = []
        for index, monster in enumerate(room["monsters"]):
            if index not in fields:
                restored.append(copy.deepcopy(monster))
            elif fields[index].get("original_monster") is not None:
                restored.append(copy.deepcopy(fields[index]["original_monster"]))
            elif fields[index].get("fields") != ["local_slot"]:
                raise ValueError("Missing original guide row for generated identity")
        source["rooms"].append(
            dict(
                order=room["order"],
                monsters=restored,
                diagnostics=["native_locale_identity_binding"]
                if saved["policy_applied"]
                else [],
            )
        )
    return source


def select_guide_carrier(configuration, versions):
    """Use original immutable generated rows, never stale indices after flattening."""
    plan = configuration["compiled_plan"]
    orders = [room["order"] for room in plan["rooms"]]
    digest = plan.get("original_guide_document_sha256")
    candidates = [
        old
        for old in versions
        if old["compiled_plan"].get("policy_mode") == "generated_native_species_policy"
        and old["route"]["key"] == configuration["route"]["key"]
        and old["compiled_plan"].get("original_guide_document_sha256") == digest
        and old["compiled_plan"]["definition_id"] == plan["definition_id"]
        and [room["order"] for room in old["compiled_plan"]["rooms"]] == orders
    ]
    for old in sorted(candidates, key=lambda value: value["version"]):
        try:
            restore_guide_plan(old)
        except ValueError:
            continue
        return old
    raise ValueError(
        "No immutable original guide carrier matches the current room topology"
    )


def prepare(
    configuration,
    native_monsters,
    admission_policy,
    definition,
    *,
    version,
    guide_carrier=None
):
    if type(version) is not int or version <= configuration["version"]:
        raise ValueError("Corrected configuration requires a newer immutable version")
    guide_carrier = configuration if guide_carrier is None else guide_carrier
    source = restore_guide_plan(guide_carrier)
    if (
        guide_carrier["route"]["key"] != configuration["route"]["key"]
        or source["definition_id"] != configuration["compiled_plan"]["definition_id"]
        or [room["order"] for room in source["rooms"]]
        != [room["order"] for room in configuration["compiled_plan"]["rooms"]]
        or source.get("original_guide_document_sha256")
        != configuration["compiled_plan"].get("original_guide_document_sha256")
    ):
        raise ValueError("Original guide carrier differs from current immutable source")
    if definition["id"] != source["definition_id"]:
        raise ValueError("Native dungeon identity differs from reviewed source")
    prepared = draft(
        source,
        definition,
        native_monsters,
        admission_policy=admission_policy,
    )
    plan = copy.deepcopy(configuration["compiled_plan"])
    plan["rooms"] = [
        dict(order=room["order"], monsters=room["monsters"], diagnostics=[])
        for room in prepared["rooms"]
    ]
    plan["document_sha256"] = canonical_hash(prepared)
    plan["generated_fields"] = [
        dict(
            order=room["order"],
            policy_applied=room["policy_applied"],
            fields=room["generated_fields"],
        )
        for room in prepared["rooms"]
    ]
    plan["local_policy"] = (
        "Preserve original guide quantities and native-bound named identities; "
        "only explicitly anonymous entries use admitted native species selection."
    )
    candidate = prepare_configuration(
        plan,
        configuration["topology"],
        configuration["route"],
        version=version,
        provenance=configuration["provenance"],
    )
    if candidate["level_policy"] != configuration["level_policy"] or {
        key: value
        for key, value in candidate["context_policy"].items()
        if key != "policy_version"
    } != {
        key: value
        for key, value in configuration["context_policy"].items()
        if key != "policy_version"
    }:
        raise ValueError("Named roster repair cannot change level or context policy")
    return candidate, {
        "source_sha256": canonical_hash(configuration),
        "candidate_sha256": canonical_hash(candidate),
        "original_guide_document_sha256": source["document_sha256"],
        "guide_carrier_version": guide_carrier["version"],
        "guide_carrier_sha256": canonical_hash(guide_carrier),
        "original_rooms": source["rooms"],
        "native_topology_unchanged": candidate["topology"] == configuration["topology"],
        "installed": False,
        "existing_runs_changed": False,
    }


def native_definition(configuration, definitions):
    plan = configuration["compiled_plan"]
    raw = definitions.get(plan["definition_id"])
    if raw is not None:
        return dict(id=raw["id"], type="DUNGEON", raw_cno=raw["cno"])
    if (
        plan.get("identity_policy") != "local_legacy_map_registry"
        or plan.get("species_pool_provenance") != "guide_verified_native_references"
    ):
        raise ValueError(
            "Native species definition or reviewed legacy identity is absent"
        )
    return dict(
        id=plan["definition_id"],
        type="DUNGEON",
        policy_mode="local_legacy_map_registry",
        native_definition_id=None,
        species_pool_provenance="guide_verified_native_references",
        local_species_pool=sorted(
            {row["ref_id"] for room in plan["rooms"] for row in room["monsters"]}
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--native-monsters", type=Path, required=True)
    parser.add_argument("--native-definitions", type=Path, required=True)
    parser.add_argument("--french-archive", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text())
    authority = json.loads(args.native_monsters.read_text())
    monsters, locale = native_locale_monsters(
        authority["monsters"], args.french_archive
    )
    definitions = {
        row["id"]: row for row in json.loads(args.native_definitions.read_text())
    }
    maximum = {}
    versions = {}
    for row in catalog["configuration_versions"]:
        maximum[row["route_key"]] = max(
            maximum.get(row["route_key"], 0), row["policy_version"]
        )
        versions.setdefault(row["route_key"], []).append(row["configuration"])
    args.output_directory.mkdir()
    manifest = dict(
        installed=False,
        existing_runs_changed=False,
        locale=locale,
        candidates=[],
        blocked=[],
        reviewed_unchanged=[],
    )
    for row in catalog["active_configurations"]:
        cfg = row["configuration"]
        key = row["route_key"]
        if not generated_source(cfg):
            manifest["reviewed_unchanged"].append(key)
            continue
        try:
            carrier = select_guide_carrier(cfg, versions[key])
            definition = native_definition(carrier, definitions)
            candidate, receipt = prepare(
                cfg,
                monsters,
                authority["admission_policy"],
                definition,
                version=maximum[key] + 1,
                guide_carrier=carrier,
            )
        except (KeyError, ValueError) as error:
            manifest["blocked"].append(dict(route_key=key, reason=str(error)))
            continue
        path = args.output_directory / (key + ".json")
        path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n")
        manifest["candidates"].append(
            dict(route_key=key, path=str(path.resolve()), **receipt)
        )
    (args.output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: len(manifest[key])
                for key in ("candidates", "blocked", "reviewed_unchanged")
            }
        )
    )


if __name__ == "__main__":
    main()
