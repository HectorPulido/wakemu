import unittest

from test_dungeon_entry_payment_postgres import (
    DungeonEntryPaymentPostgresTests,
)
from wakfu_server import dungeon_entry_payment
from wakfu_server import player_action_feedback


class EntryFeedbackUnitTests(unittest.TestCase):
    def test_typed_item_feedback_and_legacy_error_fallback(self):
        from wakfu_server.inventory_move import STACKS

        item_name = STACKS[15133]["name"]
        typed = dungeon_entry_payment.InsufficientEntranceItems(
            "Every party member needs an entrance item",
            reference=15133,
            quantity=1,
        )
        text = player_action_feedback.failure_message("transport", typed)
        self.assertIn(item_name, text)
        self.assertIn("1 ×", text)
        self.assertIn("[15133]", text)
        self.assertNotIn(str(typed), text)

        legacy = dungeon_entry_payment.InsufficientEntranceItems("legacy retry reason")
        fallback = player_action_feedback.failure_message("transport", legacy)
        self.assertIn("No se pudo", fallback)
        self.assertIn("Vuelve a abrir el acceso", fallback)
        for args in ((), ("first", "second")):
            error = dungeon_entry_payment.InsufficientEntranceItems(*args)
            self.assertEqual(error.args, args)
            self.assertEqual(str(error), str(ValueError(*args)))
            self.assertIn(
                "No se pudo",
                player_action_feedback.failure_message("transport", error),
            )
        for metadata in (
            {"reference": True, "quantity": 1},
            {"reference": 15133, "quantity": 1.0},
            {"reference": -1, "quantity": 1},
            {"reference": 15133, "quantity": 0},
        ):
            error = dungeon_entry_payment.InsufficientEntranceItems(
                "metadata must stay generic", **metadata
            )
            message = player_action_feedback.failure_message("transport", error)
            self.assertNotIn("[15133]", message)
            self.assertNotIn("×", message)
        generic = ValueError("Every party member needs 1 of entrance item 15133")
        generic_message = player_action_feedback.failure_message("transport", generic)
        self.assertNotIn("[15133]", generic_message)
        self.assertNotIn("×", generic_message)


class RejectedEntranceFeedbackPostgresTests(DungeonEntryPaymentPostgresTests):
    def test_missing_party_key_explains_cost_and_preserves_entry_state(self):
        self.grant(self.ids[0], 1)
        with self.store.connection() as db:
            before_locations = list(
                db.execute(
                    "SELECT id,map_id,instance_id,x,y,z FROM characters "
                    "WHERE id=ANY(%s) ORDER BY id",
                    (list(self.ids),),
                )
            )
            before_party = list(
                db.execute(
                    "SELECT m.party_id,m.character_id,p.leader_id "
                    "FROM player_party_members m JOIN player_parties p ON p.id=m.party_id "
                    "WHERE m.party_id=%s ORDER BY m.character_id",
                    (self.party_id,),
                )
            )
            before_items = list(
                db.execute(
                    "SELECT uid,character_id,reference,quantity,container,slot "
                    "FROM inventory_items WHERE character_id=ANY(%s) ORDER BY uid",
                    (list(self.ids),),
                )
            )
            before_instances = db.execute(
                "SELECT count(*) AS n FROM dungeon_instances"
            ).fetchone()["n"]
            before_members = db.execute(
                "SELECT count(*) AS n FROM dungeon_instance_members"
            ).fetchone()["n"]
            before_outbox = db.execute(
                "SELECT count(*) AS n FROM dungeon_transition_outbox"
            ).fetchone()["n"]

        with self.assertRaises(
            dungeon_entry_payment.InsufficientEntranceItems
        ) as caught:
            self.enter()
        error = caught.exception
        self.assertEqual((error.reference, error.quantity), (15133, 1))
        message = player_action_feedback.failure_message("transport", error)
        self.assertIn("Cada integrante del grupo, incluidos los héroes", message)
        self.assertIn("1 ×", message)
        self.assertIn("[15133]", message)
        self.assertIn("vuelve a usar el acceso", message)

        with self.store.connection() as db:
            self.assertEqual(
                list(
                    db.execute(
                        "SELECT id,map_id,instance_id,x,y,z FROM characters "
                        "WHERE id=ANY(%s) ORDER BY id",
                        (list(self.ids),),
                    )
                ),
                before_locations,
            )
            self.assertEqual(
                list(
                    db.execute(
                        "SELECT m.party_id,m.character_id,p.leader_id "
                        "FROM player_party_members m JOIN player_parties p ON p.id=m.party_id "
                        "WHERE m.party_id=%s ORDER BY m.character_id",
                        (self.party_id,),
                    )
                ),
                before_party,
            )
            self.assertEqual(
                list(
                    db.execute(
                        "SELECT uid,character_id,reference,quantity,container,slot "
                        "FROM inventory_items WHERE character_id=ANY(%s) ORDER BY uid",
                        (list(self.ids),),
                    )
                ),
                before_items,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                before_instances,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instance_members"
                ).fetchone()["n"],
                before_members,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox"
                ).fetchone()["n"],
                before_outbox,
            )
