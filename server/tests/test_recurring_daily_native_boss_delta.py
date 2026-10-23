"""Original daily boss goals with source-bound exact final occurrences."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from psycopg import DatabaseError
from psycopg.types.json import Jsonb
from wakfu_server import native_catalog
from wakfu_server.achievements import service, storage
from wakfu_server.items import quest_inventory
from wakfu_server.objectives import environmental_daily_selection as selection
from wakfu_server.objectives import environmental_modulox_contracts as targets
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.world import World


# Frozen original source fields, independent of the normalized SQL loader.
EXPECTED = {
    4142: (
        6,
        2157,
        65,
        3,
        4,
        [(7, "boss", 1)],
        [(7741, 6, None, 33890, False), (7742, 5, 12686, 20, False)],
    ),
    4151: (
        36,
        1726,
        25,
        2,
        4,
        [(3, "monster", 1)],
        [(7759, 5, 20968, 20, False), (7760, 6, None, 354430, False)],
    ),
    4153: (
        36,
        4519,
        136,
        3,
        6,
        [(3, "boss", 1)],
        [(7763, 5, 20968, 20, False), (7764, 6, None, 354430, False)],
    ),
    4185: (
        81,
        1836,
        49,
        2,
        3,
        [(1, "monster", 6)],
        [(7841, 5, 21003, 20, False), (7842, 6, None, 1971970, False)],
    ),
    4191: (
        96,
        2368,
        8,
        2,
        2,
        [(3, "monster", 2)],
        [(7855, 5, 21004, 20, False), (7856, 6, None, 3235360, False)],
    ),
    4195: (
        111,
        2972,
        83,
        2,
        2,
        [(4, "monster", 1), (5, "monster", 1)],
        [(7863, 5, 21005, 20, False), (7864, 6, None, 5308160, False)],
    ),
    4196: (
        111,
        2827,
        82,
        2,
        1,
        [(0, "monster", 1), (4, "monster", 1)],
        [(7865, 5, 21005, 20, False), (7866, 6, None, 5308160, False)],
    ),
    4217: (
        186,
        4318,
        126,
        2,
        4,
        [(0, "monster", 1), (5, "monster", 1)],
        [(7909, 5, 21010, 20, False), (7910, 6, None, 63103190, False)],
    ),
    4219: (
        186,
        4400,
        129,
        3,
        4,
        [(0, "unknown", 1)],
        [(7913, 5, 21010, 20, False), (7914, 6, None, 63103190, False)],
    ),
    4225: (
        36,
        4651,
        133,
        3,
        1,
        [(0, "boss", 1)],
        [(7922, 5, 20968, 20, False), (7923, 6, None, 354430, False)],
    ),
    4448: (
        36,
        4758,
        137,
        3,
        3,
        [(0, "boss", 1)],
        [(8298, 5, 20968, 20, False), (8299, 6, None, 354430, False)],
    ),
    4459: (
        126,
        4874,
        148,
        2,
        4,
        [(1, "monster", 1), (5, "monster", 1)],
        [(8320, 5, 21006, 20, False), (8321, 6, None, 8708950, False)],
    ),
    4981: (
        216,
        5295,
        179,
        2,
        2,
        [(0, "boss", 1), (2, "monster", 2)],
        [(9323, 5, 29023, 20, False), (9324, 6, None, 175561350, False)],
    ),
    5113: (
        36,
        5376,
        184,
        3,
        2,
        [(7, "boss", 1)],
        [(9625, 5, 20968, 20, False), (9626, 6, None, 354430, False)],
    ),
    5114: (
        36,
        5382,
        185,
        3,
        3,
        [(0, "boss", 1)],
        [(9627, 5, 20968, 20, False), (9628, 6, None, 354430, False)],
    ),
}


class DailyHunterNativeBossDeltaTests(unittest.TestCase):
    def test_15_original_goals_preserve_50_and_settle_strict_and_native43_final_receipts_once(
        self,
    ):
        from test_recurring_hunter_backend import RecurringHunterBackendTests

        fixture = RecurringHunterBackendTests(
            methodName="test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, owner = fixture.store, fixture.owner
        character_id = fixture.character["id"]
        with store.connection() as db:

            def old_rows():
                return [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM recurring_hunter_target_authority ORDER BY definition_id,version"
                    )
                ]

            original_authorities = old_rows()
            self.assertEqual(len(original_authorities), 50)
            original_contracts = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM recurring_hunter_contracts "
                    "WHERE interpretation_policy=%s ORDER BY definition_id,version",
                    (recurring.DAILY_POLICY,),
                )
            ]
            self.assertEqual(len(original_contracts), 50)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_acceptance_sources"
                ).fetchone()["n"],
                0,
            )
            child_rows = db.execute(
                "SELECT * FROM recurring_hunter_native_target_authority ORDER BY definition_id"
            ).fetchall()
            self.assertEqual({r["definition_id"] for r in child_rows}, set(EXPECTED))
            self.assertTrue(all(r["native_property_id"] == 43 for r in child_rows))
            strict = 0
            mixed = []
            for definition, (
                minimum,
                boss,
                dungeon,
                version,
                final_order,
                occurrences,
                expected_rewards,
            ) in EXPECTED.items():
                source, contract, rewards = recurring._load(db, definition)
                authority = source["daily_target_authority"]
                self.assertEqual(
                    source["interpretation_policy"], recurring.DAILY_NATIVE_POLICY
                )
                self.assertEqual(
                    (
                        contract.minimum_level,
                        contract.period_ms,
                        contract.required_distinct,
                        contract.boss_references,
                    ),
                    (minimum, selection.DAY_MS, 1, (boss,)),
                )
                self.assertEqual(
                    (
                        authority["boss_reference"],
                        authority["dungeon_definition_id"],
                        authority["route_policy_version"],
                        authority["final_room_order"],
                    ),
                    (boss, dungeon, version, final_order),
                )
                self.assertEqual(
                    targets._native_boss_authority(db, authority, kind="daily"),
                    tuple(occurrences),
                )
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
                    expected_rewards,
                )
                self.assertTrue(
                    targets.attest_authority(
                        db, authority, attest=recurring._daily_source, kind="daily"
                    )
                )
                roles = {role for _, role, _ in occurrences}
                strict += roles == {"boss"}
                if "boss" in roles and roles != {"boss"}:
                    mixed.append(definition)
            self.assertEqual(strict, 6)
            self.assertEqual(mixed, [4981])
            self.assertEqual(EXPECTED[4981][5], [(0, "boss", 1), (2, "monster", 2)])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_contracts "
                    "WHERE interpretation_policy=%s",
                    (recurring.DAILY_NATIVE_POLICY,),
                ).fetchone()["n"],
                15,
            )
            active = db.execute(
                "SELECT * FROM recurring_hunter_daily_active WHERE singleton"
            ).fetchone()
            self.assertFalse(active["enabled"])
            pool_version = active["pool_version"]
            with self.assertRaises(DatabaseError), db.transaction():
                db.execute(
                    "UPDATE recurring_hunter_native_target_authority SET proof_sha256=%s WHERE definition_id=4151",
                    ("0" * 64,),
                )
        clock = [int(store.clock() * 1000)]
        store.clock = lambda: clock[0] / 1000
        world = World(lambda _: b"", lambda _: b"", lambda *_: True)
        self.enterContext(patch.object(presence, "_world", world))
        self.enterContext(
            patch.object(recurring, "_now", side_effect=lambda _: clock[0])
        )
        # These two original goals exercise both frozen role branches. Combat
        # finish is a bounded settlement fixture, not a paid dungeon playthrough.
        for identity in (4142, 4151):
            with self.subTest(definition=identity):
                (
                    minimum,
                    boss,
                    dungeon,
                    version,
                    final_order,
                    occurrences,
                    reward_rows,
                ) = EXPECTED[identity]
                with store.connection() as db:
                    source, contract, rewards = recurring._load(db, identity)
                    authority = source["daily_target_authority"]
                    members = [
                        r["definition_id"]
                        for r in db.execute(
                            "SELECT definition_id FROM recurring_hunter_daily_members "
                            "WHERE pool_version=%s AND category_id=%s ORDER BY definition_id,version",
                            (pool_version, authority["category_id"]),
                        )
                    ]
                    day = (
                        max(recurring._now(db), int(store.now().timestamp() * 1000))
                        // selection.DAY_MS
                    )
                    day += (members.index(identity) - day) % len(members)
                    clock[0] = day * selection.DAY_MS + 1000
                    db.execute(
                        "UPDATE characters SET level=%s WHERE id=%s",
                        (minimum, character_id),
                    )
                    db.execute(
                        "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                        (XP_BY_LEVEL[minimum], character_id),
                    )
                old_generation = owner["generation"]
                world.leave(character_id, old_generation)
                generation = store.begin_session(
                    owner["account"], previous_generation=old_generation
                )
                store.select_character(owner["account"], generation, character_id)
                owner["generation"] = generation
                character = store.character(owner["account"], character_id)
                fixture.character = character
                world.join(generation, object(), character)
                with native_catalog._database().connection() as catalog_db:
                    configuration = catalog_db.execute(
                        "SELECT configuration FROM dungeon_runtime_configurations "
                        "WHERE route_key=%s AND policy_version=%s",
                        (authority["route_key"], version),
                    ).fetchone()["configuration"]
                plan = deepcopy(configuration["compiled_plan"])
                original_plan = deepcopy(plan)
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
                        "(%s,%s,'npc_dialogue',777,888,'isolated authenticated receipt, no NPC activation')",
                        (identity, source["version"]),
                    )
                    key = "daily-native:" + str(identity)
                    storage.record_event(
                        db,
                        character_id,
                        key,
                        dict(
                            kind="native_recurring_acceptance",
                            definition_id=identity,
                            real_level=minimum,
                            source_kind="npc_dialogue",
                            source_reference=777,
                            action_id=888,
                        ),
                    )
                    stamp = datetime.fromtimestamp(clock[0] / 1000, timezone.utc)
                    db.execute(
                        "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                        (stamp, character_id, key),
                    )
                    self.assertTrue(
                        recurring.accept_from_receipt(
                            db, store, character, identity, receipt_key=key
                        )["applied"]
                    )
                    self.assertFalse(
                        recurring.accept_from_receipt(
                            db, store, character, identity, receipt_key=key
                        )["applied"]
                    )
                    original_event = service._event

                    def fight(*, wrong_dungeon=False, changed_role=False):
                        rooms = deepcopy(plan["rooms"])
                        room = next(r for r in rooms if r["order"] == final_order)
                        if changed_role:
                            index, role, _ = occurrences[0]
                            room["monsters"][index]["role"] = (
                                "monster" if role == "boss" else "boss"
                            )
                        roster = [
                            m["ref_id"]
                            for m in room["monsters"]
                            for _ in range(m["count"])
                        ]

                        def provision(connection, actor, resolved, originals):
                            instance = connection.execute(
                                "SELECT instance_id FROM dungeon_room_encounters WHERE fight_id=%s",
                                (resolved.id,),
                            ).fetchone()["instance_id"]
                            connection.execute(
                                "UPDATE dungeon_instances SET definition_id=%s WHERE instance_id=%s",
                                (1 if wrong_dungeon else dungeon, instance),
                            )
                            connection.execute(
                                "UPDATE dungeon_room_encounters SET room_order=%s WHERE fight_id=%s",
                                (final_order, resolved.id),
                            )
                            connection.execute(
                                "UPDATE dungeon_room_runs SET rooms=%s WHERE instance_id=%s",
                                (Jsonb(rooms), instance),
                            )
                            return original_event(
                                connection, actor, resolved, originals
                            )

                        with patch.object(service, "_event", side_effect=provision):
                            resolved, event = fixture.fight(db, roster, bosses=False)
                        db.execute(
                            "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                            (stamp, character_id, "fight:" + str(resolved.id)),
                        )
                        return resolved, event

                    for options in (dict(wrong_dungeon=True), dict(changed_role=True)):
                        rejected, event = fight(**options)
                        result = recurring.settle_combat(
                            db, store, character, rejected, event
                        )
                        self.assertEqual(
                            (result["credited"], result["completed"]), ([], [])
                        )
                    actual, event = fight()
                    self.assertEqual(event["completed_dungeon_id"], dungeon)
                    before_xp = store.character(owner["account"], character_id, db)[
                        "xp"
                    ]
                    item = next(r[2] for r in reward_rows if r[1] == 5)
                    item_amount = next(r[3] for r in reward_rows if r[1] == 5)
                    xp_amount = next(r[3] for r in reward_rows if r[1] == 6)
                    self.assertIn(item, quest_inventory.REFERENCES)
                    before_items = quest_inventory.quantity(
                        store.character(owner["account"], character_id, db), [item]
                    )
                    with self.assertRaisesRegex(
                        RuntimeError, "rollback daily native"
                    ), db.transaction():
                        self.assertEqual(
                            recurring.settle_combat(
                                db, store, character, actual, event
                            )["completed"],
                            [identity],
                        )
                        raise RuntimeError("rollback daily native")
                    self.assertEqual(
                        store.character(owner["account"], character_id, db)["xp"],
                        before_xp,
                    )
                    self.assertEqual(
                        quest_inventory.quantity(
                            store.character(owner["account"], character_id, db), [item]
                        ),
                        before_items,
                    )
                    completed = recurring.settle_combat(
                        db, store, character, actual, event
                    )
                    self.assertEqual(completed["completed"], [identity])
                    self.assertEqual(
                        [
                            (r["definition_id"], r["boss_reference"])
                            for r in completed["credited"]
                        ],
                        [(identity, boss)],
                    )
                    current = store.character(owner["account"], character_id, db)
                    self.assertEqual(
                        (current["xp"], quest_inventory.quantity(current, [item])),
                        (before_xp + xp_amount, before_items + item_amount),
                    )
                    replay = recurring.settle_combat(db, store, current, actual, event)
                    self.assertEqual(
                        (replay["credited"], replay["completed"]), ([], [])
                    )
                    self.assertEqual(service.drain_rewards(db, store, current), [])
                    self.assertEqual(
                        store.character(owner["account"], character_id, db)["xp"],
                        current["xp"],
                    )
                    self.assertEqual(
                        quest_inventory.quantity(
                            store.character(owner["account"], character_id, db), [item]
                        ),
                        before_items + item_amount,
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                            "WHERE character_id=%s AND achievement_id=%s AND delivered_at IS NOT NULL",
                            (character_id, identity),
                        ).fetchone()["n"],
                        2,
                    )
                with native_catalog._database().connection() as catalog_db:
                    self.assertEqual(
                        catalog_db.execute(
                            "SELECT configuration FROM dungeon_runtime_configurations "
                            "WHERE route_key=%s AND policy_version=%s",
                            (authority["route_key"], version),
                        ).fetchone()["configuration"]["compiled_plan"],
                        original_plan,
                    )
        with store.connection() as db:
            self.assertEqual(old_rows(), original_authorities)
            self.assertEqual(
                [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM recurring_hunter_contracts "
                        "WHERE interpretation_policy=%s ORDER BY definition_id,version",
                        (recurring.DAILY_POLICY,),
                    )
                ],
                original_contracts,
            )
            self.assertEqual(storage.pending_rewards(db, character_id), [])
