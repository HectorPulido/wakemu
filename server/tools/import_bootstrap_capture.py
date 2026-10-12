"""Explicit offline import of the original ordered bootstrap capture into PostgreSQL."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from wakfu_server.postgres import Database
from wakfu_server.storage.bootstrap_capture import DEFAULT_KEY, import_records


def parse_source(source, expected_sha256):
    raw = Path(source).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            "Bootstrap capture source SHA256 does not match explicit expectation"
        )

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate bootstrap source JSON key")
            result[key] = value
        return result

    records = [
        json.loads(line, object_pairs_hook=unique_object)
        for line in raw.decode("utf-8").splitlines()
    ]
    return actual, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--capture-key", default=DEFAULT_KEY)
    arguments = parser.parse_args()
    source_sha, records = parse_source(arguments.source, arguments.expected_sha256)
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        with database.connection() as db:
            inserted = import_records(db, arguments.capture_key, source_sha, records)
        print(
            f"Bootstrap capture {arguments.capture_key}: {len(records)} records, "
            f"source_sha256={source_sha}, imported={inserted}"
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
