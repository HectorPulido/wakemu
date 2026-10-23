"""Five original dungeon-derived daily targets reuse selected owned settlement."""
from datetime import datetime, timezone
import struct
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb
from wakfu_server.achievements import service, storage
from wakfu_server.items import quest_inventory
from wakfu_server.objectives import environmental_daily_selection as selection
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.world import World


class DailyHunterOriginalDungeonDeltaTests(unittest.TestCase):
    def test_five_original_sources_and_selected_sylargh_final_room_reward_once(self):
        from test_recurring_hunter_backend import RecurringHunterBackendTests

        fixture = RecurringHunterBackendTests(
            methodName="test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, owner = fixture.store, fixture.owner
        character_id = fixture.character["id"]
        expected = {
            4194: (111, 2354, 21005, 5308160, [7861, 7862]),
            4212: (156, 4217, 21008, 23442740, [7899, 7900]),
            5117: (216, 5400, 29023, 175561350, [9633, 9634]),
            5397: (231, 5638, 32303, 288038370, [10083, 10084]),
            5398: (231, 5644, 32303, 288038370, [10085, 10086]),
        }
        with store.connection() as db:
            for definition, (minimum, boss, item, xp, reward_order) in expected.items():
                source, contract, rewards = recurring._load(db, definition)
                authority = source["daily_target_authority"]
                self.assertEqual(
                    (
                        contract.minimum_level,
                        contract.period_ms,
                        contract.required_distinct,
                        contract.boss_references,
                    ),
                    (minimum, 86400000, 1, (boss,)),
                )
                self.assertEqual(
                    source["interpretation_policy"], recurring.DAILY_POLICY
                )
                self.assertEqual(authority["native_reward_order"], reward_order)
                self.assertEqual(
                    [
                        (
                            r["reward_id"],
                            r["native_type"],
                            r["reference"],
                            r["amount"],
                            r["native_flag"],
                        )
                        for r in rewards
                    ],
                    [
                        (reward_order[0], 5, item, 20, False),
                        (reward_order[1], 6, None, xp, False),
                    ],
                )
            source, contract, _ = recurring._load(db, 4194)
            authority = source["daily_target_authority"]
            self.assertEqual(
                (
                    authority["boss_reference"],
                    authority["dungeon_definition_id"],
                    authority["final_room_order"],
                    authority["category_id"],
                ),
                (2354, 10, 4, 695),
            )
            active = db.execute(
                "SELECT * FROM recurring_hunter_daily_active WHERE singleton"
            ).fetchone()
            self.assertFalse(active["enabled"])
            members = [
                r["definition_id"]
                for r in db.execute(
                    "SELECT definition_id FROM recurring_hunter_daily_members "
                    "WHERE pool_version=%s AND category_id=695 ORDER BY definition_id,version",
                    (active["pool_version"],),
                )
            ]
            day = recurring._now(db) // selection.DAY_MS
            day += (members.index(4194) - day) % len(members)
            clock = [day * selection.DAY_MS + 1000]
            db.execute("UPDATE characters SET level=111 WHERE id=%s", (character_id,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[111], character_id),
            )
        store.clock = lambda: clock[0] / 1000
        generation = store.begin_session(
            owner["account"], previous_generation=owner["generation"]
        )
        store.select_character(owner["account"], generation, character_id)
        owner["generation"] = generation
        character = store.character(owner["account"], character_id)
        fixture.character = character
        world = World(lambda _: b"", lambda _: b"", lambda *_: True)
        world.join(generation, object(), character)
        self.enterContext(patch.object(presence, "_world", world))
        self.enterContext(
            patch.object(recurring, "_now", side_effect=lambda _: clock[0])
        )
        with store.connection() as db:
            self.assertEqual(selection.select_for_character(db, store, character), ())
            db.execute("UPDATE recurring_hunter_daily_active SET enabled=true")
            chosen = next(
                r
                for r in selection.select_for_character(db, store, character)
                if r["category_id"] == 695
            )
            self.assertEqual(
                (chosen["definition_id"], chosen["version"], chosen["eligible"]),
                (4194, 1, True),
            )
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                "(4194,1,'npc_dialogue',777,888,'isolated selected-offer fixture; no NPC activation claim')"
            )
            receipt_key = "daily:sylargh-original-delta"
            storage.record_event(
                db,
                character_id,
                receipt_key,
                dict(
                    kind="native_recurring_acceptance",
                    definition_id=4194,
                    real_level=111,
                    source_kind="npc_dialogue",
                    source_reference=777,
                    action_id=888,
                ),
            )
            stamp = datetime.fromtimestamp(clock[0] / 1000, timezone.utc)
            db.execute(
                "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                (stamp, character_id, receipt_key),
            )
            self.assertTrue(
                recurring.accept_from_receipt(
                    db, store, character, 4194, receipt_key=receipt_key
                )["applied"]
            )
            self.assertFalse(
                recurring.accept_from_receipt(
                    db, store, character, 4194, receipt_key=receipt_key
                )["applied"]
            )
            self.assertIn(4194, storage.load_locked(db, character_id)["running"])
            self.assertIn(21005, quest_inventory.REFERENCES)
            token_before = quest_inventory.quantity(character, [21005])
            before_xp = character["xp"]
            original_event = service._event

            def fight(definition):
                def provision(connection, actor, resolved, originals):
                    instance = connection.execute(
                        "SELECT instance_id FROM dungeon_room_encounters WHERE fight_id=%s",
                        (resolved.id,),
                    ).fetchone()["instance_id"]
                    connection.execute(
                        "UPDATE dungeon_instances SET definition_id=%s WHERE instance_id=%s",
                        (definition, instance),
                    )
                    connection.execute(
                        "UPDATE dungeon_room_encounters SET room_order=4 WHERE fight_id=%s",
                        (resolved.id,),
                    )
                    connection.execute(
                        "UPDATE dungeon_room_runs SET rooms=%s WHERE instance_id=%s",
                        (
                            Jsonb(
                                [
                                    dict(
                                        order=4,
                                        monsters=[dict(ref_id=2354, role="boss")],
                                    )
                                ]
                            ),
                            instance,
                        ),
                    )
                    return original_event(connection, actor, resolved, originals)

                with patch.object(service, "_event", side_effect=provision):
                    resolved, event = fixture.fight(db, [2354])
                db.execute(
                    "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                    (stamp, character_id, "fight:" + str(resolved.id)),
                )
                return resolved, event

            wrong, wrong_event = fight(1)
            self.assertEqual(wrong_event["completed_dungeon_id"], 1)
            rejected = recurring.settle_combat(db, store, character, wrong, wrong_event)
            self.assertEqual((rejected["credited"], rejected["completed"]), ([], []))
            self.assertEqual(
                store.character(owner["account"], character_id, db)["xp"], before_xp
            )
            actual, event = fight(10)
            self.assertEqual(event["completed_dungeon_id"], 10)
            with self.assertRaises(ValueError):
                recurring.settle_combat(
                    db, store, character, actual, dict(event, completed_dungeon_id=1)
                )
            completed = recurring.settle_combat(db, store, character, actual, event)
            self.assertEqual(completed["completed"], [4194])
            self.assertEqual(
                [
                    (r["definition_id"], r["boss_reference"])
                    for r in completed["credited"]
                ],
                [(4194, 2354)],
            )
            notices = [
                struct.unpack(">BBqqhB", body)
                for opcode, body in completed["packets"]
                if opcode == 13613
            ]
            self.assertEqual([(r[2], r[3]) for r in notices], [(character_id, 5308160)])
            current = store.character(owner["account"], character_id, db)
            self.assertEqual(current["xp"], before_xp + 5308160)
            self.assertEqual(
                quest_inventory.quantity(current, [21005]), token_before + 20
            )
            self.assertIn(4194, storage.load_locked(db, character_id)["completed"])
            self.assertEqual(storage.pending_rewards(db, character_id), [])
            replay = recurring.settle_combat(db, store, current, actual, event)
            self.assertEqual((replay["credited"], replay["completed"]), ([], []))
            self.assertEqual(service.drain_rewards(db, store, current), [])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=4194 AND delivered_at IS NOT NULL",
                    (character_id,),
                ).fetchone()["n"],
                2,
            )
        generation = store.begin_session(
            owner["account"], previous_generation=generation
        )
        store.select_character(owner["account"], generation, character_id)
        owner["generation"] = generation
        with store.connection() as db:
            current = store.character(owner["account"], character_id, db)
            self.assertEqual(current["xp"], before_xp + 5308160)
            self.assertEqual(
                quest_inventory.quantity(current, [21005]), token_before + 20
            )
            self.assertEqual(storage.pending_rewards(db, character_id), [])
