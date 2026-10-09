#!/usr/bin/env python3
"""Compare the class-scoped native export to persisted catalogs, streaming JSON.

SQLite is a private disposable comparison index, never a game database. Native
HMI ID allocation-only differences remain observations, not silent rewrites.
"""
import gzip
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / ".runtime/combat-review-20261007/mechanic-graph"
REPORTS = ROOT / "docs/reports/combat-inventory"
CATALOGS = [
    ROOT / "server/protocol" / name
    for name in (
        "spell-effect-trees.json",
        "granted-spell-effect-trees.json",
        "combat-state-definitions.json",
        "native-area-effect-trees.json",
    )
]
NATIVE = PRIVATE / "native-graph.jsonl.gz"
POINT_AREAS = ROOT / "server/protocol/native-point-areas.json"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def records(path):
    decompressor = None
    if path.suffix == ".gz":
        decompressor = subprocess.Popen(
            ["gzip", "-dc", str(path)], stdout=subprocess.PIPE
        )
        process = subprocess.Popen(
            ["jq", "-c", ".effects|to_entries[]"],
            stdin=decompressor.stdout,
            stdout=subprocess.PIPE,
            text=True,
        )
        decompressor.stdout.close()
    else:
        process = subprocess.Popen(
            ["jq", "-c", ".effects|to_entries[]", str(path)],
            stdout=subprocess.PIPE,
            text=True,
        )
    for line in process.stdout:
        row = json.loads(line)
        yield int(row["key"]), row["value"]
    if process.wait() != 0:
        raise ValueError(f"Catalog parser failed: {path}")
    if decompressor is not None and decompressor.wait() != 0:
        raise ValueError(f"Catalog decompression failed: {path}")


