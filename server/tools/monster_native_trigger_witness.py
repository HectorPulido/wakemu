"""Source-backed trigger requirements, separate from actual execution qualification."""
from copy import deepcopy
import hashlib
from pathlib import Path


SCHEMA = "native-zero-range-constant-caller-index-v1"


def validate_source_index(document, root, candidate_hash):
    if (
        document.get("schema") != SCHEMA
        or document.get("base_candidate_manifest_sha256") != candidate_hash
    ):
        raise ValueError("Native trigger index identity differs")
    sources = document.get("source_sha256")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Missing native trigger source identities")
    for name, expected in sources.items():
        path = Path(name)
        if not path.is_absolute():
            path = Path(root) / path
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Native trigger source checksum differs: " + name)
    return document


def source_callers(document, context):
    rows = [row for row in document["rows"] if row["ref"] == context["reference"]]
    if len(rows) != 1:
        return []
    row = rows[0]
    if row.get("native_initial_state_source") != "sealed_original_aMb.cle" or context[
        "spell_id"
    ] not in row.get("zero_range_owned_spell_ids", []):
        return []
    return [
        deepcopy(path)
        for path in row.get("native_initialization", {}).get("source_paths", [])
        if path.get("spell_id") == context["spell_id"]
        and path.get("family") == 426
        and path.get("route_kind") == "native426_cast_callback"
        and path.get("qualification_status") == "pending_native_trigger_witness"
    ]


def annotate_pending(case, context, document, source_receipt):
    """A source caller never upgrades an ordinary failed cast into execution proof."""
    callers = source_callers(document, context)
    if case.get("status") != "pending" or not callers:
        return case
    result = deepcopy(case)
    result["native_execution_domain_status"] = "pending_native_trigger_witness"
    result["native_trigger_source"] = dict(
        source_receipt=source_receipt,
        callers=callers,
        actual_trigger_execution_proven=False,
        ordinary_cast_unavailable_claimed=False,
    )
    return result
