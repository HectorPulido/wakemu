"""Compile all reviewed guides, apply verified evidence optionally, stage ready configs.

This tool never activates a database configuration or restarts a service.
"""
import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

from wakfu_server.maps.dungeon_catalog import compile_catalog
from wakfu_server.maps.dungeon_runtime_config import prepare_configuration


def module(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py")
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_all(documents, native, index, routes, topologies, *, version, provenance):
    """Return exhaustive coverage and executable configs, without side effects."""
    links = {row["guide_slug"]: row for row in index["guide_links"]}
    updated = []
    identity_diagnostics = {}
    for original in documents:
        document = copy.deepcopy(original)
        slug = document["dungeon"]["slug"]
        link = links.get(slug)
        reasons = []
        route = None
        if link is None or link["status"] != "exact_unique":
            reasons.append("unresolved_native_dungeon_identity")
        else:
            candidates = [
                r for r in routes if r["definition_id"] == link["client_definition_id"]
            ]
            if len(candidates) != 1:
                reasons.append("missing_or_ambiguous_entry_route")
            else:
                route = candidates[0]
                definition = link["candidates"][0]
                if route["start_map_id"] not in definition["raw_aHA"]:
                    raise ValueError("Native route contradicts dungeon definition")
                identity = dict(
                    client_definition_id=route["definition_id"],
                    client_template_id=route["template_id"],
                    client_asset_map_id=route["start_map_id"],
                )
                for field, value in identity.items():
                    if document["dungeon"][field] not in (None, value):
                        raise ValueError("Conflicting native dungeon identity")
                    document["dungeon"][field] = value
        identity_diagnostics[slug] = (reasons, route)
        updated.append(document)
    plans = compile_catalog(updated, native)
    configs, coverage = [], []
    for plan in plans:
        reasons, route = identity_diagnostics[plan.slug]
        reasons = list(reasons) + list(plan.diagnostics)
        for room in plan.rooms:
            reasons.extend(
                f"room[{room.order}].{reason}" for reason in room.diagnostics
            )
        topology = topologies.get(plan.slug)
        if topology is None:
            reasons.append("missing_verified_native_topology")
        if not plan.rooms:
            reasons.append("no_reviewed_rooms")
        if not reasons:
            try:
                configs.append(
                    prepare_configuration(
                        plan.import_record(),
                        topology,
                        route,
                        version=version,
                        provenance=provenance,
                    )
                )
            except ValueError as error:
                reasons.append("runtime_configuration: " + str(error))
        coverage.append(
            dict(
                slug=plan.slug,
                roster_ready=plan.roster_ready,
                configuration_ready=not reasons,
                reasons=reasons,
                rooms=len(plan.rooms),
            )
        )
    return updated, plans, configs, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--archive", default=".runtime/local/methodwakfu-dungeons")
    parser.add_argument(
        "--native-index",
        help="Override the source-verified native guide identity index",
    )
    parser.add_argument("--routes", required=True)
    parser.add_argument(
        "--topologies",
        required=True,
        help="JSON object mapping guide slug to verified topology",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--apply-evidence", action="store_true")
    parser.add_argument("--backup-directory")
    parser.add_argument(
        "--select",
        action="append",
        help="Restrict emitted ready configurations; coverage remains exhaustive",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    resolver, applier = module("resolve_dungeon_native_references"), module(
        "apply_dungeon_native_references"
    )

    def path(value):
        return resolver.safe_path(root, value)

    archive = args.archive.rstrip("/")
    index_path = path(args.native_index or archive + "/native-dungeon-index.json")
    index = json.loads(index_path.read_text())
    names_path = archive + "/native-monster-names-fr.json"
    names = json.loads(path(names_path).read_text())
    report = resolver.build_report(
        root,
        index,
        names,
        native_name_catalog=names_path,
        composition_directory=archive + "/compositions",
    )
    for record in report["records"]:
        if sha(path(record["composition"])) != record["composition_sha256"]:
            raise ValueError("Composition source changed before preparation")
    resolved_documents, resolved_count = applier.prepare(root, report)
    documents = [
        resolved_documents.get(p, json.loads(p.read_text()))
        for p in sorted(path(archive + "/compositions").glob("*.json"))
    ]
    native = json.loads(path("server/protocol/monsters.json").read_text())["monsters"]
    routes = json.loads(path(args.routes).read_text())
    topologies = json.loads(path(args.topologies).read_text())
    updated, plans, configs, coverage = prepare_all(
        documents,
        native,
        index,
        routes,
        topologies,
        version=args.version,
        provenance="Reviewed guide evidence and installed native catalogs; explicit local runtime policy.",
    )
    if args.select:
        selected = set(args.select)
        if not selected <= {row["slug"] for row in coverage}:
            raise ValueError("Selected guide does not exist")
        if not selected <= {config["slug"] for config in configs}:
            raise ValueError("Selected guide is not fully ready")
        configs = [config for config in configs if config["slug"] in selected]
    output = path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.apply_evidence:
        if not args.backup_directory:
            raise ValueError("Applying evidence requires a fresh backup directory")
        backup = path(args.backup_directory)
        snapshot_paths = set(resolved_documents) | {
            index_path,
            path(index["sources"]["catalog"]["path"]),
        }
        originals = {target: target.read_bytes() for target in snapshot_paths}
        try:
            applier.apply(root, report, backup)
            catalog_path = path(index["sources"]["catalog"]["path"])
            (backup / "composition-catalog.aggregate.json").write_bytes(
                catalog_path.read_bytes()
            )
            (backup / "native-dungeon-index.before.json").write_bytes(
                index_path.read_bytes()
            )
            actual = [
                json.loads(p.read_text())
                for p in sorted(path(archive + "/compositions").glob("*.json"))
            ]
            catalog = dict(
                schema_version=1,
                summary=dict(
                    guides=len(actual),
                    independently_reviewed=sum(
                        d["extraction"]["reviewed"] for d in actual
                    ),
                    status_counts=dict(
                        Counter(d["extraction"]["status"] for d in actual)
                    ),
                    rooms=sum(len(d["rooms"]) for d in actual),
                    runtime_imported=False,
                ),
                dungeons=actual,
            )
            catalog_path.write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
            )
            # Reference resolution changes neither guide titles nor native identities.
            # Preserve refined source-backed identity links while refreshing hashes.
            refreshed = copy.deepcopy(index)
            refreshed["sources"] = {
                key: dict(path=source["path"], sha256=sha(path(source["path"])))
                for key, source in index["sources"].items()
            }
            index_path.write_text(
                json.dumps(refreshed, ensure_ascii=False, indent=2) + "\n"
            )
        except BaseException:
            for target, payload in originals.items():
                temporary = target.with_name(target.name + ".bulk-rollback.tmp")
                temporary.write_bytes(payload)
                temporary.replace(target)
            raise
    result = dict(
        schema_version=1,
        runtime_imported=False,
        evidence_applied=args.apply_evidence,
        resolved_occurrences=resolved_count,
        summary=dict(
            guides=len(coverage),
            rooms=sum(r["rooms"] for r in coverage),
            configuration_ready=sum(r["configuration_ready"] for r in coverage),
            configurations_emitted=len(configs),
        ),
        coverage=coverage,
    )
    for filename, value in [
        ("coverage.json", result),
        ("resolved-catalog.json", dict(schema_version=1, dungeons=updated)),
        (
            "compiled-catalog.json",
            dict(schema_version=1, dungeons=[p.import_record() for p in plans]),
        ),
        ("configurations.json", dict(schema_version=1, configurations=configs)),
        ("reference-resolution.json", report),
    ]:
        (output / filename).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
