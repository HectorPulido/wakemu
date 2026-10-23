"""DB-frozen external committed movement reconstruction; no full-fight victory claim."""
from copy import deepcopy
from dataclasses import replace
import json
import psycopg
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase


class TalCommittedMovementBindingTests(PostgresCase):
    def fixture(self):
        from wakfu_server import combat_encounter_movement_binding as binding
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_event_replay import NativeExternalEvent
        from wakfu_server.combat_external_movement_recipient import POLICY

        for module in (binding, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        assignment = roles.role_assignment(1400, [5500])
        player = SimpleNamespace(
            id=3, owner_id=42, controlled=True, hp=100, team=assignment.player_team
        )
        boss = SimpleNamespace(
            id=-200,
            controlled=False,
            hp=100,
            team=assignment.npc_team,
            position=(0, 0, 0),
            state_ledger=SimpleNamespace(
                entries=(
                    SimpleNamespace(
                        uid=55,
                        reference=8231,
                        caster_id=3,
                        target_id=-200,
                        effect_ids=(379830,),
                    ),
                )
            ),
        )
        invocation = EffectInvocation(379830, 2, 3, -200, (0, 0, 0), state_uid=55)
        fight = SimpleNamespace(
            phase="placement",
            current=boss,
            actors={3: player, -200: boss},
            turn_id=37,
            walkable={(0, 0, 0), (1, 0, 0)},
            edges=None,
            native_encounter_roles=assignment.record(),
            native_owned_group_effects={
                71: dict(
                    invocation=dict(
                        reference=379830, caster_id=3, target_id=-200, state_uid=55
                    )
                )
            },
            native_npc_initialization_receipts={
                -200: dict(
                    ref=5500, initialized=True, resolved_states=[dict(state_id=8231)]
                )
            },
        )
        binding.freeze_movement_binding(fight, roles=assignment)
        fight.phase = "active"
        context = dict(
            policy=POLICY,
            actor_id=-200,
            turn_id=37,
            action_id=88,
            from_cell=(1, 0, 0),
            to_cell=(0, 0, 0),
            event_id=1005,
        )
        source = NativeExternalEvent(
            -200, (1005,), 60, movement_boundary_context=context
        )
        entry = SimpleNamespace(uid=71, manager_id=-200, generic_effect=379830)
        effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 379830
        )
        definition = native_catalog.record(
            DATA_ROOT / "native-retained-effect-metadata.json", "effects", 379830
        )
        args = dict(
            entry=entry, original=invocation, definition=definition, effect=effect
        )
        return binding, assignment, fight, source, args

    def test_frozen_native_descriptor_owned_uid_and_checkpoint_and_repeated_step_contract(
        self,
    ):
        from wakfu_server.combat_external_movement_recipient import (
            committed_movement_recipient_scope,
        )

        binding, assignment, fight, source, args = self.fixture()
        self.assertIsNone(source.uid)
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        # Exercise exactly the production lazy tuple projection, not a hand-
        # normalized fixture. Each preview is private and may be discarded.
        for effect in (args["effect"], ImmutableCatalog(args["effect"])):
            preview = deepcopy(fight)
            with committed_movement_recipient_scope(
                preview, source.movement_boundary_context
            ):
                self.assertEqual(
                    binding.movement_caster(
                        preview, source, **dict(args, effect=effect)
                    ),
                    -200,
                )
            self.assertFalse(hasattr(fight, "native_movement_caster_deliveries"))
        with self.assertRaises(psycopg.Error):
            with self.store.connection() as db:
                db.execute("UPDATE encounter_movement_binding_versions SET channel=6")
        with committed_movement_recipient_scope(
            fight, source.movement_boundary_context
        ):
            self.assertEqual(binding.movement_caster(fight, source, **args), -200)
            self.assertEqual(binding.movement_caster(fight, source, **args), -200)
            self.assertEqual(len(fight.native_movement_caster_deliveries), 2)
        self.assertEqual(
            (args["original"].caster_id, args["original"].target_id), (3, -200)
        )
        from wakfu_server.combat_native_events import subscription_actor_ids
        from wakfu_server.combat_conditions import (
            ConditionActor,
            ConditionContext,
            evaluate_condition,
        )
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        phase_child = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 380304
        )
        actors = {
            3: ConditionActor(actor_id=3, state_ids=frozenset()),
            -200: ConditionActor(actor_id=-200, state_ids=frozenset((8231, 8243))),
        }
        native_caster, native_target = subscription_actor_ids(
            target_code=2,
            caster_code=2,
            original_caster=3,
            original_target=-200,
            manager_actor=-200,
            source_caster=None,
            source_target=None,
            source_present=False,
        )
        self.assertEqual((native_caster, native_target), (3, -200))
        self.assertFalse(
            evaluate_condition(
                phase_child["criteria"],
                ConditionContext(
                    actors={
                        "caster": actors[native_caster],
                        "target": actors[native_target],
                    }
                ),
            )
        )
        actual_caster = next(iter(fight.native_movement_caster_deliveries.values()))[
            "reconstructed_caster"
        ]
        self.assertTrue(
            evaluate_condition(
                phase_child["criteria"],
                ConditionContext(
                    actors={
                        "caster": actors[actual_caster],
                        "target": actors[native_target],
                    }
                ),
            )
        )
        self.assertEqual(fight.actors[-200].state_ledger.entries[0].caster_id, 3)
        self.assertEqual(
            fight.native_owned_group_effects[71]["invocation"]["caster_id"], 3
        )
        restored = json.loads(json.dumps(fight.native_movement_caster_deliveries))
        fight.native_movement_caster_deliveries = restored
        with committed_movement_recipient_scope(
            fight, source.movement_boundary_context
        ):
            self.assertEqual(binding.movement_caster(fight, source, **args), -200)
            self.assertEqual(len(fight.native_movement_caster_deliveries), 3)
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_movement_binding_active")
        fight.phase = "placement"
        pinned = deepcopy(fight.native_encounter_movement_binding)
        self.assertEqual(
            binding.freeze_movement_binding(fight, roles=assignment), pinned
        )
        del fight.native_encounter_movement_binding
        self.assertIsNone(binding.freeze_movement_binding(fight, roles=assignment))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_movement_binding_active VALUES "
                "(1400,ARRAY[5500],%s)",
                (pinned["policy"],),
            )
        self.assertIsNone(binding.freeze_movement_binding(fight, roles=assignment))

    def test_foreign_boundary_descriptor_carrier_and_tamper_fail_before_publication(
        self,
    ):
        from wakfu_server.combat_external_movement_recipient import (
            committed_movement_recipient_scope,
        )

        binding, assignment, fight, source, args = self.fixture()
        with self.assertRaisesRegex(ValueError, "Unattested"):
            binding.movement_caster(fight, source, **args)
        for changed in (replace(source, channel=6), replace(source, event_ids=(1001,))):
            self.assertIsNone(binding.movement_caster(fight, changed, **args))
        with committed_movement_recipient_scope(
            fight, source.movement_boundary_context
        ):
            self.assertFalse(binding._same_sequence((True,), (1,)))
            self.assertFalse(binding._same_sequence((1,), (1.0,)))
            wrong = dict(args, effect=dict(args["effect"], criteria="tampered"))
            with self.assertRaisesRegex(ValueError, "descriptor changed"):
                binding.movement_caster(fight, source, **wrong)
            with self.assertRaisesRegex(ValueError, "actual native boss"):
                binding.movement_caster(
                    fight, replace(source, manager_actor_id=3), **args
                )
            original = args["original"]
            with self.assertRaisesRegex(ValueError, "carrier state UID"):
                binding.movement_caster(
                    fight,
                    source,
                    **dict(args, original=replace(original, state_uid=999))
                )
            fight.native_owned_group_effects[71]["invocation"]["caster_id"] = 999
            with self.assertRaisesRegex(ValueError, "retained listener UID"):
                binding.movement_caster(fight, source, **args)
            fight.native_owned_group_effects[71]["invocation"]["caster_id"] = 3
            fight.native_encounter_movement_binding["selector_mask"] = True
            with self.assertRaisesRegex(
                ValueError, "Frozen committed movement binding changed"
            ):
                binding.movement_caster(fight, source, **args)
            fight.native_encounter_movement_binding["selector_mask"] = 1
            fight.native_encounter_movement_binding["listener_reference"] = 123
            with self.assertRaisesRegex(
                ValueError, "Frozen committed movement binding changed"
            ):
                binding.movement_caster(fight, source, **args)
        self.assertFalse(hasattr(fight, "native_movement_caster_deliveries"))


