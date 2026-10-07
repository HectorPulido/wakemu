"""Batched durable clocks shared by active-zone creature processes."""


def observe(
    store,
    map_id,
    instance_id,
    *,
    present,
    generation,
    now_ms,
    excluded_ids=(),
    table,
    eligible_refs,
    policy_provider,
):
    """Caller observes each tracked zone even when absent, under harvest/group locks.

    This produces one pending cycle, not a batch of catch-up attempts. Existing
    clocks retain their interval when policy changes; new clocks read the policy.
    """
    if table not in ("monster_maturation_timers", "monster_reproduction_timers"):
        raise ValueError("Invalid active monster clock table")
    if (
        type(present) is not bool
        or type(now_ms) is not int
        or now_ms < 0
        or type(generation) is not str
        or not generation
    ):
        raise ValueError("Invalid monster maturation observation")
    configuration = policy_provider(store) if present else None
    with store.connection() as db:
        if not present:
            db.execute(
                f"UPDATE {table} SET last_active_ms=NULL "
                "WHERE map_id=%s AND instance_id=%s AND last_active_ms IS NOT NULL",
                (map_id, instance_id),
            )
            return []
        groups = db.execute(
            "SELECT group_id,members,status FROM combat_groups "
            "WHERE map_id=%s AND instance_id=%s FOR UPDATE",
            (map_id, instance_id),
        ).fetchall()
        from psycopg.types.json import Jsonb

        roster = [(group, member) for group in groups for member in group["members"]]
        terminal_ids = [
            member["id"] for _, member in roster if member["ref"] not in eligible_refs
        ]
        if terminal_ids:
            db.execute(
                f"DELETE FROM {table} WHERE map_id=%s "
                "AND instance_id=%s AND monster_id=ANY(%s)",
                (map_id, instance_id, terminal_ids),
            )
        growable = [
            (group, member)
            for group, member in roster
            if member["ref"] in eligible_refs
        ]
        if not growable:
            return []
        db.execute(
            f"INSERT INTO {table}"
            "(map_id,instance_id,monster_id,reference,remaining_ms) "
            "SELECT %s,%s,x.monster_id,x.reference,%s FROM "
            "jsonb_to_recordset(%s) AS x(monster_id bigint,reference integer) "
            "ON CONFLICT DO NOTHING",
            (
                map_id,
                instance_id,
                configuration["interval_ms"],
                Jsonb(
                    [dict(monster_id=m["id"], reference=m["ref"]) for _, m in growable]
                ),
            ),
        )
        timers = {
            row["monster_id"]: row
            for row in db.execute(
                f"SELECT * FROM {table} WHERE map_id=%s "
                "AND instance_id=%s ORDER BY monster_id FOR UPDATE",
                (map_id, instance_id),
            )
        }
        updates, due = [], []
        for group, member in growable:
            row = timers[member["id"]]
            update = dict(
                monster_id=member["id"],
                reference=row["reference"],
                remaining_ms=row["remaining_ms"],
                last_active_ms=row["last_active_ms"],
                observer_generation=row["observer_generation"],
                due=row["due"],
                cycle=row["cycle"],
            )
            if row["reference"] != member["ref"]:
                update.update(
                    reference=member["ref"],
                    remaining_ms=configuration["interval_ms"],
                    last_active_ms=None,
                    observer_generation=None,
                    due=False,
                )
            elif group["status"] != "available" or member["id"] in excluded_ids:
                update["last_active_ms"] = None
            else:
                elapsed = (
                    max(0, now_ms - row["last_active_ms"])
                    if row["last_active_ms"] is not None
                    and row["observer_generation"] == generation
                    else 0
                )
                remaining = max(0, row["remaining_ms"] - elapsed)
                newly_due = not row["due"] and remaining == 0
                update.update(
                    remaining_ms=remaining,
                    last_active_ms=now_ms,
                    observer_generation=generation,
                    due=row["due"] or newly_due,
                    cycle=row["cycle"] + int(newly_due),
                )
                if newly_due:
                    due.append(
                        dict(
                            map_id=map_id,
                            instance_id=instance_id,
                            group_id=group["group_id"],
                            monster_id=member["id"],
                            reference=member["ref"],
                            cycle=update["cycle"],
                        )
                    )
            updates.append(update)
        db.execute(
            f"UPDATE {table} t SET reference=x.reference,"
            "remaining_ms=x.remaining_ms,last_active_ms=x.last_active_ms,"
            "observer_generation=x.observer_generation,due=x.due,cycle=x.cycle "
            "FROM jsonb_to_recordset(%s) AS x(monster_id bigint,reference integer,"
            "remaining_ms bigint,last_active_ms bigint,observer_generation text,"
            "due boolean,cycle bigint) WHERE t.map_id=%s AND t.instance_id=%s "
            "AND t.monster_id=x.monster_id",
            (Jsonb(updates), map_id, instance_id),
        )
        return due
