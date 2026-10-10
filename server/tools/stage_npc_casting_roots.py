"""Stage source-exported NPC casting roots without activating a catalog release."""
import argparse
import hashlib
import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from import_native_catalogs import catalog_records, release_revision

CATALOG_PATH = "native-class-casting-roots.json"


def validate_domain(monsters, casting, domain):
    spells = sorted(
        {
            ability["spell_id"]
            for monster in monsters["monsters"]
            for ability in monster["native_abilities"]
        }
    )
    tables = casting["spells"]
    missing = [spell for spell in spells if str(spell) not in tables]
    roots = sorted(
        {
            root
            for spell in spells
            if str(spell) in tables
            for row in tables[str(spell)]["levels"]
            for root in row[2]
        }
    )
    if (
        domain["spell_references"] != spells
        or domain["root_ids"] != roots
        or domain["missing_casting_tables"] != missing
        or missing
    ):
        raise ValueError("NPC root domain differs from pinned ability catalogs")


def merge(existing, exported, domain):
    if exported.get("schema") != "native-class-casting-roots-v1":
        raise ValueError("Invalid original casting root export")
    expected = {str(root) for root in domain["root_ids"]}
    if set(exported["roots"]) != expected or domain["missing_casting_tables"]:
        raise ValueError("Incomplete NPC ability casting root export")
    for field in ("fight_properties", "normal_casting_overrides"):
        if existing[field] != exported[field]:
            raise ValueError("Conflicting original casting global metadata")
    roots = dict(existing["roots"])
    for key, value in exported["roots"].items():
        if key in roots and roots[key] != value:
            raise ValueError("Conflicting original NPC casting root: " + key)
        if (
            set(value)
            != {
                "native_casting_collision_area",
                "native_selector_present",
                "native_target_selector",
            }
            or type(value["native_selector_present"]) is not bool
            or value["native_selector_present"]
            != (value["native_target_selector"] is not None)
        ):
            raise ValueError("Invalid original casting selector contract")
        roots[key] = value
    return {
        **existing,
        "roots": roots,
        "npc_ability_root_domain": {
            "spell_references": domain["spell_references"],
            "root_ids": domain["root_ids"],
            "source": "Original monster csd ability ownership and eVn.fKX/aZF",
            "base_revision": domain["base_revision"],
            "export_sha256": domain["export_sha256"],
            "exporter_sha256": domain["exporter_sha256"],
        },
    }


def stage(connection, exported, domain):
    with connection.transaction():
        active = connection.execute(
            "SELECT revision FROM native_catalog_active WHERE id=1 FOR SHARE"
        ).fetchone()[0]
        if active != domain["base_revision"]:
            raise ValueError("Published catalog changed before NPC root staging")
        sources = {
            path: json.loads(bytes(raw))
            for path, raw in connection.execute(
                "SELECT path,raw FROM native_catalog_documents WHERE revision=%s AND path=ANY(%s)",
                (active, ["monsters.json", "native-spell-casting.json"]),
            ).fetchall()
        }
        validate_domain(
            sources["monsters.json"], sources["native-spell-casting.json"], domain
        )
        old = connection.execute(
            "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (active, CATALOG_PATH),
        ).fetchone()
        merged = merge(json.loads(bytes(old[0])), exported, domain)
        raw = json.dumps(
            merged, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        checksum = hashlib.sha256(raw).hexdigest()
        manifest = connection.execute(
            "SELECT path,sha256,source_bytes FROM native_catalog_documents WHERE revision=%s ORDER BY path",
            (active,),
        ).fetchall()
        manifest = [
            (p, checksum, len(raw)) if p == CATALOG_PATH else (p, h, n)
            for p, h, n in manifest
        ]
        revision = release_revision(manifest)
        found = connection.execute(
            "SELECT complete FROM native_catalog_releases WHERE revision=%s",
            (revision,),
        ).fetchone()
        if found:
            if found[0] is not True:
                raise ValueError("Existing NPC root release is incomplete")
            return dict(revision=revision, activated=False, already_staged=True)
        connection.execute(
            "INSERT INTO native_catalog_releases(revision,document_count,source_bytes) VALUES(%s,%s,%s)",
            (revision, len(manifest), sum(n for _, _, n in manifest)),
        )
        connection.execute(
            "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) SELECT %s,path,raw,sha256,source_bytes,record_count FROM native_catalog_documents WHERE revision=%s AND path<>%s",
            (revision, active, CATALOG_PATH),
        )
        connection.execute(
            "INSERT INTO native_catalog_records(revision,path,collection,record_key,payload) SELECT %s,path,collection,record_key,payload FROM native_catalog_records WHERE revision=%s AND path<>%s",
            (revision, active, CATALOG_PATH),
        )
        records = list(catalog_records(CATALOG_PATH, merged))
        connection.execute(
            "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) VALUES(%s,%s,%s,%s,%s,%s)",
            (revision, CATALOG_PATH, raw, checksum, len(raw), len(records)),
        )
        with connection.cursor().copy(
            "COPY native_catalog_records(revision,path,collection,record_key,payload) FROM STDIN"
        ) as copy:
            for collection, key, payload in records:
                copy.write_row(
                    (revision, CATALOG_PATH, collection, key, Jsonb(payload))
                )
        actual = connection.execute(
            "SELECT path,sha256,source_bytes FROM native_catalog_documents WHERE revision=%s ORDER BY path",
            (revision,),
        ).fetchall()
        if actual != manifest:
            raise ValueError("Staged NPC root manifest mismatch")
        connection.execute(
            "UPDATE native_catalog_releases SET complete=true,completed_at=now() WHERE revision=%s",
            (revision,),
        )
        return dict(
            revision=revision,
            base_revision=active,
            activated=False,
            documents=len(manifest),
            npc_roots=len(exported["roots"]),
            complete_roots=len(merged["roots"]),
            changed_documents=[CATALOG_PATH],
            metadata_sha256=checksum,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exported", type=Path)
    parser.add_argument("domain", type=Path)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    args = parser.parse_args()
    domain = json.loads(args.domain.read_bytes())
    domain["export_sha256"] = hashlib.sha256(args.exported.read_bytes()).hexdigest()
    domain["exporter_sha256"] = hashlib.sha256(
        Path("sniffer/java/ExportNativeCastingRoots.java").read_bytes()
    ).hexdigest()
    with psycopg.connect(
        args.dsn, password=args.password_file.read_text().strip()
    ) as connection:
        print(
            json.dumps(
                stage(connection, json.loads(args.exported.read_bytes()), domain),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
