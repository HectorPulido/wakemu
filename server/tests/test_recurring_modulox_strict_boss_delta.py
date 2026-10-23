"""Two additional strict boss contracts reuse authenticated final-room settlement."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from psycopg import DatabaseError
from psycopg.types.json import Jsonb
from wakfu_server import builds, dungeon_difficulty, native_catalog
from wakfu_server.achievements import service, storage
from wakfu_server.combat_state import Actor
from wakfu_server.items import quest_inventory
from wakfu_server.objectives import environmental_daily_selection as selection
from wakfu_server.objectives import environmental_modulox_contracts as modulox
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.wire import proto_field
from wakfu_server.world import World


ADDITIONS = {
    4475: (4520, 138, 141, 110, 3000, [8352, 8353]),
    4793: (5137, 159, 231, 200, 4000, [8993, 8994]),
}


class RecurringModuloxStrictBossDeltaTests(unittest.TestCase):
    def test_two_strict_boss_sources_preserve_62_and_settle_authenticated_final_room_once(
        self,
    ):
        from test_recurring_hunter_backend import RecurringHunterBackendTests

        fixture = RecurringHunterBackendTests(
            methodName="test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, owner = fixture.store, fixture.owner
        character_id, identity = fixture.character["id"], 4475
        with store.connection() as db:

            def original_rows():
                return [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM recurring_modulox_authority "
                        "WHERE definition_id<>ALL(%s) ORDER BY definition_id,version",
                        (list(ADDITIONS),),
                    )
                ]

            before = original_rows()
            self.assertEqual(len(before), 62)
            old_contracts = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM recurring_hunter_contracts "
                    "WHERE interpretation_policy=%s AND definition_id<>ALL(%s) ORDER BY definition_id,version",
                    (recurring.MODULOX_POLICY, list(ADDITIONS)),
                )
            ]
            self.assertEqual(len(old_contracts), 62)
            for definition, (
                boss,
                dungeon,
                real_minimum,
                effective,
                parameter,
                reward_ids,
            ) in ADDITIONS.items():
                source, contract, rewards = recurring._load(db, definition)
                authority = source["daily_target_authority"]
                self.assertEqual(
                    (
                        authority["boss_reference"],
                        authority["dungeon_definition_id"],
                        authority["route_policy_version"],
                    ),
                    (boss, dungeon, 3),
                )
                self.assertIsNone(modulox._native_boss_authority(db, authority))
                self.assertTrue(
                    modulox.attest_authority(
                        db, authority, attest=recurring._daily_source
                    )
                )
                self.assertEqual(
                    (contract.period_ms, contract.required_distinct),
                    (selection.DAY_MS, 1),
                )
                self.assertEqual({r["native_type"] for r in rewards}, {5, 17})
                self.assertEqual([r["reward_id"] for r in rewards], reward_ids)
                self.assertEqual(authority["native_reward_order"], reward_ids)
                self.assertEqual(
                    (contract.minimum_level, authority["target_effective_level"]),
                    (real_minimum, effective),
                )
                self.assertEqual(
                    [(r["native_type"], r["reference"], r["amount"]) for r in rewards],
                    [(17, None, parameter), (5, 20752, 2)],
                )
            source, contract, rewards = recurring._load(db, identity)
            authority = source["daily_target_authority"]
            target, minimum = (
                authority["target_effective_level"],
                contract.minimum_level,
            )
            active = db.execute(
                "SELECT * FROM recurring_hunter_daily_active WHERE singleton"
            ).fetchone()
            self.assertFalse(active["enabled"])
            pool = db.execute(
                "SELECT count(*) AS n,count(DISTINCT category_id) AS categories FROM recurring_hunter_daily_members "
                "WHERE pool_version=%s",
                ("wakemu.daily-hunter50-modulox64-v1",),
            ).fetchone()
            self.assertEqual((pool["n"], pool["categories"]), (114, 20))
            members = [
                r["definition_id"]
                for r in db.execute(
                    "SELECT definition_id FROM recurring_hunter_daily_members "
                    "WHERE pool_version=%s AND category_id=%s ORDER BY definition_id,version",
                    (active["pool_version"], authority["category_id"]),
                )
            ]
            day = recurring._now(db) // selection.DAY_MS
            day += (members.index(identity) - day) % len(members)
            clock = [day * selection.DAY_MS + 1000]
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s", (minimum, character_id)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[minimum], character_id),
            )
            with self.assertRaises(DatabaseError), db.transaction():
                db.execute(
                    "UPDATE recurring_modulox_authority SET boss_reference=1 WHERE definition_id=%s",
                    (identity,),
                )
        with native_catalog._database().connection() as catalog_db:
            configuration = catalog_db.execute(
                "SELECT configuration FROM dungeon_runtime_configurations "
                "WHERE route_key=%s AND policy_version=%s",
                (authority["route_key"], authority["route_policy_version"]),
            ).fetchone()["configuration"]
        plan = deepcopy(configuration["compiled_plan"])
        final_order = authority["final_room_order"]
        final = next(r for r in plan["rooms"] if r["order"] == final_order)
        self.assertTrue(
            any(
                m["ref_id"] == authority["boss_reference"] and m["role"] == "boss"
                for m in final["monsters"]
            )
        )
        store.clock = lambda: clock[0] / 1000
        generation = store.begin_session(
            owner["account"], previous_generation=owner["generation"]
        )
        store.select_character(owner["account"], generation, character_id)
        owner["generation"] = generation
        character = store.character(owner["account"], character_id)
        world = World(lambda _: b"", lambda _: b"", lambda *_: True)
        world.join(generation, object(), character)
        self.enterContext(patch.object(presence, "_world", world))
        self.enterContext(
            patch.object(recurring, "_now", side_effect=lambda _: clock[0])
        )
        with store.connection() as db:
            db.execute("UPDATE recurring_hunter_daily_active SET enabled=true")
            chosen = next(
                r
                for r in selection.select_for_character(db, store, character)
                if r["category_id"] == authority["category_id"]
            )
            self.assertEqual(
                (chosen["definition_id"], chosen["version"]),
                (identity, source["version"]),
            )
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                "(%s,%s,'npc_dialogue',777,888,'isolated acceptance receipt, no NPC activation')",
                (identity, source["version"]),
            )
            storage.record_event(
                db,
                character_id,
                "strict-boss:accept",
                dict(
                    kind="native_recurring_acceptance",
                    definition_id=identity,
                    real_level=minimum,
                    source_kind="npc_dialogue",
                    source_reference=777,
                    action_id=888,
                ),
            )
            db.execute(
                "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                (
                    datetime.fromtimestamp(clock[0] / 1000, timezone.utc),
                    character_id,
                    "strict-boss:accept",
                ),
            )
            self.assertTrue(
                recurring.accept_from_receipt(
                    db, store, character, identity, receipt_key="strict-boss:accept"
                )["applied"]
            )
            self.assertFalse(
                recurring.accept_from_receipt(
                    db, store, character, identity, receipt_key="strict-boss:accept"
                )["applied"]
            )
            db.execute(
                "UPDATE achievement_scaled_xp_active SET enabled=true WHERE singleton"
            )
            sheet = b"".join(
                proto_field(k, v)
                for k, v in (
                    (8, 0),
                    (18, b"Strict boss native actor"),
                    (24, target),
                    (56, 0),
                    (64, 1),
                )
            )
            db.execute(
                "INSERT INTO character_builds VALUES(%s,0,%s,%s,%s,%s) "
                "ON CONFLICT(character_id,build_index) DO UPDATE SET sheet=EXCLUDED.sheet",
                (
                    character_id,
                    sheet,
                    builds.EMPTY_EQUIPMENT,
                    b"",
                    builds.EMPTY_APTITUDES,
                ),
            )
            db.execute(
                "UPDATE character_build_selection SET active_index=0,revision=revision+1 WHERE character_id=%s",
                (character_id,),
            )
            admitted = store.character(owner["account"], character_id, db)
            self.assertEqual(admitted["effective_level"], target)
            fixture.character = admitted
            original_event = service._event

            def fight(*, wrong_role=False):
                rooms = deepcopy(plan["rooms"])
                room = next(r for r in rooms if r["order"] == final_order)
                if wrong_role:
                    for member in room["monsters"]:
                        if member["ref_id"] == authority["boss_reference"]:
                            member["role"] = "monster"
                roster = [
                    m["ref_id"] for m in room["monsters"] for _ in range(m["count"])
                ]

                def prepare_receipt(connection, actor, resolved, originals):
                    instance = connection.execute(
                        "SELECT instance_id FROM dungeon_room_encounters WHERE fight_id=%s",
                        (resolved.id,),
                    ).fetchone()["instance_id"]
                    connection.execute(
                        "UPDATE dungeon_instances SET definition_id=%s WHERE instance_id=%s",
                        (authority["dungeon_definition_id"], instance),
                    )
                    connection.execute(
                        "UPDATE dungeon_room_encounters SET room_order=%s WHERE fight_id=%s",
                        (final_order, resolved.id),
                    )
                    connection.execute(
                        "UPDATE dungeon_room_runs SET rooms=%s WHERE instance_id=%s",
                        (Jsonb(rooms), instance),
                    )
                    connection.execute(
                        "INSERT INTO dungeon_difficulty_selections "
                        "(instance_id,stasis_level,competitive,competitive_max_level,revision,selected_by) "
                        "VALUES(%s,1,true,%s,1,%s)",
                        (instance, target, character_id),
                    )
                    dungeon_difficulty.freeze_encounter(
                        connection, instance, resolved.id, expected_selection_revision=1
                    )
                    resolved.actors[character_id] = Actor(
                        character_id,
                        0,
                        (admitted["x"], admitted["y"], admitted["z"]),
                        admitted["hp"],
                        6,
                        3,
                        0,
                        builds.effective_sheet_level(
                            admitted, admitted.get("active_build_index", 0)
                        ),
                        owner_id=admitted["account_id"],
                        controlled=True,
                    )
                    return original_event(connection, actor, resolved, originals)

                with patch.object(service, "_event", side_effect=prepare_receipt):
                    resolved, event = fixture.fight(db, roster, bosses=False)
                db.execute(
                    "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                    (
                        datetime.fromtimestamp(clock[0] / 1000, timezone.utc),
                        character_id,
                        "fight:" + str(resolved.id),
                    ),
                )
                return resolved, event

            rejected, event = fight(wrong_role=True)
            self.assertEqual(
                recurring.settle_combat(db, store, admitted, rejected, event)[
                    "completed"
                ],
                [],
            )
            winning, event = fight()
            before_xp = store.character(owner["account"], character_id, db)["xp"]
            before_tokens = quest_inventory.quantity(
                store.character(owner["account"], character_id, db), [20752]
            )
            with self.assertRaisesRegex(
                RuntimeError, "rollback strict boss"
            ), db.transaction():
                self.assertEqual(
                    recurring.settle_combat(db, store, admitted, winning, event)[
                        "completed"
                    ],
                    [identity],
                )
                raise RuntimeError("rollback strict boss")
            self.assertEqual(
                store.character(owner["account"], character_id, db)["xp"], before_xp
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_victory_proofs"
                ).fetchone()["n"],
                0,
            )
            result = recurring.settle_combat(db, store, admitted, winning, event)
            self.assertEqual(result["completed"], [identity])
            self.assertEqual(
                [(r["definition_id"], r["boss_reference"]) for r in result["credited"]],
                [(identity, authority["boss_reference"])],
            )
            earned = db.execute(
                "SELECT * FROM achievement_scaled_xp_receipts WHERE achievement_id=%s",
                (identity,),
            ).fetchone()
            self.assertEqual(earned["real_level"], minimum)
            current = store.character(owner["account"], character_id, db)
            self.assertEqual(current["xp"], before_xp + earned["final_amount"])
            self.assertEqual(
                quest_inventory.quantity(current, [20752]), before_tokens + 2
            )
            self.assertEqual(
                recurring.settle_combat(db, store, current, winning, event)[
                    "completed"
                ],
                [],
            )
            self.assertEqual(
                store.character(owner["account"], character_id, db)["xp"], current["xp"]
            )
            self.assertEqual(
                quest_inventory.quantity(
                    store.character(owner["account"], character_id, db), [20752]
                ),
                before_tokens + 2,
            )
            self.assertEqual(original_rows(), before)
            self.assertEqual(
                [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM recurring_hunter_contracts "
                        "WHERE interpretation_policy=%s AND definition_id<>ALL(%s) ORDER BY definition_id,version",
                        (recurring.MODULOX_POLICY, list(ADDITIONS)),
                    )
                ],
                old_contracts,
            )
            self.assertEqual(storage.pending_rewards(db, character_id), [])
