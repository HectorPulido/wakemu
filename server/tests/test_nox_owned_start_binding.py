"""DB-frozen external START reconstruction; no full-fight victory claim."""
from copy import deepcopy
from dataclasses import replace
import json
import psycopg
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase


class NoxOwnedStartBindingTests(PostgresCase):
    def fixture(self):
        from wakfu_server import combat_encounter_owned_start_binding as binding
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_event_replay import NativeExternalEvent
        from wakfu_server.combat_turn_events import TURN_BOUNDARY_POLICY

        for module in (binding, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        assignment = roles.role_assignment(1435, [5664])
        player = SimpleNamespace(
            id=1,
            owner_id=42,
            controlled=True,
            hp=100,
            team=assignment.player_team,
            state_ledger=SimpleNamespace(
                entries=(
                    SimpleNamespace(
                        uid=55,
                        reference=9028,
                        caster_id=-200,
                        target_id=1,
                        effect_ids=(402183,),
                    ),
                )
            ),
        )
        boss = SimpleNamespace(id=-200, controlled=False, team=assignment.npc_team)
        invocation = EffectInvocation(402183, 1, -200, 1, (0, 0, 0), state_uid=55)
        fight = SimpleNamespace(
            phase="placement",
            current=player,
            actors={1: player, -200: boss},
            turn_id=37,
            native_encounter_roles=assignment.record(),
            native_owned_group_effects={
                71: dict(
                    invocation=dict(
                        reference=402183, caster_id=-200, target_id=1, state_uid=55
                    )
                )
            },
            native_npc_initialization_receipts={
                -200: dict(
                    ref=5664, initialized=True, resolved_states=[dict(state_id=8969)]
                )
            },
        )
        binding.freeze_owned_start_binding(fight, roles=assignment)
        fight.phase = "active"
        context = dict(
            policy=TURN_BOUNDARY_POLICY,
            actor_id=1,
            turn_id=37,
            phase="start",
            event_id=1001,
        )
        source = NativeExternalEvent(1, (1001,), 60, turn_boundary_context=context)
        entry = SimpleNamespace(uid=71, manager_id=1, generic_effect=402183)
        effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 402183
        )
        definition = native_catalog.record(
            DATA_ROOT / "native-retained-effect-metadata.json", "effects", 402183
        )
        args = dict(
            entry=entry, original=invocation, definition=definition, effect=effect
        )
        return binding, assignment, fight, source, args

    def test_frozen_native_descriptor_owned_uid_and_checkpoint_once_guard(self):
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )

        binding, assignment, fight, source, args = self.fixture()
        self.assertIsNone(source.uid)
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        # Exercise exactly the production lazy tuple projection, not a hand-
        # normalized fixture. Each preview is private and may be discarded.
        for effect in (args["effect"], ImmutableCatalog(args["effect"])):
            preview = deepcopy(fight)
            with owned_turn_recipient_scope(preview, source.turn_boundary_context):
                self.assertEqual(
                    binding.owned_start_caster(
                        preview, source, **dict(args, effect=effect)
                    ),
                    1,
                )
            self.assertFalse(hasattr(fight, "native_owned_start_caster_deliveries"))
        with self.assertRaises(psycopg.Error):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE encounter_owned_start_binding_versions SET channel=6"
                )
        with owned_turn_recipient_scope(fight, source.turn_boundary_context):
            self.assertEqual(binding.owned_start_caster(fight, source, **args), 1)
            with self.assertRaisesRegex(ValueError, "already consumed"):
                binding.owned_start_caster(fight, source, **args)
        self.assertEqual(
            (args["original"].caster_id, args["original"].target_id), (-200, 1)
        )
        restored = json.loads(json.dumps(fight.native_owned_start_caster_deliveries))
        fight.native_owned_start_caster_deliveries = restored
        with owned_turn_recipient_scope(fight, source.turn_boundary_context):
            with self.assertRaisesRegex(ValueError, "already consumed"):
                binding.owned_start_caster(fight, source, **args)
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_owned_start_binding_active")
        fight.phase = "placement"
        pinned = deepcopy(fight.native_encounter_owned_start_binding)
        self.assertEqual(
            binding.freeze_owned_start_binding(fight, roles=assignment), pinned
        )
        del fight.native_encounter_owned_start_binding
        self.assertIsNone(binding.freeze_owned_start_binding(fight, roles=assignment))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_owned_start_binding_active VALUES "
                "(1435,ARRAY[5664],%s)",
                (pinned["policy"],),
            )
        self.assertIsNone(binding.freeze_owned_start_binding(fight, roles=assignment))

    def test_foreign_boundary_descriptor_carrier_and_tamper_fail_before_publication(
        self,
    ):
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )

        binding, assignment, fight, source, args = self.fixture()
        with self.assertRaisesRegex(ValueError, "Unattested"):
            binding.owned_start_caster(fight, source, **args)
        for changed in (replace(source, channel=6), replace(source, event_ids=(1002,))):
            self.assertIsNone(binding.owned_start_caster(fight, changed, **args))
        with owned_turn_recipient_scope(fight, source.turn_boundary_context):
            self.assertFalse(binding._same_sequence((True,), (1,)))
            self.assertFalse(binding._same_sequence((1,), (1.0,)))
            wrong = dict(args, effect=dict(args["effect"], criteria=""))
            with self.assertRaisesRegex(ValueError, "descriptor changed"):
                binding.owned_start_caster(fight, source, **wrong)
            with self.assertRaisesRegex(ValueError, "actual owned participant"):
                binding.owned_start_caster(
                    fight, replace(source, manager_actor_id=-200), **args
                )
            original = args["original"]
            with self.assertRaisesRegex(ValueError, "carrier state UID"):
                binding.owned_start_caster(
                    fight,
                    source,
                    **dict(args, original=replace(original, state_uid=999))
                )
            fight.native_owned_group_effects[71]["invocation"]["caster_id"] = 999
            with self.assertRaisesRegex(ValueError, "retained listener UID"):
                binding.owned_start_caster(fight, source, **args)
            fight.native_owned_group_effects[71]["invocation"]["caster_id"] = -200
            fight.native_encounter_owned_start_binding["selector_mask"] = True
            with self.assertRaisesRegex(
                ValueError, "Frozen owned START binding changed"
            ):
                binding.owned_start_caster(fight, source, **args)
            fight.native_encounter_owned_start_binding["selector_mask"] = 1
            fight.native_encounter_owned_start_binding["listener_reference"] = 123
            with self.assertRaisesRegex(
                ValueError, "Frozen owned START binding changed"
            ):
                binding.owned_start_caster(fight, source, **args)
        self.assertFalse(hasattr(fight, "native_owned_start_caster_deliveries"))


