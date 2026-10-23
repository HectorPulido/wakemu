"""Shared Modulox backend: original sources and declared frozen modulation rule."""
from datetime import datetime, timezone
import struct
import unittest
from unittest.mock import patch

from psycopg import DatabaseError
from psycopg.types.json import Jsonb
from wakfu_server import builds, dungeon_difficulty
from wakfu_server.combat_state import Actor
from wakfu_server.achievements import rewards, service, storage
from wakfu_server.items import quest_inventory
from wakfu_server.objectives import environmental_daily_selection as selection
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.wire import proto_field
from wakfu_server.world import World


NATIVE_BOSS_ADDITIONS = (4073, 4107, 4113, 4117, 4118, 4478, 4787, 4789, 4475, 4793)


class RecurringModuloxBackendTests(unittest.TestCase):
    def test_all_54_sources_selected_offer_frozen_modulation_and_scaled_rewards_once(
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
        identity, category = 4062, 684
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_authority WHERE definition_id<>ALL(%s)",
                    (list(NATIVE_BOSS_ADDITIONS),),
                ).fetchone()["n"],
                54,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_category_members"
                ).fetchone()["n"],
                102,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_category_sources"
                ).fetchone()["n"],
                5,
            )
            contracts = db.execute(
                "SELECT definition_id FROM recurring_hunter_contracts "
                "WHERE interpretation_policy=%s AND definition_id<>ALL(%s) ORDER BY definition_id",
                (recurring.MODULOX_POLICY, list(NATIVE_BOSS_ADDITIONS)),
            ).fetchall()
            self.assertEqual(len(contracts), 54)
            for entry in contracts:
                source, contract, native_rewards = recurring._load(
                    db, entry["definition_id"]
                )
                authority = source["daily_target_authority"]
                self.assertEqual(
                    (contract.period_ms, contract.required_distinct), (86400000, 1)
                )
                self.assertEqual({r["native_type"] for r in native_rewards}, {5, 17})
                self.assertEqual(
                    [r["reward_id"] for r in native_rewards],
                    authority["native_reward_order"],
                )
                self.assertEqual(
                    authority["interpretation_policy"], recurring.MODULOX_POLICY
                )
            source, contract, native_rewards = recurring._load(db, identity)
            authority = source["daily_target_authority"]
            self.assertEqual(
                (
                    contract.minimum_level,
                    authority["category_id"],
                    authority["boss_reference"],
                    authority["dungeon_definition_id"],
                    authority["final_room_order"],
                    authority["target_effective_level"],
                ),
                (51, 684, 44, 90, 3, 20),
            )
            self.assertEqual(
                [
                    (r["native_type"], r["reference"], r["amount"])
                    for r in native_rewards
                ],
                [(5, 20752, 2), (17, None, 1000)],
            )
            active = db.execute(
                "SELECT * FROM recurring_hunter_daily_active WHERE singleton"
            ).fetchone()
            self.assertFalse(active["enabled"])
            counts = db.execute(
                "SELECT count(*) AS members,count(DISTINCT category_id) AS categories "
                "FROM recurring_hunter_daily_members WHERE pool_version=%s",
                ("wakemu.daily-hunter50-modulox62-v1",),
            ).fetchone()
            self.assertEqual((counts["members"], counts["categories"]), (112, 20))
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
            db.execute("UPDATE characters SET level=50 WHERE id=%s", (character_id,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[50], character_id),
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

        def receipt(db, definition, key):
            actual = store.character(owner["account"], character_id, db)
            storage.record_event(
                db,
                character_id,
                key,
                dict(
                    kind="native_recurring_acceptance",
                    definition_id=definition,
                    real_level=actual["level"],
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
                    key,
                ),
            )
            return recurring.accept_from_receipt(
                db, store, actual, definition, receipt_key=key
            )

        with store.connection() as db:
            self.assertEqual(selection.select_for_character(db, store, character), ())
            db.execute("UPDATE recurring_hunter_daily_active SET enabled=true")
            choices = selection.select_for_character(db, store, character)
            selected = next(r for r in choices if r["category_id"] == category)
            self.assertEqual(
                (selected["definition_id"], selected["version"], selected["eligible"]),
                (identity, 1, False),
            )
            daily_choice = next(r for r in choices if r["category_id"] == 691)
            daily_id, weekly_id = daily_choice["definition_id"], 3766
            for definition, version in (
                (identity, 1),
                (daily_id, daily_choice["version"]),
                (weekly_id, recurring._load(db, weekly_id)[0]["version"]),
            ):
                db.execute(
                    "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                    "(%s,%s,'npc_dialogue',777,888,'isolated owned acceptance producer, not native NPC activation')",
                    (definition, version),
                )
            with self.assertRaises(ValueError):
                receipt(db, identity, "modulox:level50")
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_acceptances "
                    "WHERE definition_id=%s",
                    (identity,),
                ).fetchone()["n"],
                0,
            )
            db.execute("UPDATE characters SET level=51 WHERE id=%s", (character_id,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[51], character_id),
            )
            character = store.character(owner["account"], character_id, db)
            self.assertTrue(receipt(db, weekly_id, "modulox:weekly-coexist")["applied"])
            self.assertTrue(receipt(db, daily_id, "modulox:daily-coexist")["applied"])
            self.assertTrue(receipt(db, identity, "modulox:owned-offer")["applied"])
            self.assertFalse(
                recurring.accept_from_receipt(
                    db, store, character, identity, receipt_key="modulox:owned-offer"
                )["applied"]
            )
            self.assertIn(identity, storage.load_locked(db, character_id)["running"])
            self.assertFalse(
                db.execute(
                    "SELECT enabled FROM achievement_scaled_xp_active WHERE singleton"
                ).fetchone()["enabled"]
            )
            db.execute(
                "UPDATE achievement_scaled_xp_active SET enabled=true WHERE singleton"
            )
            # Actor effective level is supplied while constructing the winning
            # fight, before the actual server event is generated and recorded.
            original_event = service._event

            def fight(
                *,
                competitive=True,
                cap=20,
                actor_level=20,
                definition=90,
                boss=44,
                room_order=3
            ):
                sheet = b"".join(
                    proto_field(k, v)
                    for k, v in (
                        (8, 0),
                        (18, b"Winning actor build"),
                        (24, actor_level),
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
                fixture.character = admitted
                self.assertEqual(
                    (admitted["level"], admitted["effective_level"]), (51, actor_level)
                )

                def construct_event(connection, actor, resolved, originals):
                    instance = connection.execute(
                        "SELECT instance_id FROM dungeon_room_encounters "
                        "WHERE fight_id=%s",
                        (resolved.id,),
                    ).fetchone()["instance_id"]
                    connection.execute(
                        "UPDATE dungeon_instances SET definition_id=%s WHERE instance_id=%s",
                        (definition, instance),
                    )
                    connection.execute(
                        "UPDATE dungeon_room_encounters SET room_order=%s WHERE fight_id=%s",
                        (room_order, resolved.id),
                    )
                    connection.execute(
                        "UPDATE dungeon_room_runs SET rooms=%s WHERE instance_id=%s",
                        (
                            Jsonb(
                                [
                                    dict(
                                        order=room_order,
                                        monsters=[dict(ref_id=boss, role="boss")],
                                    )
                                ]
                            ),
                            instance,
                        ),
                    )
                    connection.execute(
                        "INSERT INTO dungeon_difficulty_selections "
                        "(instance_id,stasis_level,competitive,competitive_max_level,revision,selected_by) "
                        "VALUES(%s,1,%s,%s,1,%s)",
                        (
                            instance,
                            competitive,
                            cap if competitive else 0,
                            character_id,
                        ),
                    )
                    frozen = dungeon_difficulty.freeze_encounter(
                        connection, instance, resolved.id, expected_selection_revision=1
                    )
                    if definition == authority["dungeon_definition_id"]:
                        self.assertIsNotNone(frozen)
                    resolved.actors[character_id] = Actor(
                        id=admitted["id"],
                        team=0,
                        position=(admitted["x"], admitted["y"], admitted["z"]),
                        hp=admitted["hp"],
                        ap=6,
                        mp=3,
                        initiative=0,
                        effective_level=builds.effective_sheet_level(
                            admitted, admitted.get("active_build_index", 0)
                        ),
                        owner_id=admitted["account_id"],
                        controlled=True,
                    )
                    self.assertEqual(
                        resolved.actors[character_id].effective_level, actor_level
                    )
                    return original_event(connection, actor, resolved, originals)

                with patch.object(service, "_event", side_effect=construct_event):
                    resolved, event = fixture.fight(db, [boss])
                db.execute(
                    "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                    (
                        datetime.fromtimestamp(clock[0] / 1000, timezone.utc),
                        character_id,
                        "fight:" + str(resolved.id),
                    ),
                )
                return resolved, event

            for options in (
                dict(competitive=False),
                dict(actor_level=21),
                dict(cap=35),
                dict(definition=1),
                dict(boss=1259),
                dict(room_order=2),
            ):
                with self.subTest(options=options):
                    resolved, event = fight(**options)
                    result = recurring.settle_combat(
                        db, store, character, resolved, event
                    )
                    self.assertNotIn(identity, result["completed"])
                    self.assertFalse(
                        any(r["definition_id"] == identity for r in result["credited"])
                    )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_victory_proofs"
                ).fetchone()["n"],
                0,
            )
            winning, event = fight()
            # Change only the current persisted build AFTER fight construction.
            # This selected build exceeds the original target; the winning
            # actor and immutable encounter still prove effective level20.
            sheet = b"".join(
                proto_field(k, v)
                for k, v in (
                    (8, 0),
                    (18, b"Post victory build"),
                    (24, 35),
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
            character = store.character(owner["account"], character_id, db)
            self.assertEqual(
                (character["level"], character["effective_level"]), (51, 35)
            )
            with self.assertRaises(ValueError):
                recurring.settle_combat(
                    db, store, character, winning, dict(event, completed_dungeon_id=1)
                )
            quest_inventory.grant(db, character_id, 20752, 9999)
            before_xp = character["xp"]
            # Real settlement inside a discarded outer transaction proves that
            # proof, credits, XP, journal and pending rewards roll back together.
            with self.assertRaisesRegex(
                RuntimeError, "rollback Modulox settlement"
            ), db.transaction():
                result = recurring.settle_combat(db, store, character, winning, event)
                self.assertIn(identity, result["completed"])
                self.assertGreater(
                    store.character(owner["account"], character_id, db)["xp"], before_xp
                )
                raise RuntimeError("rollback Modulox settlement")
            self.assertEqual(
                store.character(owner["account"], character_id, db)["xp"], before_xp
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_victory_proofs"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(storage.pending_rewards(db, character_id), [])
            result = recurring.settle_combat(db, store, character, winning, event)
            self.assertEqual(result["completed"], [identity])
            self.assertEqual(
                {r["definition_id"] for r in result["credited"]}, {weekly_id, identity}
            )
            self.assertTrue(all(r["boss_reference"] == 44 for r in result["credited"]))
            proof = db.execute(
                "SELECT * FROM recurring_modulox_victory_proofs"
            ).fetchone()
            self.assertEqual(
                (
                    proof["fight_id"],
                    proof["effective_level"],
                    proof["target_effective_level"],
                    proof["difficulty_snapshot"]["competitive"],
                ),
                (winning.id, 20, 20, True),
            )
            earned = dict(
                db.execute(
                    "SELECT * FROM achievement_scaled_xp_receipts WHERE achievement_id=%s",
                    (identity,),
                ).fetchone()
            )
            self.assertEqual(earned["real_level"], 51)
            self.assertEqual(earned["native_parameter"], 1000)
            current_xp = store.character(owner["account"], character_id, db)["xp"]
            self.assertEqual(current_xp, before_xp + earned["final_amount"])
            xp_packets = [
                struct.unpack(">BBqqhB", body)
                for opcode, body in result["packets"]
                if opcode == 13613
            ]
            self.assertEqual(
                [(r[2], r[3]) for r in xp_packets],
                [(character_id, earned["final_amount"])],
            )
            pending = storage.pending_rewards(db, character_id)
            self.assertEqual(len(pending), 1)
            self.assertEqual(
                (
                    pending[0]["achievement_id"],
                    pending[0]["payload"]["aeV"],
                    pending[0]["payload"]["ckl"],
                ),
                (identity, 5, [20752, 2]),
            )
            self.assertTrue(pending[0]["cycle_key"].startswith("modulox-daily:"))
            journal = storage.load_locked(db, character_id)
            self.assertIn(identity, journal["completed"])
            self.assertTrue({weekly_id, daily_id}.issubset(set(journal["running"])))
            replay = recurring.settle_combat(db, store, character, winning, event)
            self.assertEqual((replay["completed"], replay["credited"]), ([], []))
            self.assertEqual(
                store.character(owner["account"], character_id, db)["xp"], current_xp
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_victory_proofs"
                ).fetchone()["n"],
                1,
            )
            with self.assertRaises(DatabaseError), db.transaction():
                db.execute(
                    "UPDATE recurring_modulox_victory_proofs SET effective_level=19"
                )
            db.execute(
                "UPDATE achievement_scaled_xp_active SET enabled=false WHERE singleton"
            )
            clock[0] += selection.DAY_MS
            recurring.synchronize(db, store, character)
            self.assertEqual(storage.pending_rewards(db, character_id), pending)
            self.assertNotIn(
                identity, storage.load_locked(db, character_id)["completed"]
            )
            from wakfu_server.dungeon_entry_payment import consume

            consume(db, [character_id], 20752, 2)
        generation = store.begin_session(
            owner["account"], previous_generation=generation
        )
        store.select_character(owner["account"], generation, character_id)
        owner["generation"] = generation
        with store.connection() as db:
            current = store.character(owner["account"], character_id, db)
            self.assertEqual(current["xp"], current_xp)
            self.assertEqual(quest_inventory.quantity(current, [20752]), 9999)
            self.assertEqual(storage.pending_rewards(db, character_id), [])
            self.assertEqual(service.drain_rewards(db, store, current), [])
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM achievement_scaled_xp_receipts WHERE achievement_id=%s",
                        (identity,),
                    ).fetchone()
                ),
                earned,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=%s",
                    (character_id, identity),
                ).fetchone()["n"],
                2,
            )

    def test_original_102_category_quota_blocks_unqualified_members_and_preserves_owned_replay(
        self,
    ):
        from copy import deepcopy
        from test_recurring_hunter_backend import RecurringHunterBackendTests

        fixture = RecurringHunterBackendTests(
            methodName="test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, owner = fixture.store, fixture.owner
        character_id, identity, category = fixture.character["id"], 4062, 684
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_modulox_category_members"
                ).fetchone()["n"],
                102,
            )
            source, contract, _ = recurring._load(db, identity)
            self.assertEqual(contract.minimum_level, 51)
            # This original member deliberately has no executable target among
            # the 54. Category authority must still account for its old journal.
            unsupported = db.execute(
                "SELECT m.* FROM recurring_modulox_category_members m "
                "LEFT JOIN recurring_modulox_authority a ON a.definition_id=m.definition_id "
                "WHERE m.category_id=%s AND a.definition_id IS NULL ORDER BY m.definition_id LIMIT 1",
                (category,),
            ).fetchone()
            self.assertIsNotNone(unsupported)
            opposite = db.execute(
                "SELECT definition_id FROM recurring_modulox_category_members "
                "WHERE category_id<>%s ORDER BY definition_id LIMIT 1",
                (category,),
            ).fetchone()["definition_id"]
            active = db.execute(
                "SELECT * FROM recurring_hunter_daily_active WHERE singleton"
            ).fetchone()
            self.assertFalse(active["enabled"])
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
                (chosen["definition_id"], chosen["version"], chosen["eligible"]),
                (identity, 1, True),
            )
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                "(%s,1,'npc_dialogue',777,888,'isolated quota-test owned receipt producer')",
                (identity,),
            )
            key = "modulox:category-quota"
            storage.record_event(
                db,
                character_id,
                key,
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
                    key,
                ),
            )
            baseline = storage.load_locked(db, character_id)
            other = unsupported["definition_id"]
            current_date = clock[0] - 1
            previous_date = current_date - unsupported["period_ms"]
            self.assertGreaterEqual(previous_date, unsupported["anchor_ms"])

            def journal(*, running=(), completed=(), dates=None):
                state = deepcopy(baseline)
                state["running"] = sorted(set(state["running"]) | set(running))
                state["completed"] = sorted(set(state["completed"]) | set(completed))
                state["completion_dates"].update(dates or {})
                storage.store(db, character_id, state)
                return state

            def accept(actor=character):
                return recurring.accept_from_receipt(
                    db, store, actor, identity, receipt_key=key
                )

            for state, message in (
                (journal(running=(other,)), "active or non-resettable"),
                (None, "active or non-resettable"),
                (None, "completion date"),
            ):
                if state is None:
                    if message == "completion date":
                        state = journal(completed=(other,))
                    else:
                        state = journal(
                            completed=(other,), dates={str(other): current_date}
                        )
                with self.subTest(message=message), self.assertRaisesRegex(
                    ValueError, message
                ):
                    accept()
                self.assertEqual(storage.load_locked(db, character_id), state)
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM recurring_hunter_acceptances "
                        "WHERE character_id=%s AND definition_id=%s",
                        (character_id, identity),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(storage.pending_rewards(db, character_id), [])
            # Acceptance is real, then explicitly rolled back to exercise a
            # second independent positive category case with the same receipt.
            old = journal(completed=(other,), dates={str(other): previous_date})
            with self.assertRaisesRegex(
                RuntimeError, "rollback prior-period acceptance"
            ), db.transaction():
                self.assertTrue(accept()["applied"])
                raise RuntimeError("rollback prior-period acceptance")
            self.assertEqual(storage.load_locked(db, character_id), old)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_acceptances "
                    "WHERE character_id=%s AND definition_id=%s",
                    (character_id, identity),
                ).fetchone()["n"],
                0,
            )
            unrelated = journal(running=(opposite,))
            self.assertTrue(accept()["applied"])
            current = storage.load_locked(db, character_id)
            self.assertTrue({identity, opposite}.issubset(set(current["running"])))
            self.assertEqual(
                set(current["running"]) - {identity}, set(unrelated["running"])
            )
            # Own running quest would fail a fresh category evaluation; replay
            # must instead preserve its exact durable acceptance once.
            self.assertFalse(accept()["applied"])
            self.assertEqual(storage.load_locked(db, character_id), current)
            foreign = store.character(
                fixture.foreign["account"], fixture.foreign["character"], db
            )
            with self.assertRaises(ValueError):
                accept(foreign)
            with self.assertRaises(ValueError):
                accept(dict(character, account_id=foreign["account_id"]))
            rows = db.execute(
                "SELECT version,acceptance_event_key FROM recurring_hunter_acceptances "
                "WHERE character_id=%s AND definition_id=%s",
                (character_id, identity),
            ).fetchall()
            self.assertEqual(rows, [dict(version=1, acceptance_event_key=key)])
            self.assertEqual(storage.pending_rewards(db, character_id), [])
            self.assertEqual(
                store.character(owner["account"], character_id, db)["xp"],
                XP_BY_LEVEL[51],
            )
