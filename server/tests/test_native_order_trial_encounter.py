"""Typed one-team combat construction remains isolated from ordinary PvE."""

from dataclasses import replace
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server import (
    combat_abandon,
    combat_bootstrap,
    combat_death_reconciliation,
    fight_checkpoint_store,
    combat_shared,
    combat_runtime_messages,
    combat_state,
    combat_state_ledger,
    combat_wire,
    combat_environment_participant_footprints,
    combat_encounter_roles,
    combat_actor_snapshot,
    native_order_trial_admission,
    native_order_trial_encounter,
)

from pathlib import Path
import json
import struct

_FIXTURE = (
    Path(__file__).parent / "fixtures" / "native_pizzlarva_admission_sources.json"
)


class NativeOrderTrialEncounterTests(unittest.TestCase):
    def build_fight(self, policy=None):
        cells = {(0, 0, 0), (1, 0, 0)}
        player = combat_state.Actor(17, 1, (0, 0, 0), 100, 6, 3, 12, 3, 4, True)
        fight = combat_state.Fight(
            77,
            [player],
            cells,
            {1: {(0, 0, 0)}, 0: {(1, 0, 0)}},
            native_order_policy=policy,
        )
        terrain = combat_wire.arena(885, 901, cells, {1: {(0, 0, 0)}, 0: {(1, 0, 0)}})
        return fight, terrain, player

    def policy(self):
        return native_order_trial_encounter.ConstructorPolicy(
            17, 4, 901, 77, "normal", "a" * 64, "b" * 64, 885, 1, 0
        )

    def test_real_one_player_constructor_and_12847_allow_only_typed_empty_team(self):
        fight, terrain, actor = self.build_fight(self.policy())
        packets = combat_bootstrap.placement_messages(
            fight,
            terrain,
            {17: (b"stats", b"effects")},
            terrain_effect_id=46,
            terrain_instance_id=901,
            leaders={1: 17, 0: 0},
        )
        opcode, body = next(
            (opcode, body) for opcode, body in packets if opcode == 12847
        )
        decoded = combat_wire.decode_bootstrap(body)
        self.assertEqual(opcode, 12847)
        self.assertEqual((decoded["myI"], decoded["myJ"]), (0, 17))
        self.assertEqual(
            [(p["actor_id"], p["myn"]) for p in decoded["participants"]], [(17, 1)]
        )
        self.assertTrue(fight.native_order_trial_constructor is not None)

        with self.assertRaisesRegex(ValueError, "both teams"):
            combat_state.Fight(
                78,
                [combat_state.Actor(18, 0, (0, 0, 0), 100, 6, 3, 12, 3, 4, True)],
                {(0, 0, 0), (1, 0, 0)},
                {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
            )

    def test_fight_rejects_malformed_or_foreign_constructor_policy(self):
        for invalid in (
            replace(self.policy(), owner_id=999),
            replace(self.policy(), encounter_id=78),
            replace(self.policy(), mode="entrance"),
            replace(self.policy(), source_sha256="bad"),
        ):
            with self.subTest(policy=invalid):
                with self.assertRaises(ValueError):
                    self.build_fight(invalid)
        with self.assertRaisesRegex(ValueError, "both teams"):
            self.build_fight(None)

    def test_real_native_admission_proof_prepares_constructor_and_registers_current_session(
        self,
    ):
        capability = native_order_trial_admission.document()
        capability[
            "enabled"
        ] = True  # Test-local fixture copy; checked-in profile stays disabled.
        sources = {row["id"]: row for row in json.loads(_FIXTURE.read_text())}
        character = dict(
            id=17, account_id=4, instance_id=901, map_id=885, x=1, y=0, z=0
        )
        source = sources[23620]
        body = struct.pack(">qHH", 23620, 0, 0)
        proof = native_order_trial_admission.plan(
            capability, character, body, native_source=source
        )
        proof = replace(proof, generation="current-lease")
        selected = {"ready_step": "order_trial_ready"}
        context = {
            "configuration": {"fixture": "reviewed context boundary"},
            "policy": selected,
            "completed_steps": {"order_trial_ready"},
        }
        with patch(
            "wakfu_server.native_order_trial_context.policy", return_value=selected
        ):
            constructor = native_order_trial_encounter.prepare_policy(
                proof,
                character,
                77,
                capability=capability,
                context=context,
                native_source=source,
            )
        self.assertEqual(
            (
                constructor.owner_id,
                constructor.account_id,
                constructor.instance_id,
                constructor.encounter_id,
                constructor.mode,
            ),
            (17, 4, 901, 77, "hard"),
        )
        with patch(
            "wakfu_server.native_order_trial_context.policy", return_value=selected
        ):
            with self.assertRaises(ValueError):
                native_order_trial_encounter.prepare_policy(
                    replace(proof, source_sha256="0" * 64),
                    character,
                    77,
                    capability=capability,
                    context=context,
                    native_source=source,
                )

        fight, _terrain, _actor = self.build_fight(constructor)
        session = combat_shared.Session(4, 17, "current-lease", 885, 901)
        registry = combat_shared.Registry(lambda current: current == session)
        shared = registry.register(fight, session)
        self.assertIs(shared.fight, fight)
        self.assertEqual(shared.participants[4], session)
        self.assertIn(17, registry.by_character)

    def test_checkpoint_snapshot_preserves_only_valid_typed_constructor_policy(self):
        fight, _terrain, _actor = self.build_fight(self.policy())
        saved = fight_checkpoint_store.snapshot(fight)
        self.assertEqual(
            saved["native_order_trial_constructor"],
            {
                "owner_id": 17,
                "account_id": 4,
                "instance_id": 901,
                "encounter_id": 77,
                "mode": "normal",
                "source_sha256": "a" * 64,
                "admission_sha256": "b" * 64,
                "map_id": 885,
                "player_team": 1,
                "npc_team": 0,
            },
        )

        ordinary = combat_state.Fight(
            80,
            [
                combat_state.Actor(21, 0, (0, 0, 0), 100, 6, 3, 12, 3, 4, True),
                combat_state.Actor(22, 1, (1, 0, 0), 100, 6, 3, 1, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.assertNotIn(
            "native_order_trial_constructor", fight_checkpoint_store.snapshot(ordinary)
        )

        fight.native_order_trial_constructor = {"owner_id": 17}
        with self.assertRaisesRegex(
            ValueError, "Invalid source-bound order constructor"
        ):
            fight_checkpoint_store.snapshot(fight)

    def test_verified_participant_cells_accept_only_typed_trial_map_scope(self):
        fight, _terrain, actor = self.build_fight(self.policy())
        catalog = {"default_actor_radius": 0, "npc_profiles": {}}
        arena = {
            "map_id": 885,
            "native_environment_participant_footprints": {
                "schema": combat_environment_participant_footprints.SCHEMA,
                "map_id": 885,
                "actors": [
                    {
                        "id": actor.id,
                        "reference": None,
                        "position": list(actor.position),
                        "physical_radius": 0,
                        "source": "native-actor-characteristics.default_actor_radius",
                    }
                ],
            },
        }
        self.assertEqual(
            combat_environment_participant_footprints.verified_participant_cells(
                fight, arena, catalog=catalog
            ),
            {(0, 0)},
        )

        foreign_arena = dict(arena, map_id=886)
        with self.assertRaisesRegex(
            ValueError, "Missing frozen environment participant scope"
        ):
            combat_environment_participant_footprints.verified_participant_cells(
                fight, foreign_arena, catalog=catalog
            )

        ordinary_roles = combat_encounter_roles.EncounterRoles(
            combat_encounter_roles.ORDINARY_POLICY,
            "ordinary-existing-constructor-role-policy",
            885,
            (),
            0,
            1,
        )
        with self.assertRaisesRegex(ValueError, "Unscoped default roles"):
            ordinary_roles.record()

    def test_native_profile_resource_pool_keeps_role_and_native_actor_book_state(self):
        catalog = combat_actor_snapshot.native_actor_catalog()
        profile = combat_actor_snapshot.native_npc_creation_values(
            3217, 1, catalog=catalog
        )
        actor = combat_state.Actor(
            17,
            1,
            (0, 0, 0),
            profile[1]["current"],
            profile[2]["current"],
            profile[3]["current"],
            profile[35]["current"],
            1,
            4,
            False,
            max_hp=profile[1]["maximum"],
        )
        snapshot = combat_actor_snapshot.build_npc_snapshot(
            {"id": 17, "ref": 3217},
            actor,
            wp_current=profile[4]["current"],
            wp_maximum=profile[4]["maximum"],
            running_effects=(),
            catalog=catalog,
        )
        snapshot.install(actor)
        team_before = actor.team
        spell_modifiers_before = actor.spell_ap_cost_modifiers
        combat_actor_snapshot.install_native_profile_resource_pool(
            actor, 3217, 1, catalog=catalog
        )
        self.assertEqual((actor.hp, actor.max_hp), (1, 1))
        self.assertEqual((actor.ap, actor.max_ap), (6, 6))
        self.assertEqual((actor.mp, actor.max_mp), (3, 3))
        self.assertEqual(actor.effect_stats[4], 4)
        from wakfu_server.combat_hp_raw import hp_raw_current
        from wakfu_server.combat_resource_pa_notifications import resource_raw_current

        self.assertEqual(hp_raw_current(actor), 1)
        self.assertEqual(
            (resource_raw_current(actor, 2), resource_raw_current(actor, 3)), (6, 3)
        )
        self.assertEqual(actor.team, team_before)
        self.assertIs(actor.spell_ap_cost_modifiers, spell_modifiers_before)

    def test_spawn_controller_retains_only_the_original_owner_state_once(self):
        fight, _terrain, actor = self.build_fight(self.policy())
        roots = (118957, 118951)
        profile = {"effects": roots, "duration": 5, "realtime_duration": 0}

        class Retention:
            def __init__(self):
                self.fight = fight
                self.calls = []

            def apply_state_reference(
                self, handler, invocation, reference, level, *, carrier_context
            ):
                self.calls.append((invocation, reference, level, carrier_context))
                state = combat_state_ledger.RunningState(
                    7001,
                    reference,
                    level,
                    invocation.caster_id,
                    invocation.target_id,
                    profile["duration"],
                    "caster",
                    False,
                    roots,
                    profile["realtime_duration"],
                    True,
                    None,
                )
                ledger = fight.actors[invocation.target_id].state_ledger
                ledger._entries = (*ledger.entries, state)
                return True

        retention = Retention()
        handler = SimpleNamespace(fight=fight, catalog=object())
        dispatcher = SimpleNamespace(
            native_state_handler=handler, native_retention=retention
        )
        proof = SimpleNamespace(owner_id=17)
        with patch(
            "wakfu_server.combat_definitions.state_profile", return_value=profile
        ) as selected:
            with patch(
                "wakfu_server.combat_native_timing_context.native_time_payload",
                return_value=b"timing",
            ):
                self.assertTrue(
                    native_order_trial_encounter.install_spawn_controller(
                        fight, dispatcher, proof
                    )
                )
                self.assertFalse(
                    native_order_trial_encounter.install_spawn_controller(
                        fight, dispatcher, proof
                    )
                )
        self.assertEqual(
            selected.call_args_list,
            [
                ((handler.catalog, 3044, 1), {}),
                ((handler.catalog, 3044, 1), {}),
            ],
        )
        self.assertEqual(len(retention.calls), 1)
        invocation, reference, level, carrier = retention.calls[0]
        self.assertEqual(
            (invocation.reference, invocation.caster_id, invocation.target_id),
            (2226, 17, 17),
        )
        self.assertEqual((reference, level), (3044, 1))
        self.assertEqual(actor.state_ledger.entries[0].effect_ids, roots)
        self.assertEqual(fight.native_order_spawn_controller["carrier_uid"], 7001)

        other_fight, _terrain, _actor = self.build_fight(self.policy())
        foreign_dispatcher = SimpleNamespace(
            native_state_handler=SimpleNamespace(fight=other_fight, catalog=object()),
            native_retention=SimpleNamespace(fight=fight, apply_state_reference=Mock()),
        )
        with self.assertRaisesRegex(ValueError, "lost its selected fight"):
            native_order_trial_encounter.install_spawn_controller(
                fight, foreign_dispatcher, proof
            )

        with patch(
            "wakfu_server.combat_definitions.state_profile",
            return_value={**profile, "effects": (1, 2)},
        ):
            clean_fight, _terrain, _actor = self.build_fight(self.policy())
            clean_retention = Retention()
            clean_handler = SimpleNamespace(fight=clean_fight, catalog=object())
            clean_retention.fight = clean_fight
            with self.assertRaisesRegex(ValueError, "roots changed"):
                native_order_trial_encounter.install_spawn_controller(
                    clean_fight,
                    SimpleNamespace(
                        native_state_handler=clean_handler,
                        native_retention=clean_retention,
                    ),
                    proof,
                )

    def test_original_3052_marks_hard_mode_only_and_rejects_inherited_normal_flag(self):
        roots = (119030,)
        profile = {"effects": roots, "duration": 5, "realtime_duration": 0}

        class Retention:
            def __init__(self, fight):
                self.fight = fight
                self.calls = []

            def apply_state_reference(
                self, handler, invocation, reference, level, *, carrier_context
            ):
                self.calls.append((invocation, reference, level, carrier_context))
                entry = combat_state_ledger.RunningState(
                    7101,
                    reference,
                    level,
                    invocation.caster_id,
                    invocation.target_id,
                    profile["duration"],
                    "caster",
                    False,
                    roots,
                    profile["realtime_duration"],
                    True,
                    None,
                )
                ledger = self.fight.actors[invocation.target_id].state_ledger
                ledger._entries = (*ledger.entries, entry)
                return True

        hard, _terrain, actor = self.build_fight(replace(self.policy(), mode="hard"))
        hard_proof = SimpleNamespace(owner_id=17, mode="hard")
        hard_retention = Retention(hard)
        handler = SimpleNamespace(fight=hard, catalog=object())
        dispatcher = SimpleNamespace(
            native_state_handler=handler, native_retention=hard_retention
        )
        with patch(
            "wakfu_server.combat_definitions.state_profile", return_value=profile
        ):
            with patch(
                "wakfu_server.combat_native_timing_context.native_time_payload",
                return_value=b"timing",
            ):
                self.assertTrue(
                    native_order_trial_encounter.install_mode_flag(
                        hard, dispatcher, hard_proof
                    )
                )
                self.assertFalse(
                    native_order_trial_encounter.install_mode_flag(
                        hard, dispatcher, hard_proof
                    )
                )
        self.assertEqual(len(hard_retention.calls), 1)
        self.assertEqual(actor.state_ledger.entries[0].reference, 3052)
        self.assertEqual(actor.state_ledger.entries[0].level, 1)
        self.assertEqual(actor.state_ledger.entries[0].effect_ids, roots)
        self.assertEqual(
            hard.native_order_hard_flag, {"owner_id": 17, "carrier_uid": 7101}
        )

        normal, _terrain, normal_actor = self.build_fight(self.policy())
        normal_retention = Retention(normal)
        normal_dispatcher = SimpleNamespace(
            native_state_handler=SimpleNamespace(fight=normal, catalog=object()),
            native_retention=normal_retention,
        )
        self.assertFalse(
            native_order_trial_encounter.install_mode_flag(
                normal, normal_dispatcher, SimpleNamespace(owner_id=17, mode="normal")
            )
        )
        self.assertEqual(normal_actor.state_ledger.entries, ())
        inherited = combat_state_ledger.RunningState(
            7201,
            3052,
            1,
            17,
            17,
            5,
            "caster",
            False,
            roots,
            0,
            True,
            None,
        )
        normal_actor.state_ledger._entries = (inherited,)
        with self.assertRaisesRegex(ValueError, "cannot inherit"):
            native_order_trial_encounter.install_mode_flag(
                normal, normal_dispatcher, SimpleNamespace(owner_id=17, mode="normal")
            )

        changed, _terrain, _actor = self.build_fight(
            replace(self.policy(), mode="hard")
        )
        with patch(
            "wakfu_server.combat_definitions.state_profile",
            return_value={**profile, "effects": (119031,)},
        ):
            with self.assertRaisesRegex(ValueError, "marker changed"):
                native_order_trial_encounter.install_mode_flag(
                    changed,
                    SimpleNamespace(
                        native_state_handler=SimpleNamespace(
                            fight=changed, catalog=object()
                        ),
                        native_retention=Retention(changed),
                    ),
                    hard_proof,
                )
        with self.assertRaisesRegex(ValueError, "selected constructor"):
            native_order_trial_encounter.install_mode_flag(
                hard,
                SimpleNamespace(
                    native_state_handler=SimpleNamespace(fight=changed),
                    native_retention=SimpleNamespace(fight=hard),
                ),
                hard_proof,
            )

    def test_earned_normal_order_completion_closes_only_with_unique_receipt(self):
        from types import SimpleNamespace

        fight, _terrain, _actor = self.build_fight(self.policy())
        fight.phase = "active"
        fight.native_order_trial = {"fixture": "validated by checkpoint boundary"}
        from wakfu_server import (
            native_order_trial_orders,
            native_order_trial_checkpoint,
        )

        fight.native_order_request_policy = native_order_trial_orders.POLICY
        event = fight._event("order_requests_completed", actor_id=17)
        proof = SimpleNamespace(owner_id=17)
        completed = SimpleNamespace(
            hard_mode=False,
            finished=True,
            orders=(),
            receipts=frozenset(
                {
                    f"event:{event['sequence']}:{native_order_trial_checkpoint._digest(event)}"
                }
            ),
        )
        runtime = combat_runtime_messages.RuntimeMessages(fight)
        runtime.pending = [(13510, b"current action acknowledgement")]
        runtime.awaiting_ack = (4, 17, 1)
        runtime.turn_deadline = 100.0
        runtime.deadline_turn = 1
        last_delivery = ((13510, b"action-owned packet"),)
        runtime.last_native_delivery = last_delivery
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=(proof, object(), completed),
        ):
            self.assertTrue(native_order_trial_encounter.finish_normal(fight, runtime))
        self.assertEqual((fight.phase, fight.winner), ("finished", 1))
        self.assertEqual(runtime.pending, [])
        self.assertIsNone(runtime.awaiting_ack)
        self.assertIsNone(runtime.turn_deadline)
        self.assertIsNone(runtime.deadline_turn)
        self.assertEqual(runtime.last_native_delivery, last_delivery)

        for state in (
            SimpleNamespace(
                hard_mode=True, finished=True, orders=(), receipts=completed.receipts
            ),
            SimpleNamespace(
                hard_mode=False, finished=False, orders=(), receipts=completed.receipts
            ),
            SimpleNamespace(
                hard_mode=False,
                finished=True,
                orders=(("red", "cheese"),),
                receipts=completed.receipts,
            ),
        ):
            other, _terrain, _actor = self.build_fight(self.policy())
            other.native_order_trial = object()
            untouched = combat_runtime_messages.RuntimeMessages(other)
            with patch(
                "wakfu_server.native_order_trial_checkpoint.validate",
                return_value=(proof, object(), state),
            ):
                self.assertFalse(
                    native_order_trial_encounter.finish_normal(other, untouched)
                )
            self.assertNotEqual(other.phase, "finished")

        missing, _terrain, _actor = self.build_fight(self.policy())
        missing.native_order_trial = object()
        missing.native_order_request_policy = native_order_trial_orders.POLICY
        missing._event("order_requests_completed", actor_id=17)
        with patch(
            "wakfu_server.native_order_trial_checkpoint.validate",
            return_value=(
                proof,
                object(),
                SimpleNamespace(
                    hard_mode=False, finished=True, orders=(), receipts=frozenset()
                ),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "unique earned request receipt"):
                native_order_trial_encounter.finish_normal(
                    missing, combat_runtime_messages.RuntimeMessages(missing)
                )

    def test_empty_opposition_defers_only_typed_owner_death_and_abandon_winner_list(
        self,
    ):
        fight, _terrain, _actor = self.build_fight(self.policy())
        self.assertTrue(native_order_trial_encounter.defer_victory(fight, {1}))
        plan = combat_death_reconciliation.DeathReconciliationPlan(
            (17,), 17, 1, (17,), frozenset({1})
        )
        combat_death_reconciliation.apply_death_reconciliation(fight, plan)
        self.assertEqual((fight.phase, fight.winner), ("placement", None))

        planned = type(
            "Planned",
            (),
            {
                "fight": fight,
                "_prefix": lambda _self: b"head",
                "_flush": lambda _self: (13000, b"flush"),
            },
        )()
        with patch(
            "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
            return_value=set(),
        ):
            packets = combat_abandon._terminal_packets(planned, losing_team=0)
        self.assertEqual(packets[-1], (13000, b"flush"))
        self.assertEqual(packets[0][0], 12238)

        ordinary = combat_state.Fight(
            79,
            [
                combat_state.Actor(19, 0, (0, 0, 0), 100, 6, 3, 12, 3, 4, True),
                combat_state.Actor(20, 1, (1, 0, 0), 100, 6, 3, 1, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.assertFalse(native_order_trial_encounter.defer_victory(ordinary, {0}))
        self.assertTrue(native_order_trial_encounter.empty_opposition_allowed(fight))
        self.assertFalse(
            native_order_trial_encounter.empty_opposition_allowed(ordinary)
        )


if __name__ == "__main__":
    unittest.main()
