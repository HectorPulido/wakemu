"""One owned PostgreSQL lifecycle: interrupted capture, fencing and next login."""
from copy import deepcopy
from dataclasses import replace
import unittest
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.characters.captured_roster_store import save
from wakfu_server.captured_roster_recovery import reconcile_aborted


class CapturedAbortedRecoveryTests(PostgresCase):
    def test_attested_abort_restores_only_availability_and_preserves_newer_state(self):
        from wakfu_server import health_store

        store = self.store
        store.clock = lambda: 1000
        account = store.register("aborted-capture", "local-password")["id"]
        generation = store.begin_session(account)
        owner = store.create_character(account, "Capture Return", breed=2)
        owner = store.select_character(account, generation, owner["id"])
        slots = [None] * 10
        slots[1] = CapturedCreature(1, 4, "Existing Tofu")
        slots[3] = CapturedCreature(3, 1152, "Existing capture")
        used = OwnedCapturedRoster(owner["id"], tuple(slots), (False,) * 10, 1)
        with store.connection() as db:
            save(db, owner, used)
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('aborted') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (fight_id, owner["id"], account, generation),
            )
            state = dict(
                actors={
                    str(owner["id"]): dict(
                        id=owner["id"], controlled=True, owner_id=account
                    )
                },
                native_captured_rosters={str(owner["id"]): used.to_record()},
            )
            db.execute(
                "INSERT INTO fight_checkpoints VALUES(%s,%s,%s,1,'aborted',%s,CURRENT_TIMESTAMP)",
                (fight_id, account, generation, Jsonb(state)),
            )
            original = store.character(account, owner["id"], db)
            # Gameplay initialization must not release a slot from a live book.
            live = health_store.initialize(
                store, account, generation, owner["id"], db=db
            )
            self.assertEqual(live["captured_roster"], used.to_record())
            for status, checkpoint_status in (
                ("active", "aborted"),
                ("aborted", "active"),
                ("finished", "ended"),
            ):
                with self.subTest(
                    status=status, checkpoint=checkpoint_status
                ), db.transaction(force_rollback=True):
                    db.execute(
                        "UPDATE combat_fights SET status=%s WHERE id=%s",
                        (status, fight_id),
                    )
                    db.execute(
                        "UPDATE fight_checkpoints SET status=%s WHERE fight_id=%s",
                        (checkpoint_status, fight_id),
                    )
                    self.assertFalse(reconcile_aborted(db, original))
            with db.transaction(force_rollback=True):
                foreign = deepcopy(state)
                foreign["actors"][str(owner["id"])]["owner_id"] = account + 1
                db.execute(
                    "UPDATE fight_checkpoints SET snapshot=%s WHERE fight_id=%s",
                    (Jsonb(foreign), fight_id),
                )
                with self.assertRaisesRegex(ValueError, "actual controlled owner"):
                    reconcile_aborted(db, original)
            with db.transaction(force_rollback=True):
                new_fight = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                    (new_fight, owner["id"], account, generation),
                )
                self.assertFalse(reconcile_aborted(db, original))
                # An older still-live membership also owns its capture lifetime.
                later_abort = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('aborted') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                    (later_abort, owner["id"], account, generation),
                )
                db.execute(
                    "INSERT INTO fight_checkpoints VALUES(%s,%s,%s,1,'aborted',%s,CURRENT_TIMESTAMP)",
                    (later_abort, account, generation, Jsonb(state)),
                )
                self.assertFalse(reconcile_aborted(db, original))
            with db.transaction(force_rollback=True):
                renamed = list(used.slots)
                renamed[1] = replace(renamed[1], name="Later descriptor edit")
                changed = replace(used, slots=tuple(renamed))
                save(db, owner, changed)
                self.assertFalse(
                    reconcile_aborted(db, store.character(account, owner["id"], db))
                )
            # Keep a user's subsequent selection rather than restoring old slot1.
            selected = replace(used, selected_slot=3)
            save(db, owner, selected)
            before = store.character(account, owner["id"], db)
            with db.transaction(force_rollback=True):
                self.assertTrue(reconcile_aborted(db, before))
            self.assertEqual(
                store.character(account, owner["id"], db)["captured_roster"],
                selected.to_record(),
            )
            returned = health_store.initialize(
                store, account, generation, owner["id"], exploration=True, db=db
            )
            restored = OwnedCapturedRoster.from_record(
                returned["captured_roster"], expected_owner_id=owner["id"]
            )
            self.assertEqual(restored.available, (True,) * 10)
            self.assertEqual(restored.slots, used.slots)
            self.assertEqual(restored.selected_slot, 3)
            revision = db.execute(
                "SELECT revision FROM character_captured_rosters WHERE character_id=%s",
                (owner["id"],),
            ).fetchone()["revision"]
            self.assertFalse(reconcile_aborted(db, returned))
            self.assertEqual(
                db.execute(
                    "SELECT revision FROM character_captured_rosters WHERE character_id=%s",
                    (owner["id"],),
                ).fetchone()["revision"],
                revision,
            )
            self.assertEqual(returned["level"], before["level"])
            self.assertEqual(returned["hp_damage"], before["hp_damage"])


if __name__ == "__main__":
    unittest.main()
