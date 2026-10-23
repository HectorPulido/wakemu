"""Reconstructed Nox scoring consumes validated shared damage receipts."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from postgres_case import PostgresCase

from wakfu_server.combat_npc_phase_controller import (
    NOX_SCORE_POLICY,
    install_npc_phase_score,
    deliver_npc_score_result,
)
from wakfu_server.maps.boss_score_runtime import (
    stage_damage,
    staged_score,
    finish_survival,
)


class NoxScoreControllerTests(unittest.TestCase):
    def fixture(self, difficulty=0):
        player = SimpleNamespace(id=7, controlled=True, team=0, hp=100)
        boss = SimpleNamespace(
            id=-200,
            controlled=False,
            team=1,
            hp=99999999,
            position=(-1, -11, 0),
            state_ledger=SimpleNamespace(entries=[]),
        )
        if difficulty:
            boss.state_ledger.entries.append(
                SimpleNamespace(reference=8988, level=difficulty)
            )
        fight = SimpleNamespace(
            phase="active",
            turn_id=1,
            native_start_event_delivered=True,
            native_timeline_round=1,
            actors={7: player, -200: boss},
            current=boss,
            native_npc_initialization_receipts={
                -200: dict(
                    ref=5664,
                    initialized=True,
                    resolved_states=[dict(state_id=8969)],
                )
            },
        )
        calls = []

        def apply(handler, invocation, reference, level, **kwargs):
            calls.append((invocation, reference, level, kwargs))
            boss.state_ledger.entries.append(
                SimpleNamespace(reference=reference, level=level)
            )
            return True

        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=fight, apply_state_reference=apply),
            native_state_handler=SimpleNamespace(catalog=object()),
        )
        install_npc_phase_score(dispatcher)
        return fight, dispatcher, calls

    def hit(self, fight, amount, *, uid=1, armor=0):
        stage_damage(
            fight,
            action_id=1,
            runner_uid=uid,
            source=fight.actors[7],
            target=fight.actors[-200],
            result=dict(
                hp_requested=amount, virtual_hp_absorbed=0, armor_absorbed=armor
            ),
        )

    def test_shared_receipts_deduplicate_and_zero_damage_never_wins(self):
        fight, dispatcher, calls = self.fixture()
        self.assertEqual(
            fight.boss_score_profile["encounter_controller"], NOX_SCORE_POLICY
        )
        self.assertFalse(deliver_npc_score_result(dispatcher, actor_id=-200))
        self.hit(fight, 100)
        self.hit(fight, 100)
        self.assertEqual(staged_score(fight), 100)
        self.assertFalse(deliver_npc_score_result(dispatcher, actor_id=-200))
        self.assertEqual(calls, [])
        fight.native_timeline_round = 11
        self.assertFalse(finish_survival(fight))
        self.assertEqual(fight.phase, "active")

    def test_threshold_and_difficulty_enter_native_marker_once(self):
        fight, dispatcher, calls = self.fixture(difficulty=2)
        self.assertEqual(
            (
                fight.boss_score_profile["round_limit"],
                fight.boss_score_profile["minimum_score"],
            ),
            (12, 4000000),
        )
        self.hit(fight, 3999999)
        self.assertFalse(deliver_npc_score_result(dispatcher, actor_id=-200))
        self.hit(fight, 0, uid=2, armor=1)
        with patch(
            "wakfu_server.combat_definitions.state_profile",
            return_value=dict(duration=-1, realtime_duration=0, level=1),
        ):
            self.assertTrue(deliver_npc_score_result(dispatcher, actor_id=-200))
        self.assertEqual(len(calls), 1)
        invocation, reference, level, kwargs = calls[0]
        self.assertEqual(
            (reference, level, invocation.caster_id, invocation.target_id),
            (9031, 1, -200, -200),
        )
        self.assertEqual(invocation.native_retained_container, {"present": False})
        self.assertFalse(deliver_npc_score_result(dispatcher, actor_id=-200))

    def test_staged_receipt_ownership_and_preview_discard(self):
        fight, dispatcher, calls = self.fixture()
        preview = deepcopy(fight)
        self.hit(preview, 3000000)
        self.assertEqual(staged_score(fight), 0)
        event = next(iter(preview.boss_score_events.values()))
        event["owner_actor_id"] = 99
        with self.assertRaisesRegex(ValueError, "ownership"):
            staged_score(preview)

    def test_unreviewed_or_changed_difficulty_rejected_before_marker(self):
        with self.assertRaisesRegex(ValueError, "difficulty"):
            self.fixture(difficulty=11)
        fight, dispatcher, calls = self.fixture(difficulty=1)
        fight.actors[-200].state_ledger.entries[0].level = 2
        with self.assertRaisesRegex(ValueError, "difficulty changed"):
            deliver_npc_score_result(dispatcher, actor_id=-200)
        self.assertEqual(calls, [])

    def test_native_marker_failure_does_not_publish_canonical_preview(self):
        fight, dispatcher, calls = self.fixture()
        self.hit(fight, 3000000)
        canonical = deepcopy(fight)
        dispatcher.native_retention.apply_state_reference = (
            lambda *args, **kwargs: False
        )
        with patch(
            "wakfu_server.combat_definitions.state_profile",
            return_value=dict(duration=-1, realtime_duration=0, level=1),
        ):
            with self.assertRaisesRegex(ValueError, "not installed"):
                deliver_npc_score_result(dispatcher, actor_id=-200)
        self.assertEqual(vars(fight), vars(canonical))
        self.assertFalse(hasattr(fight, "native_npc_score_result"))

    def test_frozen_weight_is_uncapped_but_native_extra_tables_stop_at_ten(self):
        from wakfu_server.dungeon_stele_states import POLICY as STELE_POLICY

        fight, dispatcher, calls = self.fixture()
        del fight.boss_score_profile
        fight.id = 17
        fight.native_dungeon_stele_receipt = dict(
            policy=STELE_POLICY,
            fight_id=17,
            initialized=True,
            actor_ids=[-200],
            difficulty_weight=12,
        )
        with patch(
            "wakfu_server.combat_definitions.state_profile",
            return_value=dict(duration=-1, realtime_duration=0, level=10),
        ):
            install_npc_phase_score(dispatcher)
        self.assertEqual(
            (
                fight.boss_score_profile["difficulty"],
                fight.boss_score_profile["extra_table_turns"],
                fight.boss_score_profile["round_limit"],
                fight.boss_score_profile["minimum_score"],
            ),
            (12, 10, 20, 9000000),
        )
        self.assertEqual((calls[0][1], calls[0][2]), (8988, 10))

    def test_last_player_boundary_updates_bound_boss_before_its_next_turn(self):
        fight, dispatcher, calls = self.fixture()
        self.hit(fight, 3000000)
        fight.current = fight.actors[7]
        with patch(
            "wakfu_server.combat_definitions.state_profile",
            return_value=dict(duration=-1, realtime_duration=0, level=1),
        ):
            self.assertTrue(deliver_npc_score_result(dispatcher, actor_id=7))
        self.assertEqual((calls[0][0].caster_id, calls[0][0].target_id), (-200, -200))
        self.assertEqual(fight.native_npc_score_result["boundary_actor_id"], 7)


class NativeNoxSuccessCarrierTests(unittest.TestCase):
    def test_isolated_controller_decision_uses_actual_native_carrier_and_children(self):
        """Protocol-path witness only: the score decision is explicitly mocked.

        This is not a paid-damage victory or a full encounter acceptance.
        Actor construction, source states, direct eWu, children and wire are real.
        """
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_state_carrier import STATE_CARRIER_APPLICATION_OPCODE
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            native_target_ref=5664,
            native_target_level=245,
            compact_arena=False,
        )
        # Advance actual public Fight turns; this isolated state witness does
        # not claim to qualify RuntimeMessages' turn/ACK delivery ordering.
        for _ in range(len(fight.order)):
            if fight.current.id == -7:
                break
            actor = fight.current
            fight.end_turn(actor.owner_id, actor.id, actor.turn_count)
        self.assertEqual(fight.current.id, -7)
        preview = deepcopy(fight)
        factory, _ = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=100,
            critical=False,
            player_characters=characters,
            deck_blobs=decks,
        )
        dispatcher, packets = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        executed = []
        handler = dispatcher.native_state_handler
        original_execute = handler.execute_child

        def observe(invocation, **kwargs):
            result = original_execute(invocation, **kwargs)
            if invocation.reference in (402276, 402277):
                executed.append(invocation.reference)
            return result

        with patch(
            "wakfu_server.maps.boss_score_runtime.staged_score", return_value=3000000
        ), patch.object(handler, "execute_child", observe), preview.effect_resolution():
            self.assertTrue(deliver_npc_score_result(dispatcher, actor_id=-7))
        entries = [
            entry
            for entry in preview.actors[-7].state_ledger.entries
            if entry.reference == 9031
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, 1)
        self.assertEqual(executed, [402276, 402277])
        self.assertIn(entries[0].uid, preview.state_wire_payloads)
        self.assertTrue(
            any(opcode == STATE_CARRIER_APPLICATION_OPCODE for opcode, body in packets)
        )
        self.assertFalse(
            any(
                entry.reference == 9031
                for entry in fight.actors[-7].state_ledger.entries
            )
        )
        self.assertEqual(snapshot(preview)["native_npc_score_result"]["score"], 3000000)


class NoxDurableScoreTests(PostgresCase):
    def test_threshold_rollback_and_terminal_replay_share_real_receipts(self):
        """Durable accounting witness; damage deliveries are explicit inputs."""
        from wakfu_server.maps import boss_score

        account = self.store.register("nox-score", "local-password")["id"]
        identity = self.store.create_character(account, "NoxScoreWitness")["id"]
        for amount, defeated in ((2999999, True), (3000000, False), (3000000, True)):
            with self.store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                    (fight_id, identity, account),
                )
                boss_score.freeze_snapshot(
                    db,
                    fight_id,
                    dict(
                        policy=boss_score.POLICY,
                        encounter_controller=NOX_SCORE_POLICY,
                        bosses={"-200": dict(reference=5664)},
                        player_ids=[identity],
                        player_team=0,
                        round_limit=10,
                        minimum_score=3000000,
                        difficulty=0,
                    ),
                )
            delivery = dict(
                event_id="damage-runner-receipt",
                source_id=identity,
                target_id=-200,
                owner_actor_id=identity,
                post_mitigation_damage=amount,
                armor_absorbed=0,
                round_number=10,
            )
            with self.assertRaisesRegex(
                RuntimeError, "abort"
            ), self.store.connection() as db:
                boss_score.record_damage(db, fight_id, **delivery)
                raise RuntimeError("abort")
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM boss_score_damage_receipts WHERE fight_id=%s",
                        (fight_id,),
                    ).fetchone()["n"],
                    0,
                )
                boss_score.record_damage(db, fight_id, **delivery)
                boss_score.record_damage(db, fight_id, **delivery)
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s",
                    (fight_id,),
                )
                result = boss_score.finalize(
                    db,
                    fight_id,
                    completed_rounds=10,
                    survived=True,
                    winning_team=0,
                    boss_defeated=defeated,
                )
                self.assertEqual(result["eligible"], amount == 3000000 and defeated)
                self.assertEqual(
                    result["score"], amount if amount == 3000000 and defeated else 0
                )
                self.assertEqual(
                    result,
                    boss_score.finalize(
                        db,
                        fight_id,
                        completed_rounds=10,
                        survived=True,
                        winning_team=0,
                        boss_defeated=defeated,
                    ),
                )
                context = boss_score.drop_context(db, fight_id)
                if amount == 3000000 and defeated:
                    from wakfu_server.combat_nox_complex_loot_policy import (
                        load_policy,
                        permission,
                        validate_durable_permission,
                    )

                    policy = load_policy(db)
                    self.assertEqual(context["score"], amount)
                    self.assertEqual(context["boss_score_drop_rate_bp"], 13000)
                    self.assertEqual(context["nox_complex_loot"], permission(policy))
                    validate_durable_permission(db, fight_id, context)
                    other = db.execute(
                        "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
                    ).fetchone()["id"]
                    with self.assertRaisesRegex(ValueError, "durable terminal"):
                        validate_durable_permission(db, other, context)
                else:
                    self.assertEqual(context, {})
