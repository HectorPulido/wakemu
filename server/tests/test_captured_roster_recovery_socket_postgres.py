"""Exact selector socket stays usable after malformed historical capture state.

World bootstrap serialization remains the existing explicit fixture boundary;
this verifies server selection, durable capture recovery and ping continuity.
"""
import struct
from psycopg.types.json import Jsonb

import test_character_selection_socket_postgres as socket_fixture
from wakfu_server.captured_roster import CapturedCreature, OwnedCapturedRoster
from wakfu_server.captured_roster_store import save


class CapturedRecoverySocketTests(socket_fixture.CharacterSelectionSocketPostgresTests):
    def test_foreign_historical_actor_cannot_disconnect_or_replace_owned_captures(self):
        self.actor = self.store.create_character(
            self.account, "Recovered Osamodas", breed=2
        )
        self.namespace["reconcile_closed_rift_login"] = lambda *args, **kwargs: None
        slots = [None] * 10
        slots[3] = CapturedCreature(3, 4, "Current renamed capture")
        current = OwnedCapturedRoster(self.actor["id"], tuple(slots), (False,) * 10, 3)
        with self.store.connection() as db:
            save(db, self.actor, current)
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('aborted') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (fight_id, self.actor["id"], self.account, self.generation),
            )
            db.execute(
                "INSERT INTO fight_checkpoints VALUES(%s,%s,%s,1,'aborted',%s,CURRENT_TIMESTAMP)",
                (
                    fight_id,
                    self.account,
                    self.generation,
                    Jsonb(
                        {
                            "actors": {
                                str(self.actor["id"]): {
                                    "id": self.actor["id"],
                                    "controlled": True,
                                    "owner_id": self.account + 99,
                                }
                            },
                            "native_captured_rosters": {
                                str(self.actor["id"]): "invalid historical component"
                            },
                        }
                    ),
                ),
            )
            before = self.store.character(self.account, self.actor["id"], db)
        self.first_selection()
        after = self.store.character(self.account, self.actor["id"])
        roster = OwnedCapturedRoster.from_record(
            after["captured_roster"], expected_owner_id=self.actor["id"]
        )
        self.assertEqual(roster.available, (True,) * 10)
        self.assertEqual(roster.slots, current.slots)
        self.assertEqual(roster.selected_slot, current.selected_slot)
        for key in ("hp_damage", "health_dead", "xp", "inventory_items"):
            self.assertEqual(after[key], before[key], key)
        self.send(33, b"capture-recovered")
        self.assertEqual(self.receive(), (23, b"\x01capture-recovered"))
        self.assertEqual(self.receive(), (309, struct.pack(">I", 12345)))
        self.assertTrue(self.failures.empty())


# Reuse the exact socket harness without rerunning unrelated selection cases.
for _name in dir(socket_fixture.CharacterSelectionSocketPostgresTests):
    if _name.startswith("test_"):
        setattr(CapturedRecoverySocketTests, _name, None)
