"""Lease-scoped mount toggles; location/occupation guards come from the world."""
from .mount_inventory import equipped
from psycopg.pq import TransactionStatus


def load(db, character_id):
    row = db.execute(
        "SELECT mounted,last_mount_at,revision FROM character_mount_state "
        "WHERE character_id=%s",
        (character_id,),
    ).fetchone()
    return (
        dict(row)
        if row is not None
        else dict(mounted=False, last_mount_at=None, revision=0)
    )


def reconcile_equipment(db, previous, current):
    """Changing mount units ends riding; cosmetic/stat changes do not revive it."""
    if (
        db.info.transaction_status != TransactionStatus.INTRANS
        or previous["id"] != current["id"]
    ):
        raise ValueError(
            "Mount equipment reconciliation requires its owned transaction"
        )
    if not previous.get("mount_state", {}).get("mounted", False):
        return False
    before, after = equipped(previous), equipped(current)
    if before is not None and after is not None and before["uid"] == after["uid"]:
        return False
    return (
        db.execute(
            "UPDATE character_mount_state SET mounted=false,revision=revision+1 "
            "WHERE character_id=%s AND mounted=true",
            (current["id"],),
        ).rowcount
        == 1
    )


def toggle(
    store,
    account_id,
    generation,
    character_id,
    *,
    mounted,
    in_fight,
    location_allowed,
    occupation_cancelable
):
    """Return native ride result and owned snapshot after commit, or no mutation.

    Callers must validate the request body and authoritative world guards;
    this function independently checks durable combat, ownership and cooldown.
    """
    if any(
        type(value) is not bool
        for value in (mounted, in_fight, location_allowed, occupation_cancelable)
    ):
        raise ValueError("Invalid authoritative mount context")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        state = load(db, character_id)
        if (
            in_fight
            or db.execute(
                "SELECT 1 FROM combat_fights f JOIN combat_fight_participants p "
                "ON p.fight_id=f.id WHERE p.character_id=%s AND p.account_id=%s "
                "AND f.status IN ('placement','active') LIMIT 1",
                (character_id, account_id),
            ).fetchone()
            is not None
        ):
            return 3, character
        policy = {
            row["name"]: row["value"]
            for row in db.execute(
                "SELECT name,value FROM settings WHERE name=ANY(%s)",
                (
                    [
                        "mounts_enabled",
                        "mounts_require_unlock_quest",
                        "mount_toggle_cooldown_ms",
                    ],
                ),
            )
        }
        if (
            type(policy.get("mounts_enabled")) is not bool
            or type(policy.get("mounts_require_unlock_quest")) is not bool
            or type(policy.get("mount_toggle_cooldown_ms")) is not int
            or not 0 <= policy["mount_toggle_cooldown_ms"] <= 300000
        ):
            raise ValueError("Invalid PostgreSQL mount policy")
        if mounted:
            if not policy["mounts_enabled"]:
                return 3, character
            if policy["mounts_require_unlock_quest"]:
                raise ValueError("Mount quest authority is not implemented")
            if character["hp"] <= 0:
                return 2, character
            if not location_allowed:
                return 4, character
            from wakfu_server.swimming import at_position

            try:
                if at_position(character):
                    return 4, character
            except ValueError:
                # Unexported or unverified surfaces are not assumed dry.
                return 4, character
            if not occupation_cancelable:
                return 5, character
            # The world must cancel a durable harvest before granting a ride.
            # Do not trust a caller's context boolean over a live SQL ticket.
            if (
                db.execute(
                    "SELECT 1 FROM resource_harvest_occupations "
                    "WHERE character_id=%s AND expires_at>%s LIMIT 1",
                    (character_id, store.now()),
                ).fetchone()
                is not None
            ):
                return 5, character
            unit = equipped(character)
            if unit is None:
                return 7, character
            mount = unit["mount"]
            if mount["health"] <= 0:
                return 1, character
            if mount["sleep_item_ref"] > 0 and mount["sleep_date"] != 0:
                return 3, character
        if state["mounted"] == mounted:
            return 0, character
        now = store.now()
        if (
            mounted
            and state["last_mount_at"] is not None
            and (now - state["last_mount_at"]).total_seconds() * 1000
            < policy["mount_toggle_cooldown_ms"]
        ):
            return 6, character
        db.execute(
            "INSERT INTO character_mount_state(character_id,mounted,last_mount_at,revision) "
            "VALUES(%s,%s,%s,1) ON CONFLICT(character_id) DO UPDATE SET "
            "mounted=excluded.mounted,last_mount_at=excluded.last_mount_at,"
            "revision=character_mount_state.revision+1",
            (character_id, mounted, now if mounted else state["last_mount_at"]),
        )
        return 0, store.character(account_id, character_id, db)
