"""Publish current guild refreshes after commit, retaining failed deliveries.

A publisher must load current authority and current selected recipient leases.
Historical native deltas are never reconstructed from this recovery ledger.
Publication is at least once; consumers must tolerate duplicate snapshots.
"""


def drain(store, publisher, *, limit=64):
    """Refresh guilds in event order; acknowledge only successful publications.

    Return the number of acknowledged events. Publisher failures propagate and
    preserve the failing guild's events. No transaction spans network callbacks.
    Concurrent drains can duplicate refreshes but cannot lose later revisions.
    """
    if type(limit) is not int or not 1 <= limit <= 1024:
        raise ValueError("Guild outbox limit must be between 1 and 1024")
    with store.connection() as db:
        events = db.execute(
            "SELECT id,guild_id,revision,payload FROM guild_events "
            "WHERE published_at IS NULL ORDER BY id LIMIT %s",
            (limit,),
        ).fetchall()
    guilds = {}
    for event in events:
        entry = guilds.setdefault(
            event["guild_id"], {"revision": 0, "affected": set(), "ids": []}
        )
        entry["revision"] = max(entry["revision"], event["revision"])
        entry["ids"].append(event["id"])
        payload = event["payload"]
        for key in ("character_id", "target_id"):
            value = payload.get(key)
            if type(value) is int:
                entry["affected"].add(value)
        for value in payload.get("member_ids", []):
            if type(value) is int:
                entry["affected"].add(value)
    acknowledged = 0
    for guild_id, entry in guilds.items():
        publisher(guild_id, entry["revision"], tuple(sorted(entry["affected"])))
        with store.connection() as db:
            # Ack only the bounded batch observed before publication. Events
            # committed during the callback retain their own delivery attempt.
            rows = db.execute(
                "UPDATE guild_events SET published_at=CURRENT_TIMESTAMP "
                "WHERE id=ANY(%s) AND guild_id=%s AND revision<=%s "
                "AND published_at IS NULL RETURNING id",
                (entry["ids"], guild_id, entry["revision"]),
            ).fetchall()
            acknowledged += len(rows)
    return acknowledged
