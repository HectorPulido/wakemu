"""Portable authenticated source inventories without historical payload copies."""


def validated_retired_inventories(inventories, *, payload_revisions=()):
    from wakfu_server.native_catalog_compatibility import _inventory

    if type(inventories) is not list:
        raise ValueError("Invalid retired native catalog inventories")
    seen = set(payload_revisions)
    result = []
    for inventory in inventories:
        if type(inventory) is not dict:
            raise ValueError("Invalid retired native catalog inventory")
        revision = inventory.get("revision")
        if revision in seen:
            raise ValueError("Duplicate or payload-overlapping retired native revision")
        _inventory(inventory, revision)
        seen.add(revision)
        # Inventories are public source metadata; never carry arbitrary columns
        # or raw document bodies into an installation pack.
        value = {
            key: inventory[key]
            for key in ("revision", "document_count", "source_bytes", "complete")
        }
        for key in ("identity_scheme", "manifest_sha256"):
            if key in inventory:
                value[key] = inventory[key]
        value["documents"] = [
            {key: row[key] for key in ("path", "sha256", "source_bytes")}
            for row in inventory["documents"]
        ]
        result.append(value)
    return sorted(result, key=lambda row: row["revision"])


def export_retired_inventories(db, *, payload_revisions=()):
    """Carry source seals for every complete release omitted from the payload pack."""
    payload_revisions = set(payload_revisions)
    inventories = []
    for row in db.execute(
        "SELECT r.revision,r.document_count,r.source_bytes,r.complete,a.inventory "
        "FROM native_catalog_releases r "
        "LEFT JOIN native_catalog_retired_inventories a USING(revision) "
        "WHERE r.complete ORDER BY r.revision"
    ):
        if row["revision"] in payload_revisions:
            continue
        inventory = row["inventory"]
        if inventory is None:
            inventory = {
                key: row[key]
                for key in ("revision", "document_count", "source_bytes", "complete")
            }
            inventory["documents"] = [
                dict(document)
                for document in db.execute(
                    "SELECT path,sha256,source_bytes FROM native_catalog_documents "
                    'WHERE revision=%s ORDER BY path COLLATE "C"',
                    (row["revision"],),
                )
            ]
        if any(
            inventory.get(key) != row[key]
            for key in ("revision", "document_count", "source_bytes", "complete")
        ):
            raise ValueError("Retired native inventory differs from its release header")
        inventories.append(inventory)
    return validated_retired_inventories(
        inventories, payload_revisions=payload_revisions
    )


def restore_retired_inventories(database, inventories, *, payload_revisions=()):
    from psycopg.types.json import Jsonb

    inventories = validated_retired_inventories(
        inventories, payload_revisions=payload_revisions
    )
    if not inventories:
        return 0
    with database.connection() as db:
        db.execute(
            "SELECT pg_advisory_xact_lock_shared(hashtextextended("
            "current_database()||':'||current_schema()||':native_catalog_maintenance',0))"
        )
        for inventory in inventories:
            revision = inventory["revision"]
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete,created_at,completed_at) "
                "VALUES(%s,%s,%s,true,to_timestamp(0),to_timestamp(0)) "
                "ON CONFLICT(revision) DO NOTHING",
                (revision, inventory["document_count"], inventory["source_bytes"]),
            )
            header = db.execute(
                "SELECT revision,document_count,source_bytes,complete "
                "FROM native_catalog_releases WHERE revision=%s FOR UPDATE",
                (revision,),
            ).fetchone()
            if any(
                header[key] != inventory[key]
                for key in ("revision", "document_count", "source_bytes", "complete")
            ):
                raise ValueError(
                    "Retired native inventory conflicts with existing release"
                )
            if (
                db.execute(
                    "SELECT 1 FROM native_catalog_documents WHERE revision=%s LIMIT 1",
                    (revision,),
                ).fetchone()
                is not None
            ):
                # A retained full source is stronger authority than an archive.
                continue
            existing = db.execute(
                "SELECT inventory FROM native_catalog_retired_inventories WHERE revision=%s",
                (revision,),
            ).fetchone()
            if existing is not None:
                prior = validated_retired_inventories([existing["inventory"]])[0]
                if prior != inventory:
                    raise ValueError(
                        "Retired native inventory conflicts with existing archive"
                    )
                continue
            db.execute(
                "INSERT INTO native_catalog_retired_inventories(revision,inventory) VALUES(%s,%s)",
                (revision, Jsonb(inventory)),
            )
    return len(inventories)