class TalCommittedMovementReplayHookTests(unittest.TestCase):
    def test_real_replay_binds_clone_and_children_only_and_failed_preview_is_discardable(
        self,
    ):
        from test_combat_event_replay import NativeEventReplayTests
        from wakfu_server import combat_encounter_movement_binding as binding
        from wakfu_server.combat_event_replay import NativeExternalEvent
        from wakfu_server.combat_external_movement_recipient import POLICY
        from wakfu_server.combat_external_movement_recipient import (
            committed_movement_recipient_scope,
        )
        from wakfu_server.fight_checkpoint_store import snapshot

        def engine():
            case = NativeEventReplayTests()
            case.setUpClass()
            case.setUp()
            # This is the existing generic native replay fixture, not another
            # Tal encounter. The two PG tests above qualify the real262 guard.
            row = case.fight.native_owned_group_effects[900]
            row["invocation"]["caster_id"] = -7
            row["native_subscription_masks"][5] = [1005]
            case.retention.metadata["effects"]["308265"][
                "event_reverse_subscription"
            ] = True
            case.effects["308265"]["criteria"] = "1 == 1"
            return case

        canonical = engine()
        retained_original = canonical.fight.native_owned_group_effects[900]
        before = deepcopy(retained_original["invocation"])
        calls, executed = [], []

        def bridge(fight, source, **kwargs):
            calls.append((source, kwargs))
            self.assertIsNone(source.uid)
            self.assertEqual(source.channel, 60)
            self.assertEqual(source.movement_boundary_context["actor_id"], 7)
            self.assertEqual(
                (kwargs["original"].caster_id, kwargs["original"].target_id), (-7, 7)
            )
            return 7  # Binding decision only; real guard is covered above.

        def replay(case, *, fail=False):
            execute = case.dispatcher._execute

            def observe(invocation, **kwargs):
                if invocation.reference != 308265:
                    executed.append(invocation)
                    if fail:
                        raise RuntimeError("qualifying native child failure")
                return execute(invocation, **kwargs)

            context = dict(
                policy=POLICY,
                actor_id=7,
                turn_id=case.fight.turn_id,
                action_id=88,
                from_cell=(1, 0, 0),
                to_cell=(0, 0, 0),
                event_id=1005,
            )
            source = NativeExternalEvent(
                7, (1005,), 60, movement_boundary_context=context
            )
            with committed_movement_recipient_scope(case.fight, context), patch.object(
                binding, "movement_caster", side_effect=bridge
            ), patch.object(case.dispatcher, "_execute", side_effect=observe):
                return case.replay(source, authority=case.authority)

        replay(canonical)
        self.assertTrue(calls)
        self.assertTrue(executed)
        from wakfu_server.combat_conditions import (
            ConditionActor,
            ConditionContext,
            evaluate_condition,
        )
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        phase_child = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 380304
        )
        for invocation in executed:
            self.assertTrue(
                evaluate_condition(
                    phase_child["criteria"],
                    ConditionContext(
                        actors={
                            "caster": ConditionActor(
                                actor_id=invocation.caster_id,
                                state_ids=frozenset((8243,))
                                if invocation.caster_id == 7
                                else frozenset(),
                            ),
                            "target": ConditionActor(
                                actor_id=invocation.target_id,
                                state_ids=frozenset((8243,))
                                if invocation.target_id == 7
                                else frozenset(),
                            ),
                        }
                    ),
                )
            )
        self.assertTrue(
            all(
                (inv.caster_id, inv.target_id) == (7, 7)
                and inv.native_trigger_context is None
                for inv in executed
            )
        )
        # The generic fixture may naturally consume its one-shot listener.
        # Its retained invocation itself must still preserve original actors.
        self.assertEqual(retained_original["invocation"], before)
        stable = snapshot(canonical.fight)
        preview = engine()
        executed.clear()
        with self.assertRaisesRegex(RuntimeError, "native child failure"):
            replay(preview, fail=True)
        self.assertTrue(executed)
        self.assertTrue(
            all(
                (inv.caster_id, inv.target_id) == (7, 7)
                and inv.native_trigger_context is None
                for inv in executed
            )
        )
        self.assertEqual(retained_original["invocation"], before)
        self.assertEqual(snapshot(canonical.fight), stable)
