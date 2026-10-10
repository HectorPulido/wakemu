"""Stream the exact class graph and scoped original captured projection."""
import gzip
from collections import Counter
import hashlib
import json
import re
from import_class_summon_dependencies import entries


def captured_rows(path):
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            row = dict(row)
            row["parameter_sample_levels"] = sorted(map(int, row.get("samples", {})))
            row["native_criterion_structure"] = row.get("criterion_native")
            row.pop("samples", None)
            yield row["kind"] + ":" + str(row["reference"]), row


def strict_identity(key, original, projected):
    if original.get("kind") == "effect":
        for field in (
            "family",
            "native_runner_class",
            "raw_parameters",
            "minimum_level",
            "maximum_level",
            "criterion_raw",
        ):
            if original.get(field) != projected.get(field):
                raise ValueError(
                    "Conflicting original projected identity " + key + "/" + field
                )


def merged_nodes(graph, *projections):
    projected = {}
    for path in projections:
        for key, row in captured_rows(path):
            if key in projected:
                strict_identity(key, projected[key], row)
            else:
                projected[key] = row
    seen = set()
    for key, row in entries(graph, "nodes"):
        if key in projected:
            strict_identity(key, row, projected[key])
        seen.add(key)
        yield key, row
    for key, row in projected.items():
        if key not in seen:
            yield key, row


def referenced_projection_owners(path, manifest_path, source_membership):
    manifest = json.loads(manifest_path.read_text())
    matches = [
        value
        for name, value in manifest["source_sha256"].items()
        if name.endswith("/" + path.name)
    ]
    if len(matches) != 1:
        raise ValueError("Ambiguous typed projection provenance")
    expected = matches[0]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Referenced typed projection hash mismatch")
    rows = dict(captured_rows(path))
    if dict(Counter(row["kind"] for row in rows.values())) != manifest["counts"]:
        raise ValueError("Referenced typed projection count mismatch")
    if any(
        row.get("native_missing") or row.get("native_export_exception")
        for row in rows.values()
    ):
        raise ValueError("Missing referenced original definition")
    adjacency = {}
    for key, row in rows.items():
        edges = set("effect:" + str(r) for r in row.get("children_ordered", []))
        for values in row.get("root_samples", {}).values():
            edges.update("effect:" + str(r) for r in values)
        edges.update("effect:" + str(r) for r in row.get("raw_roots", []))
        for sample in row.get("level_samples", {}).values():
            edges.update("effect:" + str(r) for r in sample.get("roots", []))
        for reference in row.get("classified_reference_samples", []):
            if 0 <= reference["sample_level"] <= 245:
                edges.add(reference["kind"] + ":" + str(reference["reference"]))
        adjacency[key] = edges
    owners = {}
    for edge in manifest["native_owner_target_edges"]:
        seed = "spell:" + str(edge["spell_reference"])
        if seed not in rows:
            continue
        breeds = set(
            source_membership.get("effect:" + str(edge["effect_reference"]), {})
        )
        if not breeds:
            raise ValueError(
                "Missing actual class ownership for referenced spell " + seed
            )
        pending, seen = [seed], set()
        while pending:
            key = pending.pop()
            if key in seen:
                continue
            seen.add(key)
            owners.setdefault(key, set()).update(breeds)
            pending.extend(adjacency.get(key, ()))
    if set(rows) - set(owners):
        raise ValueError("Referenced typed nodes have no proven class seed ownership")
    return manifest, owners


def verified_projection(path, manifest_path, runtime_path):
    from wakfu_server.storage import native_catalog

    manifest = json.loads(manifest_path.read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    # The large effects dictionary is irrelevant to this metadata comparison.
    # Keep a bounded prefix/tail instead of materializing the runtime catalog.
    with native_catalog.open(runtime_path, "rt") as stream:
        prefix = stream.read(1024)
        tail = prefix
        while chunk := stream.read(65536):
            tail = (tail + chunk)[-262144:]
    runtime = {
        "source_graph_sha256": json.loads(
            re.search(r'"source_graph_sha256"\s*:\s*("[^"]+")', prefix).group(1)
        )
    }
    decoder = json.JSONDecoder()
    for kind in ("effect", "spell", "state", "area"):
        match = re.search(r'"' + kind + r'_reference_closure"\s*:\s*', tail)
        if match is None:
            raise ValueError("Runtime closure metadata exceeds bounded tail")
        runtime[kind + "_reference_closure"] = decoder.raw_decode(tail[match.end() :])[
            0
        ]
    if (
        manifest["class_id"] != 2
        or runtime["source_graph_sha256"] != digest
        or manifest["missing_native_records"]
    ):
        raise ValueError("Unverified captured typed projection")
    counts = Counter()
    references = {}
    for key, row in captured_rows(path):
        counts[row["kind"]] += 1
        references.setdefault(row["kind"], []).append(row["reference"])
        if row.get("native_missing") or row.get("native_export_exception"):
            raise ValueError("Missing captured native record")
    if dict(counts) != manifest["counts"]:
        raise ValueError("Captured typed counts disagree")
    for kind in ("effect", "spell", "state", "area"):
        if sorted(references[kind]) != runtime[kind + "_reference_closure"]:
            raise ValueError("Runtime typed closure mismatch " + kind)
    return manifest, references
