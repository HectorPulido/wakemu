"""Read-only PostgreSQL Sram closure, including inherited eYW trap dependencies."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import os
import psycopg
from audit_huppermage_catalog import compact, reference_values

ROOT = Path(__file__).resolve().parents[2]
EFFECT_PATHS = (
    "spell-effect-trees.json",
    "granted-spell-effect-trees.json",
    "combat-state-definitions.json",
    "native-area-effect-trees.json",
    "native-class-spell-grant-closure.json",
    "native-class-summon-effect-closure.json",
)


def inventory(connection):
    revision = connection.execute(
        "SELECT a.revision FROM native_catalog_active a JOIN native_catalog_releases r USING(revision) WHERE a.id=1 AND r.complete"
    ).fetchone()[0]
    hashes = {}

    def document(path):
        raw, digest = connection.execute(
            "SELECT raw,sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (revision, path),
        ).fetchone()
        raw = bytes(raw)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("PostgreSQL document checksum mismatch")
        hashes[path] = digest
        return json.loads(raw)

    spells = [s for s in document("spells.json")["spells"] if s["breed"] == 4]
    innate = next(
        r
        for r in document("breed-innate-definitions.json")["breeds"]
        if r["breed"] == 4
    )
    paths = set(EFFECT_PATHS) | {
        "native-effect-areas.json",
        "native-class-summon-abilities.json",
        "native-class-summon-initial-states.json",
    }
    for path in sorted(paths):
        result = connection.execute(
            "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (revision, path),
        ).fetchone()
        if result:
            hashes[path] = result[0]
    nodes = {}
    edges = []
    missing = []
    dynamic = []
    pending = [("spell", s["id"]) for s in spells] + [
        ("state", s["reference"]) for s in innate["innate_states"]
    ]
    while pending:
        kind, identity = pending.pop()
        key = f"{kind}:{identity}"
        if key in nodes:
            continue
        collection = {
            "spell": "spells",
            "state": "states",
            "effect": "effects",
            "area": "areas",
            "profile": "profiles",
        }[kind]
        lookup = (
            EFFECT_PATHS
            if kind in ("spell", "state", "effect")
            else ("native-effect-areas.json",)
            if kind == "area"
            else ("native-class-summon-abilities.json",)
        )
        rows = connection.execute(
            "SELECT path,payload FROM native_catalog_records WHERE revision=%s AND path=ANY(%s) AND collection=%s AND record_key=%s",
            (revision, list(lookup), collection, str(identity)),
        ).fetchall()
        if not rows:
            missing.append(key)
            nodes[key] = dict(missing=True)
            continue
        values = [r[1] for r in rows]
        if kind == "effect":
            for field in ("effect_class", "children", "parameters", "criteria"):
                if any(v.get(field) != values[0].get(field) for v in values[1:]):
                    raise ValueError(f"Conflicting native Sram record: {key}/{field}")
        row = values[0]
        nodes[key] = dict(compact(row), catalog_paths=sorted(r[0] for r in rows))
        targets = []
        if kind == "spell":
            targets = [
                ("effect", v) for level in row.get("levels", []) for v in level[2]
            ]
        elif kind in ("state", "area"):
            targets = [("effect", v) for v in row.get("effect_ids", [])]
        elif kind == "profile":
            targets = [("spell", v["reference"]) for v in row.get("abilities", [])]
            initial = connection.execute(
                "SELECT payload FROM native_catalog_records WHERE revision=%s AND path=%s AND collection=%s AND record_key=%s",
                (
                    revision,
                    "native-class-summon-initial-states.json",
                    "profiles",
                    str(identity),
                ),
            ).fetchone()
            nodes[key]["initial_state_source"] = initial[0] if initial else None
            if initial:
                for entry in initial[0].get("initial_states", []):
                    if isinstance(entry, dict):
                        targets.append(("state", entry["reference"]))
        else:
            targets = [("effect", v) for v in row.get("children", [])]
            family = row["effect_class"]
            spec = {
                304: ("state", 0),
                308: ("area", 0),
                314: ("area", 0),
                315: ("area", 0),
                339: ("area", 0),
                649: ("spell", 2),
                307: ("profile", 0),
            }.get(family)
            if spec:
                refkind, slot = spec
                refs = reference_values(row, slot)
                if not refs:
                    dynamic.append(
                        dict(
                            source=key,
                            family=family,
                            slot=slot,
                            status="no finite exported reference authority",
                        )
                    )
                targets += [(refkind, v) for v in refs]
        for target in sorted(set(targets)):
            edges.append(dict(source=key, target=f"{target[0]}:{target[1]}"))
            pending.append(target)
    return dict(
        schema="sram-postgresql-closure-v1",
        breed=4,
        revision=revision,
        document_hashes=hashes,
        source_spells=spells,
        innate=innate,
        nodes=nodes,
        edges=edges,
        counts=dict(Counter(key.split(":")[0] for key in nodes)),
        missing=sorted(missing),
        dynamic_references=dynamic,
        accreditation="source dependency closure only; no automatic gameplay or client completion claim",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    password = Path(os.environ["WAKFU_DATABASE_PASSWORD_FILE"]).read_text().strip()
    with psycopg.connect(
        os.environ["WAKFU_DATABASE_URL"],
        password=password,
        options="-c default_transaction_read_only=on",
    ) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        report = inventory(connection)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                revision=report["revision"],
                counts=report["counts"],
                missing=report["missing"],
                dynamic=len(report["dynamic_references"]),
            )
        )
    )


if __name__ == "__main__":
    main()
