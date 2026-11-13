"""One-time local correction for observed quest XP underpayments."""
import os
from wakfu_server.store import Store
from wakfu_server.achievements import storage
from wakfu_server.achievements.service import _owner


def reconcile(store):
    with store.connection() as db:
        owner = db.execute(
            "SELECT account_id FROM characters WHERE id=%s AND name=%s AND deleted_at IS NULL",
            (16, "Prueba Sacro"),
        ).fetchone()
        if owner is None:
            raise ValueError("Expected local character missing")
        character = {"id": 16, "account_id": owner["account_id"]}
        _owner(db, character)
        policy = db.execute(
            "SELECT v.version,v.xp_rate_bp,v.created_at FROM combat_reward_policy_active a JOIN combat_reward_policy_versions v USING(version) WHERE a.singleton FOR SHARE OF a,v"
        ).fetchone()
        if policy is None or policy["version"] != 8 or policy["xp_rate_bp"] != 100000:
            raise ValueError("Local XP policy no longer matches the observed 10x rate")
        total = 0
        for identity, reward_id in ((1197, 2004), (1217, 2069), (1220, 2015)):
            receipt = db.execute(
                "SELECT payload,delivered_at FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s FOR UPDATE",
                (16, identity, "once", str(reward_id)),
            ).fetchone()
            if (
                receipt is None
                or receipt["delivered_at"] is None
                or receipt["delivered_at"] < policy["created_at"]
                or receipt["payload"].get("aeV") != 6
                or receipt["payload"].get("ckl") != [445000]
            ):
                raise ValueError("Expected delivered mission reward does not match")
            fact = {
                "achievement_id": identity,
                "reward_id": reward_id,
                "base_xp": 445000,
                "rate_bp": 100000,
                "difference_xp": 4005000,
                "policy_version": 8,
            }
            if storage.record_event(
                db, 16, f"local-flat-xp-correction-v1:{identity}:{reward_id}", fact
            ):
                total += 4005000
        if total:
            from wakfu_server.progression import XP_BY_LEVEL

            row = db.execute(
                "SELECT c.level,p.xp FROM characters c JOIN character_progression p ON p.character_id=c.id WHERE c.id=%s FOR UPDATE OF c,p",
                (16,),
            ).fetchone()
            new_xp = row["xp"] + total
            new_level = max(
                row["level"],
                max(
                    level
                    for level, threshold in XP_BY_LEVEL.items()
                    if threshold <= new_xp
                ),
            )
            if new_level != row["level"] or new_xp >= 2**63:
                raise ValueError(
                    "Correction crosses a level or exceeds signed64; use normal reward service"
                )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (new_xp, 16),
            )
        return total


if __name__ == "__main__":
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        print("XP added:", reconcile(store))
    finally:
        store.close()
