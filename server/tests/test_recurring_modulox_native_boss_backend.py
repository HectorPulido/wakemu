"""Native BOSS43 authority narrows final-room credit without rewriting roles."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from psycopg import DatabaseError
from psycopg.types.json import Jsonb
from wakfu_server import builds, dungeon_difficulty, native_catalog
from wakfu_server.combat_state import Actor
from wakfu_server.achievements import service, storage
from wakfu_server.items import quest_inventory
from wakfu_server.objectives import environmental_daily_selection as selection
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.objectives import environmental_modulox_contracts as modulox
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.wire import proto_field
from wakfu_server.world import World


NEW_TARGETS = {
    4073: (1726, 25),
    4107: (1836, 49),
    4113: (2368, 8),
    4117: (2972, 83),
    4118: (2827, 82),
    4478: (4874, 148),
    4787: (4318, 126),
    4789: (4400, 129),
}


class RecurringModuloxNativeBossBackendTests(unittest.TestCase):
    def test_eight_native_boss_sources_preserve_54_and_settle_original_monster_role_once(
        self,
    ):
        from test_recurring_hunter_backend import RecurringHunterBackendTests

        fixture = RecurringHunterBackendTests(
            methodName="test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, owner, character_id = (
            fixture.store,
            fixture.owner,
            fixture.character["id"],
        )
        identity, category = 4073, 684
        with store.connection() as db:

            def old_rows():
                return [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM recurring_modulox_authority "
                        "WHERE definition_id<>ALL(%s) ORDER BY definition_id,version",
                        (list(NEW_TARGETS) + [4475, 4793],),
                    )
                ]

            old = old_rows()
            self.assertEqual(len(old), 54)
            child_rows = db.execute(
                "SELECT * FROM recurring_modulox_native_boss_authority ORDER BY definition_id"
            ).fetchall()
            self.assertEqual(len(child_rows), 8)
            self.assertEqual({r["definition_id"] for r in child_rows}, set(NEW_TARGETS))
            self.assertTrue(all(r["native_property_id"] == 43 for r in child_rows))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_native_boss_occurrences"
                ).fetchone()["n"],
                12,
            )
            for definition, (boss, dungeon) in NEW_TARGETS.items():
                source, contract, rewards = recurring._load(db, definition)
                authority = source["daily_target_authority"]
                self.assertEqual(
                    (authority["boss_reference"], authority["dungeon_definition_id"]),
                    (boss, dungeon),
                )
                self.assertEqual(
                    (contract.period_ms, contract.required_distinct),
                    (selection.DAY_MS, 1),
                )
                self.assertEqual({r["native_type"] for r in rewards}, {5, 17})
                self.assertTrue(
                    modulox.attest_authority(
                        db, authority, attest=recurring._daily_source
                    )
                )
            self.assertEqual(old_rows(), old)
            source, contract, rewards = recurring._load(db, identity)
            authority = source["daily_target_authority"]
            self.assertEqual(
                (
                    contract.minimum_level,
                    authority["target_effective_level"],
                    authority["final_room_order"],
                ),
                (51, 50, 4),
            )
            self.assertEqual(
                [
                    (r["reward_id"], r["native_type"], r["reference"], r["amount"])
                    for r in rewards
                ],
                [(7673, 17, None, 1000), (7529, 5, 20752, 2)],
            )
            occurrences = modulox._native_boss_authority(db, authority)
            self.assertEqual(occurrences, ((3, "monster", 1),))
            with self.assertRaises(ValueError):
                recurring._daily_source(
                    authority["native_catalog_revision"],
                    authority["monsters_path"],
                    authority["monsters_sha256"],
                    authority["boss_reference"],
                    authority["route_key"],
                    authority["route_policy_version"],
                    authority["plan_sha256"],
                    authority["dungeon_definition_id"],
                    authority["final_room_order"],
                )
            with self.assertRaises(DatabaseError), db.transaction():
                db.execute(
                    "UPDATE recurring_modulox_native_boss_authority SET native_property_id=42 WHERE definition_id=%s",
                    (identity,),
                )
            active = db.execute(
                "SELECT * FROM recurring_hunter_daily_active WHERE singleton"
            ).fetchone()
            self.assertFalse(active["enabled"])
            counts = db.execute(
                "SELECT count(*) AS n,count(DISTINCT category_id) AS categories "
                "FROM recurring_hunter_daily_members WHERE pool_version=%s",
                ("wakemu.daily-hunter50-modulox62-v1",),
            ).fetchone()
            self.assertEqual((counts["n"], counts["categories"]), (112, 20))
            members = [
                r["definition_id"]
                for r in db.execute(
                    "SELECT definition_id FROM recurring_hunter_daily_members "
                    "WHERE pool_version=%s AND category_id=%s ORDER BY definition_id,version",
                    (active["pool_version"], category),
                )
            ]
            day = recurring._now(db) // selection.DAY_MS
            day += (members.index(identity) - day) % len(members)
            clock = [day * selection.DAY_MS + 1000]
            db.execute("UPDATE characters SET level=51 WHERE id=%s", (character_id,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[51], character_id),
            )
        with native_catalog._database().connection() as catalog_db:
            configuration = catalog_db.execute(
                "SELECT configuration FROM dungeon_runtime_configurations "
                "WHERE route_key=%s AND policy_version=%s",
                (authority["route_key"], authority["route_policy_version"]),
            ).fetchone()["configuration"]
        plan = deepcopy(configuration["compiled_plan"])
        original_plan = deepcopy(plan)
        final = next(r for r in plan["rooms"] if r["order"] == 4)
        self.assertEqual(
            (
                final["monsters"][3]["ref_id"],
                final["monsters"][3]["role"],
                final["monsters"][3]["count"],
            ),
            (1726, "monster", 1),
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
                if r["category_id"] == category
            )
            self.assertEqual(
                (chosen["definition_id"], chosen["version"]),
                (identity, source["version"]),
            )
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                "(%s,%s,'npc_dialogue',777,888,'isolated owned acceptance producer, not NPC activation')",
                (identity, source["version"]),
            )
            storage.record_event(
                db,
                character_id,
                "native-boss43:accept",
                dict(
                    kind="native_recurring_acceptance",
                    definition_id=identity,
                    real_level=51,
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
                    "native-boss43:accept",
                ),
            )
            self.assertTrue(
                recurring.accept_from_receipt(
                    db, store, character, identity, receipt_key="native-boss43:accept"
                )["applied"]
            )
            db.execute(
                "UPDATE achievement_scaled_xp_active SET enabled=true WHERE singleton"
            )
            original_event = service._event

            def fight(*, room_order=4, forged_role=False, extra_target=False):
                sheet = b"".join(
                    proto_field(k, v)
                    for k, v in (
                        (8, 0),
                        (18, b"Native boss actor build"),
                        (24, 50),
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
                self.assertEqual(
                    (admitted["level"], admitted["effective_level"]), (51, 50)
                )
                fixture.character = admitted
                rooms = deepcopy(plan["rooms"])
                room = next(r for r in rooms if r["order"] == room_order)
                if forged_role:
                    room["monsters"][3]["role"] = "boss"
                roster = [
                    m["ref_id"] for m in room["monsters"] for _ in range(m["count"])
                ]
                if extra_target:
                    roster.append(1726)

                def prepare_receipt(connection, actor, resolved, originals):
                    instance_id = connection.execute(
                        "SELECT instance_id FROM dungeon_room_encounters WHERE fight_id=%s",
                        (resolved.id,),
                    ).fetchone()["instance_id"]
                    connection.execute(
                        "UPDATE dungeon_instances SET definition_id=25 WHERE instance_id=%s",
                        (instance_id,),
                    )
                    connection.execute(
                        "UPDATE dungeon_room_encounters SET room_order=%s WHERE fight_id=%s",
                        (room_order, resolved.id),
                    )
                    connection.execute(
                        "UPDATE dungeon_room_runs SET rooms=%s WHERE instance_id=%s",
                        (Jsonb(rooms), instance_id),
                    )
                    connection.execute(
                        "INSERT INTO dungeon_difficulty_selections "
                        "(instance_id,stasis_level,competitive,competitive_max_level,revision,selected_by) "
                        "VALUES(%s,1,true,50,1,%s)",
                        (instance_id, character_id),
                    )
                    dungeon_difficulty.freeze_encounter(
                        connection,
                        instance_id,
                        resolved.id,
                        expected_selection_revision=1,
                    )
                    resolved.actors[character_id] = Actor(
                        admitted["id"],
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

            # Native43 does not authorize an earlier room, changed planned
            # occurrence or extra dead target; no fallback to role='boss'.
            for options in (
                dict(room_order=3),
                dict(forged_role=True),
                dict(extra_target=True),
            ):
                with self.subTest(options=options):
                    resolved, event = fight(**options)
                    result = recurring.settle_combat(
                        db, store, character, resolved, event
                    )
                    self.assertEqual(
                        (result["completed"], result["credited"]), ([], [])
                    )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_victory_proofs"
                ).fetchone()["n"],
                0,
            )
            winning, event = fight()
            current_rooms = db.execute(
                "SELECT r.rooms FROM dungeon_room_runs r JOIN dungeon_room_encounters e "
                "USING(instance_id) WHERE e.fight_id=%s",
                (winning.id,),
            ).fetchone()["rooms"]
            self.assertEqual(current_rooms, original_plan["rooms"])
            before_xp = store.character(owner["account"], character_id, db)["xp"]
            before_items = quest_inventory.quantity(
                store.character(owner["account"], character_id, db), [20752]
            )
            with self.assertRaisesRegex(
                RuntimeError, "rollback native boss settlement"
            ), db.transaction():
                self.assertEqual(
                    recurring.settle_combat(db, store, character, winning, event)[
                        "completed"
                    ],
                    [identity],
                )
                raise RuntimeError("rollback native boss settlement")
            self.assertEqual(
                store.character(owner["account"], character_id, db)["xp"], before_xp
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_victory_proofs"
                ).fetchone()["n"],
                0,
            )
            result = recurring.settle_combat(db, store, character, winning, event)
            self.assertEqual(result["completed"], [identity])
            self.assertEqual(
                [(r["definition_id"], r["boss_reference"]) for r in result["credited"]],
                [(identity, 1726)],
            )
            earned = db.execute(
                "SELECT * FROM achievement_scaled_xp_receipts WHERE achievement_id=%s",
                (identity,),
            ).fetchone()
            self.assertEqual(
                (earned["real_level"], earned["native_parameter"]), (51, 1000)
            )
            current = store.character(owner["account"], character_id, db)
            self.assertEqual(current["xp"], before_xp + earned["final_amount"])
            self.assertEqual(
                quest_inventory.quantity(current, [20752]), before_items + 2
            )
            self.assertEqual(storage.pending_rewards(db, character_id), [])
            replay = recurring.settle_combat(db, store, current, winning, event)
            self.assertEqual((replay["completed"], replay["credited"]), ([], []))
            self.assertEqual(
                store.character(owner["account"], character_id, db)["xp"], current["xp"]
            )
            self.assertEqual(
                quest_inventory.quantity(
                    store.character(owner["account"], character_id, db), [20752]
                ),
                before_items + 2,
            )
            self.assertEqual(old_rows(), old)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_victory_proofs"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=%s",
                    (character_id, identity),
                ).fetchone()["n"],
                2,
            )
        with native_catalog._database().connection() as catalog_db:
            self.assertEqual(
                catalog_db.execute(
                    "SELECT configuration FROM dungeon_runtime_configurations "
                    "WHERE route_key=%s AND policy_version=%s",
                    (authority["route_key"], authority["route_policy_version"]),
                ).fetchone()["configuration"]["compiled_plan"],
                original_plan,
            )
