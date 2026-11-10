"""Retire unused derived publications while protecting live reader sessions."""

MAINTENANCE_LOCK = (
    "hashtextextended(current_database()||':'||current_schema()||"
    "':compiled_catalog_maintenance',0)"
)


def retained_publications(db, *, keep=(), retain=2):
    if type(retain) is not int or retain < 1:
        raise ValueError("At least one complete publication must be retained")
    rows = db.execute(
        "SELECT generation,complete FROM native_compiled_catalog_releases "
        "ORDER BY created_at DESC,generation DESC"
    ).fetchall()
    known = {row["generation"] for row in rows}
    keep = set(keep)
    if keep - known:
        raise ValueError("Explicitly retained compiled generation does not exist")
    keep.update([row["generation"] for row in rows if row["complete"]][:retain])
    remove = []
    for row in rows:
        generation = row["generation"]
        if generation in keep:
            continue
        locked = db.execute(
            "SELECT pg_try_advisory_xact_lock(hashtextextended("
            "current_database()||':'||current_schema()||':compiled_generation:'||%s,0)) AS acquired",
            (generation,),
        ).fetchone()["acquired"]
        if locked:
            remove.append(generation)
        else:
            keep.add(generation)
    return sorted(keep), remove


def delete_publications(db, generations):
    db.execute("SET LOCAL wakemu.compiled_catalog_maintenance='on'")
    db.execute(
        "DELETE FROM native_compiled_catalog_collections WHERE generation=ANY(%s)",
        (generations,),
    )
    db.execute(
        "DELETE FROM native_compiled_catalog_releases WHERE generation=ANY(%s)",
        (generations,),
    )
    unused = db.execute(
        "SELECT content_id FROM native_compiled_collection_contents c "
        "WHERE NOT EXISTS(SELECT 1 FROM native_compiled_catalog_collections r "
        "WHERE r.content_id=c.content_id)"
    ).fetchall()
    ids = [row["content_id"] for row in unused]
    db.execute(
        "DELETE FROM native_compiled_content_records WHERE content_id=ANY(%s)", (ids,)
    )
    db.execute(
        "DELETE FROM native_compiled_collection_contents WHERE content_id=ANY(%s)",
        (ids,),
    )
    return len(ids)


def prune_compiled_publications(database, *, keep=(), retain=2):
    with database.connection() as db:
        db.execute("SELECT pg_advisory_xact_lock(" + MAINTENANCE_LOCK + ")")
        kind = db.execute(
            "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_compiled_catalog_records')"
        ).fetchone()["relkind"]
        if kind != "v":
            raise RuntimeError("Compact legacy compiled catalog storage before pruning")
        retained, removed = retained_publications(db, keep=keep, retain=retain)
        unused = delete_publications(db, removed)
        return dict(retained=retained, removed=removed, removed_contents=unused)