class NoxOwnedStartReplayHookTests(unittest.TestCase):
    def test_real_replay_binds_clone_and_children_only_and_failed_preview_is_discardable(
        self,
    ):
        from test_combat_event_replay import NativeEventReplayTests
        from wakfu_server import combat_encounter_owned_start_binding as binding
        from wakfu_server.combat_event_replay import NativeExternalEvent
        from wakfu_server.combat_turn_events import TURN_BOUNDARY_POLICY
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )
        from wakfu_server.fight_checkpoint_store import snapshot

        def engine():
            case = NativeEventReplayTests()
            case.setUpClass()
            case.setUp()
            # This is the existing generic native replay fixture, not another
            # Nox encounter. The two PG tests above qualify the real259 guard.
            row = case.fight.native_owned_group_effects[900]
            row["invocation"]["caster_id"] = -7
            row["native_subscription_masks"][5] = [1001]
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
            self.assertEqual(source.turn_boundary_context["actor_id"], 7)
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
                policy=TURN_BOUNDARY_POLICY,
                actor_id=7,
                turn_id=case.fight.turn_id,
                phase="start",
                event_id=1001,
            )
            source = NativeExternalEvent(7, (1001,), 60, turn_boundary_context=context)
            with owned_turn_recipient_scope(case.fight, context), patch.object(
                binding, "owned_start_caster", side_effect=bridge
            ), patch.object(case.dispatcher, "_execute", side_effect=observe):
                return case.replay(source, authority=case.authority)

        replay(canonical)
        self.assertTrue(calls)
        self.assertTrue(executed)
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
