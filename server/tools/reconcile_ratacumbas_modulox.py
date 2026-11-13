"""Replay one locally recorded eligible Ratacumbas win through normal settlement.

The target is Hector's already accepted quest and durable winning checkpoint.
No fabricated objective, inventory or XP grant is used; all normal settlement
and outbox checks run in the same transaction. Use --apply to commit.
"""
import argparse
import os
from types import SimpleNamespace

from wakfu_server.store import Store
from wakfu_server.objectives import environmental_recurring_storage as recurring


class DryRunRollback(Exception):
    pass


def run(store, *, apply):
    try:
        with store.connection() as db:
            with db.transaction():
                # Serialize against new fights or other changes to this owner.
                db.execute(
                    "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (2,)
                ).fetchone()
                owner = db.execute(
                    "SELECT id FROM characters WHERE id=%s AND account_id=%s AND name=%s AND deleted_at IS NULL FOR UPDATE",
                    (16, 2, "Prueba Sacro"),
                ).fetchone()
                if owner is None:
                    raise ValueError("Expected local owner missing")
                if db.execute(
                    "SELECT 1 FROM combat_fights f JOIN combat_fight_participants p ON p.fight_id=f.id WHERE p.character_id=%s AND f.status NOT IN ('finished','aborted') LIMIT 1",
                    (16,),
                ).fetchone():
                    raise ValueError("Character has an unfinished combat")
                checkpoint = db.execute(
                    "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s AND status=%s",
                    (467, "ended"),
                ).fetchone()
                if checkpoint is None:
                    raise ValueError("Missing terminal fight checkpoint")
                data = checkpoint["snapshot"]
                if (
                    data.get("id") != 467
                    or data.get("phase") != "finished"
                    or data.get("winner") != 0
                ):
                    raise ValueError("Unexpected terminal fight state")
                fields = (
                    "id",
                    "controlled",
                    "owner_id",
                    "team",
                    "hp",
                    "effective_level",
                    "pve_withdrawn",
                )
                actors = {
                    int(k): SimpleNamespace(**{a: v.get(a) for a in fields})
                    for k, v in data["actors"].items()
                }
                fight = SimpleNamespace(
                    id=467,
                    phase="finished",
                    winner=0,
                    actors=actors,
                    native_summon_registrations=data.get(
                        "native_summon_registrations", {}
                    ),
                )
                receipt = db.execute(
                    "SELECT payload FROM character_achievement_events WHERE character_id=16 AND event_key='fight:467'"
                ).fetchone()
                if (
                    receipt is None
                    or receipt["payload"].get("completed_dungeon_id") != 12
                    or actors[16].effective_level != 80
                ):
                    raise ValueError(
                        "Winning source or level is not the expected evidence"
                    )
                policy = db.execute(
                    "SELECT policy_version FROM achievement_scaled_xp_active WHERE singleton FOR UPDATE"
                ).fetchone()
                if (
                    policy is None
                    or policy["policy_version"]
                    != "wakemu.achievement-native17-base-no-subscription-v1"
                ):
                    raise ValueError("Unexpected scaled XP policy")
                db.execute(
                    "UPDATE achievement_scaled_xp_active SET enabled=true WHERE singleton"
                )
                character = store.character(2, 16, db)
                result = recurring.settle_combat(
                    db, store, character, fight, receipt["payload"]
                )
                print(
                    "Completed:",
                    result["completed"],
                    "credited:",
                    result["credited"],
                    "packets:",
                    len(result["packets"]),
                )
                if result["completed"] not in ([], [4100]):
                    raise ValueError("Unexpected settlement scope")
                if not apply:
                    raise DryRunRollback()
    except DryRunRollback:
        print("Dry run rolled back")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        run(store, apply=args.apply)
    finally:
        store.close()


if __name__ == "__main__":
    main()
