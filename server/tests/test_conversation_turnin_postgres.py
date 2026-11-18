"""Real inventory and achievement transaction for the School80 item basket."""
import gzip
import json
from pathlib import Path

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import dungeon_criteria, npc_dialogue
from wakfu_server.achievements import conversation, conversation_turnin, storage


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "server/tests/fixtures/school80_basket_native.json"
NATIVE_DIALOGUE = ROOT / "database/protocol/npc-dialogues.json.gz"


class ConversationTurnInPostgresTests(PostgresCase):
    def test_school80_basket_debits_both_items_once_and_missing_second_item_rolls_back(
        self,
    ):
        source = json.loads(SOURCE.read_text())
        self.assertEqual(source["schema"], "school80-native-basket-fixture-v1")
        definition = source["definition"]
        payment = source["payment"]
        self.assertEqual(definition["d"], 2785)
        self.assertEqual(
            payment["items"],
            [
                {"reference": 21054, "quantity": 5},
                {"reference": 13180, "quantity": 30},
            ],
        )
        node_id, choice_id = payment["node_id"], payment["choice_id"]
        catalog = json.loads(gzip.decompress(NATIVE_DIALOGUE.read_bytes()))
        nodes = {row["id"]: row for row in catalog["nodes"]}
        native_choice = next(
            row for row in nodes[node_id]["choices"] if row["id"] == choice_id
        )
        self.assertEqual(native_choice["criteria"], payment["criterion"])
        actor_id, reference_id, action_id = -2251799935991201, 3275, 596
        placement = dict(
            actor_id=actor_id,
            reference_id=reference_id,
            map_id=1019,
            instance_id=0,
            x=60,
            y=-2,
            z=0,
            direction=0,
            dialogue_root=node_id,
            action_ids=[action_id],
            interaction_range=4,
            enabled=True,
            provenance="test: native Thomas turn-in fixture",
        )
        binding = conversation.QualifiedConversation(
            quest_id=2785,
            objective_id=5623,
            reference_id=reference_id,
            action_id=action_id,
            node_id=node_id,
            choice_id=choice_id,
            placement_sha256=conversation.placement_signature(placement),
            native_definition_sha256=conversation._digest(definition),
        )

        def setup_character(character, *, include_second):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=1019,instance_id=0,x=60,y=-2,z=0 WHERE id=%s",
                    (character["id"],),
                )
                bag = db.execute(
                    "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0 ORDER BY uid LIMIT 1",
                    (character["id"],),
                ).fetchone()
                self.assertIsNotNone(bag)
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "VALUES(%s,21054,5,%s,20)",
                    (character["id"], bag["uid"]),
                )
                if include_second:
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,13180,30,%s,21)",
                        (character["id"], bag["uid"]),
                    )
                state = storage.load_locked(db, character["id"])
                state.update(
                    running=[2785], completed=[2783], objectives=[5621], tracking=[2785]
                )
                storage.store(db, character["id"], state)

        account = self.store.register(
            "school80-basket-success", "isolated-test-password"
        )["id"]
        character = self.store.create_character(account, "School Basket")
        setup_character(character, include_second=True)

        # Use the actual native node and its offered choice. Authority checks the
        # real objective flags and carried item quantities before settlement.
        from wakfu_server.dungeon_achievement_authority import (
            queries_from_state as authority,
        )

        def offered_session(character_id, db=None, owner_account=account):
            if db is None:
                with self.store.connection() as current_db:
                    current = self.store.character(
                        owner_account, character_id, current_db
                    )
                    state = storage.load_locked(current_db, character_id)
            else:
                current = self.store.character(owner_account, character_id, db)
                state = storage.load_locked(db, character_id)
            session = npc_dialogue.DialogueSession(
                nodes=nodes,
                graph={(node_id, choice_id): None},
                authorize_node=lambda node: not node.get("criteria"),
                authorize_choice=lambda choice: dungeon_criteria.evaluate(
                    self.store,
                    choice["criteria"],
                    character=current,
                    queries=authority(state),
                ),
            )
            session.quest_nearby = lambda _character, _row: True
            session.open(
                node_id,
                actor_id,
                lambda speaker, node: (speaker, node) == (actor_id, node_id),
            )
            self.assertTrue(session.authorize_choice(native_choice))
            return current, session

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO world_dialogue_npcs "
                "(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,interaction_range,enabled,provenance) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s)",
                (
                    actor_id,
                    reference_id,
                    *[
                        placement[key]
                        for key in (
                            "map_id",
                            "instance_id",
                            "x",
                            "y",
                            "z",
                            "direction",
                            "dialogue_root",
                        )
                    ],
                    Jsonb([action_id]),
                    4,
                    placement["provenance"],
                ),
            )
            current, session = offered_session(character["id"], db)
            result = conversation_turnin.settle(
                db,
                self.store,
                current,
                session,
                binding,
                definition,
                tuple(
                    conversation_turnin.TurnInRequirement(
                        row["reference"], row["quantity"]
                    )
                    for row in payment["items"]
                ),
                node_id=node_id,
                choice_id=choice_id,
            )
            self.assertTrue(result["applied"])
            self.assertIn(5623, storage.load_locked(db, character["id"])["objectives"])
            event = db.execute(
                "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (character["id"], "native-quest-delivery:2785:5623"),
            ).fetchone()
            self.assertEqual(
                event["payload"]["items"],
                [
                    {"item_reference": row["reference"], "quantity": row["quantity"]}
                    for row in payment["items"]
                ],
            )
        with self.store.connection() as db:
            remaining = list(
                db.execute(
                    "SELECT reference,quantity FROM inventory_items WHERE character_id=%s AND reference IN (21054,13180)",
                    (character["id"],),
                )
            )
            self.assertEqual(remaining, [])
            current = self.store.character(account, character["id"], db)
            replay = conversation_turnin.settle(
                db,
                self.store,
                current,
                session,
                binding,
                definition,
                tuple(
                    conversation_turnin.TurnInRequirement(
                        row["reference"], row["quantity"]
                    )
                    for row in payment["items"]
                ),
                node_id=node_id,
                choice_id=choice_id,
            )
            self.assertFalse(replay["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (character["id"], "native-quest-delivery:2785:5623"),
                ).fetchone()["n"],
                1,
            )

        rollback_account = self.store.register(
            "school80-basket-rollback", "isolated-test-password"
        )["id"]
        rollback_character = self.store.create_character(
            rollback_account, "Basket Rollback"
        )
        setup_character(rollback_character, include_second=True)
        _rollback_current, rollback_session = offered_session(
            rollback_character["id"], owner_account=rollback_account
        )
        # The selected choice was genuinely offered while both native stacks
        # existed. The second stack disappears before settlement, so the first
        # sequential debit must roll back with the failed second payment.
        rollback_session.authorize_choice = lambda choice: choice["id"] == choice_id
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s AND reference=13180",
                (rollback_character["id"],),
            )
        with self.assertRaisesRegex(ValueError, "needs 30 of entrance item 13180"):
            with self.store.connection() as db:
                current = self.store.character(
                    rollback_account, rollback_character["id"], db
                )
                conversation_turnin.settle(
                    db,
                    self.store,
                    current,
                    rollback_session,
                    binding,
                    definition,
                    tuple(
                        conversation_turnin.TurnInRequirement(
                            row["reference"], row["quantity"]
                        )
                        for row in payment["items"]
                    ),
                    node_id=node_id,
                    choice_id=choice_id,
                )
        with self.store.connection() as db:
            quantities = list(
                db.execute(
                    "SELECT reference,quantity FROM inventory_items WHERE character_id=%s AND reference IN (21054,13180) ORDER BY reference",
                    (rollback_character["id"],),
                )
            )
            self.assertEqual(quantities, [{"reference": 21054, "quantity": 5}])
            self.assertEqual(
                storage.load_locked(db, rollback_character["id"])["objectives"], [5621]
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (rollback_character["id"], "native-quest-delivery:2785:5623"),
                ).fetchone()["n"],
                0,
            )
