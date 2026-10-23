"""Build append-only source302 named-type policies, never gameplay activation."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

if __package__:
    from .compile_environmental_destroy_sources import (
        compile_named_sources,
        qualify_named_sources,
        NAMED_POLICY,
        sql,
    )
else:
    from compile_environmental_destroy_sources import (
        compile_named_sources,
        qualify_named_sources,
        NAMED_POLICY,
        sql,
    )


def build(
    *,
    specs_path,
    inventory_path,
    monsters_path,
    native_actions_path,
    excluded_path,
    audit_path,
    audited_manifest_path,
    output_directory
):
    specs = json.loads(specs_path.read_text())
    for source, expected in specs["source_sha256"].items():
        if sha256(Path(source).read_bytes()).hexdigest() != expected:
            raise ValueError("Named-type source document SHA changed: " + source)
    actions = json.loads(native_actions_path.read_text())
    docs = {row["path"]: row["sha256"] for row in actions["documents"]}
    if docs.get("monsters.json") != sha256(monsters_path.read_bytes()).hexdigest():
        raise ValueError(
            "Native actor document differs from actual action catalog release"
        )
    excluded = json.loads(excluded_path.read_text())
    excluded_ids = {
        case["scenario_id"]
        for template in excluded["templates"]
        for case in template["scenario_cases"]
    }
    rows, selections = compile_named_sources(
        specs,
        json.loads(inventory_path.read_text()),
        json.loads(monsters_path.read_text()),
        actions,
        excluded_ids=excluded_ids,
    )
    audit = json.loads(audit_path.read_text())
    if (
        sha256(audited_manifest_path.read_bytes()).hexdigest()
        != audit["source_manifest_sha256"]
    ):
        raise ValueError("Deterministic annotation baseline manifest changed")
    if json.loads(audited_manifest_path.read_text())["rows"] != rows:
        raise ValueError(
            "Named-type annotation was produced for another source selection"
        )
    rows, pending = qualify_named_sources(rows, audit)
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest = dict(
        policy_version=NAMED_POLICY,
        counts=dict(
            scenarios=len(rows),
            templates=len({row["template_reference"] for row in rows}),
            species=len({row["monster_reference"] for row in rows}),
            source_rows=len(rows),
        ),
        catalog_revision=actions["revision"],
        catalog_documents=actions["documents"],
        excluded_historical_scenarios=sorted(excluded_ids),
        pending_unproven_targets=pending,
        annotation_sha256=sha256(audit_path.read_bytes()).hexdigest(),
        selections=selections,
        rows=rows,
    )
    (output_directory / "destroy_named_sources.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    (output_directory / "302_environmental_named_destroy_sources.sql").write_text(
        "-- Declared native named-type variants. Source data only; no profile activation.\n"
        + sql(rows)
    )
    return manifest["counts"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "specs_path",
        "inventory_path",
        "monsters_path",
        "native_actions_path",
        "excluded_path",
        "audit_path",
        "audited_manifest_path",
        "output_directory",
    ):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    print(json.dumps(build(**vars(parser.parse_args()))))


if __name__ == "__main__":
    main()
