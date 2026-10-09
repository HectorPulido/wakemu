"""Prepare exact native profile export seeds from persisted owned-roster records.

No database or runtime catalog imports. Profiles not occupied in these records
cannot be added through this interface. Records themselves remain private.
"""
import argparse
import hashlib
import json
from pathlib import Path
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    captured_profile_seeds,
)


def prepare(records):
    if type(records) is not list:
        raise ValueError("Expected a list of owned captured-roster records")
    identities, profiles = [], set()
    owners = set()
    for record in records:
        if not isinstance(record, dict) or type(record.get("owner_id")) is not int:
            raise ValueError("Owned record identity required")
        owner = record["owner_id"]
        if owner in owners:
            raise ValueError("Duplicate captured roster owner")
        owners.add(owner)
        roster = OwnedCapturedRoster.from_record(record, expected_owner_id=owner)
        seeds = captured_profile_seeds(roster)
        profiles.update(seeds)
        identity = hashlib.sha256(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        identities.append(
            {"owner_id": owner, "record_sha256": identity, "profile_ids": list(seeds)}
        )
    return {
        "schema": "owned-captured-profile-seeds-v1",
        "rosters": identities,
        "profile_ids": sorted(profiles),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    before = args.records.read_bytes()
    result = prepare(json.loads(before))
    result["input_file_sha256"] = hashlib.sha256(before).hexdigest()
    if args.records.read_bytes() != before:
        raise RuntimeError("Owned records changed while deriving native seeds")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "rosters": len(result["rosters"]),
                "actual_profile_seeds": len(result["profile_ids"]),
            }
        )
    )


if __name__ == "__main__":
    main()