def native_rows():
    with gzip.open(NATIVE, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if (
                row["kind"] == "effect"
                and not row.get("native_missing")
                and not row.get("native_export_exception")
            ):
                yield row


def no_allocated_hmi_ids(value):
    result = {}
    for channel, actions in value.items():
        selected = []
        for action in actions:
            record = {key: field for key, field in action.items() if key != "id"}
            text = record.get("native")
            marker = "HMIAction{m_id=" + str(action.get("id")) + ","
            if isinstance(text, str) and text.count(marker) == 1:
                record["native"] = text.replace(
                    marker, "HMIAction{m_id=<allocated-id>,", 1
                )
            selected.append(record)
        result[channel] = selected
    return result


def main():
    paths = CATALOGS + [
        NATIVE,
        POINT_AREAS,
        ROOT / "server/wakfu_server/combat/combat_native_area_metadata.py",
        ROOT / "server/wakfu_server/combat/combat_effect_runtime.py",
        Path(__file__),
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    native_timings = {
        row["reference"]: {
            level: row["samples"][level]["timing"]
            for level in ("0", "1", "200", "32767")
            if level in row["samples"]
        }
        for row in native_rows()
    }
    wanted = set(native_timings)
    point_areas = json.loads(POINT_AREAS.read_text())
    database = PRIVATE / "local-effect-comparison.sqlite3"
    if database.exists():
        database.unlink()
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE effects(reference INTEGER PRIMARY KEY, row_json TEXT, locations TEXT)"
    )
    conflicts = []
    sources = {}
    for path in CATALOGS:
        selected = 0
        for reference, row in records(path):
            if reference not in wanted:
                continue
            selected += 1
            encoded = json.dumps(row, sort_keys=True, separators=(",", ":"))
            location = str(path.relative_to(ROOT))
            existing = connection.execute(
                "SELECT row_json,locations FROM effects WHERE reference=?", (reference,)
            ).fetchone()
            if existing:
                if existing[0] != encoded:
                    prior = json.loads(existing[0])
                    fields = sorted(
                        key
                        for key in set(prior) | set(row)
                        if prior.get(key) != row.get(key)
                    )
                    reasons = []
                    for field in fields:
                        if field == "native_hmi_actions" and no_allocated_hmi_ids(
                            prior.get(field, {})
                        ) == no_allocated_hmi_ids(row.get(field, {})):
                            reasons.append("native_HMI_allocation_only")
                        elif field == "native_timing_checks" and all(
                            native_timings[reference].get(str(level)) == timing
                            for value in (prior.get(field, {}), row.get(field, {}))
                            for level, timing in value.items()
                        ):
                            reasons.append("additional_timing_samples_equal_native")
                        elif field == "native_area_points" and all(
                            value.get(field)
                            == point_areas.get(str(reference), {}).get(field)
                            for value in (prior, row)
                            if field in value
                        ):
                            reasons.append(
                                "point_metadata_present_in_separate_native_join"
                            )
                        else:
                            reasons.append("unclassified_definition_difference")
                    conflicts.append(
                        {
                            "reference": reference,
                            "locations": json.loads(existing[1]) + [location],
                            "different_fields": fields,
                            "field_classifications": reasons,
                            "classification": "metadata_only_native_equal"
                            if "unclassified_definition_difference" not in reasons
                            else "definition_field_difference_requires_review",
                        }
                    )
                locations = json.loads(existing[1])
                locations.append(location)
                connection.execute(
                    "UPDATE effects SET locations=? WHERE reference=?",
                    (json.dumps(locations), reference),
                )
            else:
                connection.execute(
                    "INSERT INTO effects VALUES(?,?,?)",
                    (reference, encoded, json.dumps([location])),
                )
        connection.commit()
        sources[str(path.relative_to(ROOT))] = selected
        print(json.dumps({"catalog": path.name, "selected": selected}), flush=True)
    mismatches = []
    missing = []
    coverage = []
    matched = 0
    field_counts = Counter()
    allocation = []
    joined_points = []
    tree_omissions = []
    for native in native_rows():
        reference = native["reference"]
        stored = connection.execute(
            "SELECT row_json,locations FROM effects WHERE reference=?", (reference,)
        ).fetchone()
        if stored is None:
            missing.append(reference)
            continue
        local = json.loads(stored[0])
        metadata = native["native_metadata"]
        differences = []
        missing_fields = []
        if (
            local.get("area_class") in ("anE", "anJ")
            and "native_area_points" not in local
        ):
            point = point_areas.get(str(reference))
            if point is not None and all(
                point.get(field) == local.get(field)
                for field in ("area_class", "area_native", "effect_class")
            ):
                tree_omissions.append(reference)
                local = dict(local, native_area_points=point["native_area_points"])
                joined_points.append(reference)
        expected = {
            "effect_class": native["family"],
            "children": native["children_ordered"],
            "criteria": native["criterion_raw"],
            "minimum_level": native["minimum_level"],
            "maximum_level": native["maximum_level"],
            "parameters": native["raw_parameters"],
            "variant": native["native_definition"]["native_fields"]["Qa.bev"],
        }
        expected.update(metadata)
        # These registry fields are supplied by a separate retained metadata catalog,
        # not by the tree row. They remain explicitly outside this tree comparison.
        for field, value in expected.items():
            if field not in local:
                missing_fields.append(field)
                continue
            if local[field] == value:
                continue
            if field == "native_hmi_actions" and no_allocated_hmi_ids(
                local[field]
            ) == no_allocated_hmi_ids(value):
                allocation.append(reference)
                continue
            differences.append(
                {"field": field, "expected_native": value, "persisted": local[field]}
            )
            field_counts[field] += 1
        for field, sample_key in (
            ("parameters_by_level", "parameters"),
            ("probabilities", "probability"),
        ):
            samples = local.get(field)
            if not isinstance(samples, list):
                missing_fields.append(field)
                continue
            bad = []
            for level, value in enumerate(samples, 1):
                native_sample = native["samples"].get(str(level))
                if native_sample is None:
                    continue
                if value != native_sample[sample_key]:
                    bad.append(level)
            if bad:
                differences.append({"field": field, "different_sample_levels": bad})
                field_counts[field] += 1
            if len(samples) < 245:
                coverage.append(
                    {
                        "reference": reference,
                        "field": field,
                        "persisted_levels": len(samples),
                        "native_export_levels": 245,
                        "status": "unattested_extension_domain_not_numerical_mismatch",
                    }
                )
        if "native_timing_checks" in local:
            bad = []
            for level, timing in local["native_timing_checks"].items():
                sample = native["samples"].get(str(level))
                if sample is not None and timing != sample["timing"]:
                    bad.append(int(level))
            if bad:
                differences.append(
                    {"field": "native_timing_checks", "different_sample_levels": bad}
                )
                field_counts["native_timing_checks"] += 1
        if differences or missing_fields:
            mismatches.append(
                {
                    "reference": reference,
                    "family": native["family"],
                    "native_runner": native["native_runner_class"],
                    "locations": json.loads(stored[1]),
                    "differences": differences,
                    "missing_fields": missing_fields,
                }
            )
        else:
            matched += 1
    connection.close()
    after = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    report = {
        "scope": "Exact persisted tree fields versus native class-scoped metadata/parameter samples; no runtime execution",
        "sources_before": before,
        "sources_after": after,
        "sources_stable": before == after,
        "native_effects": len(wanted),
        "fully_matched_available_tree_fields": matched,
        "missing_effects": missing,
        "local_duplicate_definition_differences": conflicts,
        "catalog_selected_counts": sources,
        "different_field_counts": dict(field_counts),
        "native_hmi_id_allocation_only": allocation,
        "tree_point_field_omissions_covered_by_native_join": tree_omissions,
        "native_point_area_join_count": len(joined_points),
        "differences_or_missing_tree_fields": mismatches,
        "sample_domain_extensions": coverage,
        "limitations": [
            "Native OY.d/toString exports its allocated ID twice; normalization removes only matching HMIAction.m_id and id while every other HMI field remains exact. Allocation/lifecycle semantics remain separate.",
            "Missing fields and shorter sample domains are reported, never silently defaulted.",
            "Registry event fields require comparison with separate retained metadata; this report compares tree rows only.",
            "Matching native definitions does not establish dynamic reachability or client behavior.",
        ],
    }
    path = REPORTS / "class-native-catalog-comparison-20261007.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "native_effects": len(wanted),
                "matched": matched,
                "mismatch_rows": len(mismatches),
                "missing": len(missing),
                "duplicate_definition_differences": len(conflicts),
                "allocation_only": len(allocation),
                "different_field_counts": dict(field_counts),
                "joined_points": len(joined_points),
                "duplicate_classifications": dict(
                    Counter(item["classification"] for item in conflicts)
                ),
                "stable": before == after,
            }
        )
    )


if __name__ == "__main__":
    main()
