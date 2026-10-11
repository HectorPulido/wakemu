"""Join affected-pattern evidence into a historical inventory without promotion."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def annotate(inventory, queue):
    result = copy.deepcopy(inventory)
    native = {}
    for row in result["monsters"]:
        reference = row["ref"]
        if type(reference) is not int or reference <= 0 or reference in native:
            raise ValueError("Invalid or duplicate recovery inventory identity")
        native[reference] = row
        row["affected_source_patterns"] = []
    patterns = set()
    affected = set()
    for group in queue["groups"]:
        pattern = group["pattern"]
        if not isinstance(pattern, str) or not pattern or pattern in patterns:
            raise ValueError("Invalid or duplicate recovery pattern")
        patterns.add(pattern)
        seen = set()
        for entry in group["references"]:
            reference = entry["ref"]
            if (
                type(reference) is not int
                or reference not in native
                or reference in seen
            ):
                raise ValueError(
                    "Recovery queue reference is invalid or outside inventory"
                )
            seen.add(reference)
            affected.add(reference)
            native[reference]["affected_source_patterns"].append(
                dict(pattern=pattern, replay_status=entry["status"])
            )
    for field in ("unique_references", "unique_reference_count"):
        if field in queue and (
            type(queue[field]) is not int or queue[field] != len(affected)
        ):
            raise ValueError("Recovery queue unique count differs from its references")
    result["source_fix_affected_count"] = len(affected)
    result[
        "source_fix_annotation_note"
    ] = "Affected patterns are replay candidates, not readiness, execution or activation evidence."
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw_inventory, raw_queue = args.inventory.read_bytes(), args.queue.read_bytes()
    result = annotate(json.loads(raw_inventory), json.loads(raw_queue))
    result["source_fix_annotation_sha256"] = {
        str(path): hashlib.sha256(raw).hexdigest()
        for path, raw in ((args.inventory, raw_inventory), (args.queue, raw_queue))
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Annotated {result['source_fix_affected_count']} references; original stages preserved"
    )


if __name__ == "__main__":
    main()
