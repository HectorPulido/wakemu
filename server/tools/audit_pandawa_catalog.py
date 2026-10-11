"""Read-only Pandawa closure including native barrel-constructor state seeds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import psycopg
import audit_huppermage_catalog as reader

reader.BREED = 12


def inventory(connection):
    result = reader.inventory(connection)
    revision = result["revision"]
    path = "native-class-summon-initial-states.json"
    raw, digest = connection.execute(
        "SELECT raw,sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
        (revision, path),
    ).fetchone()
    raw = bytes(raw)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Barrel constructor catalog checksum mismatch")
    profile = json.loads(raw)["profiles"]["3794"]
    triples = profile["initial_state_triples"]
    pending = [("states", str(triples[index])) for index in range(0, len(triples), 3)]
    closure, missing = {}, []
    while pending:
        kind, identity = pending.pop()
        key = kind + ":" + identity
        if key in closure:
            continue
        row = connection.execute(
            "SELECT payload FROM native_catalog_records WHERE revision=%s "
            "AND path='combat-state-definitions.json' AND collection=%s AND record_key=%s",
            (revision, kind, identity),
        ).fetchone()
        if row is None:
            missing.append(key)
            continue
        payload = row[0]
        closure[key] = payload
        pending.extend(
            ("effects", str(child))
            for child in payload.get("effect_ids", ())
            if kind == "states"
        )
        pending.extend(("effects", str(child)) for child in payload.get("children", ()))
    result["constructor_profiles"] = {
        "3794": dict(
            source_path=path,
            source_sha256=digest,
            descriptor_level=-2,
            profile=profile,
            initial_state_closure=closure,
            missing=missing,
        )
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    kwargs = dict(options="-c default_transaction_read_only=on")
    if os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"):
        kwargs["password"] = (
            Path(os.environ["WAKFU_DATABASE_PASSWORD_FILE"]).read_text().strip()
        )
    with psycopg.connect(os.environ["WAKFU_DATABASE_URL"], **kwargs) as connection:
        result = inventory(connection)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            dict(
                revision=result["revision"],
                counts=result["counts"],
                constructor_missing=result["constructor_profiles"]["3794"]["missing"],
            )
        )
    )


if __name__ == "__main__":
    main()
