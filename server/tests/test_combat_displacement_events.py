import random
import unittest
from dataclasses import replace
from unittest.mock import patch
import test_combat_displacement as fixture
from wakfu_server.combat_displacement_events import (
    BASE_EVENT_IDS,
    displacement_event_ids,
)
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_native_events import (
    subscription_actor_ids,
    subscription_selection,
)
from wakfu_server.combat_conditions import evaluate_condition
from wakfu_server.combat_native_timing_context import native_definition_timing


class NativeDisplacementMaskTests(unittest.TestCase):
    def test_registry_masks_do_not_fabricate_collision_or_external_events(self):
        for kind, expected in BASE_EVENT_IDS.items():
            effect = dict(effect_class=kind, target_masks=[None] * 7)
            self.assertEqual(displacement_event_ids(effect), expected)
            self.assertNotIn(204, expected)
            self.assertNotIn(1002, expected)
        effect = dict(effect_class=301, target_masks=[None] * 6 + [[2254]])
        self.assertEqual(displacement_event_ids(effect), (0, 185, 188, 2254))


class OrdinaryDisplacementEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.NativeDisplacementTests.setUpClass()

    def setUp(self):
        self.f = fixture.NativeDisplacementTests()
        self.f.setUp()
        f = self.f
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=f.authority,
            cast=ordinary_cast_authority(
                actors=f.authority,
                timing=NativeEffectTimingProvider(f.fixture.states),
                rng=random.Random(1),
                critical=False,
            ),
        )
        factory = NativeEffectRuntimeFactory(
            effects=f.effects,
            state_catalog=f.fixture.states,
            characteristic_registry=f.fixture.registry,
            action_id=1,
            contexts=replace(
                self.adapter.contexts(), selected_surface=f.selected_surface
            ),
            displacement_authority=f.authority,
        )
        self.dispatcher, self.packets = factory(
            f.preview, dict(spell_id=6266, evaluation_level=1)
        )

    def capture(self, invocation):
        seen = []
        original = type(self.dispatcher.replay_event).__call__

        def replay(instance, source, **kwargs):
            seen.append(
                (
                    source.channel,
                    source.manager_actor_id,
                    source.target_id,
                    source.value,
                    source.event_ids,
                    self.f.preview.actors[-7].position,
                )
            )
            return original(instance, source, **kwargs)

        with patch.object(type(self.dispatcher.replay_event), "__call__", replay):
            self.dispatcher.execute(invocation)
        return seen

    def test_native_pull_phase_order_values_and_actual_position(self):
        seen = self.capture(
            EffectInvocation(326111, 1, 7, -7, (0, 0, 0), native_explicit_target=True)
        )
        native = [row for row in seen if row[4] != (2128,)]
        completion = [row for row in seen if row[4] == (2128,)]
        self.assertEqual([row[0] for row in native], [10, 1, 20, 2, 30, 3, 40, 4])
        self.assertEqual([row[3] for row in native], [0, 0, 0, 0, 2, 2, 2, 2])
        self.assertTrue(all(row[4] == (0, 185, 188) for row in native))
        self.assertEqual([row[5] for row in native], [(4, 0, 0)] * 4 + [(2, 0, 0)] * 4)
        # 2128 is a separate server completion policy (reaction state 4801),
        # emitted only after a real move; it does not replace native eVi phases.
        self.assertEqual([row[0] for row in completion], [30, 3])
        self.assertEqual([row[3] for row in completion], [2, 2])
        self.assertEqual(self.f.preview.native_effect_uid_next, 201)

    def test_targetless_teleport_keeps_native_null_target_and_caster_roles(self):
        seen = self.capture(EffectInvocation(349548, 1, 7, None, (2, 2, 0)))
        native = [row for row in seen if row[4] != (2128,)]
        completion = [row for row in seen if row[4] == (2128,)]
        self.assertEqual([row[0] for row in native], [10, 20, 30, 40])
        self.assertTrue(all(row[1] == 7 and row[2] is None for row in native))
        self.assertTrue(all(row[4] == (0, 189, 197) for row in native))
        self.assertEqual([row[0] for row in completion], [30, 3])
        self.assertEqual(completion[0][4], (2128,))
        self.assertEqual(self.f.preview.actors[7].position, (2, 2, 0))

    def test_2128_completion_is_absent_when_native_displacement_does_not_move(self):
        # Catalog target teleport 351394 is valid while selecting its current
        # cell. Native application may produce its normal phases, but movement
        # completion policy 2128 requires an actual position transition.
        self.f.preview.actors[-7].position = (3, 3, 0)
        fixture.install_synthetic_qi_occupancy(self.f.preview)
        seen = self.capture(
            EffectInvocation(351394, 1, 7, -7, (3, 3, 0), native_explicit_target=True)
        )
        self.assertEqual(self.f.preview.actors[-7].position, (3, 3, 0))
        self.assertTrue(any(row[4] != (2128,) for row in seen), seen)
        self.assertFalse(any(row[4] == (2128,) for row in seen), seen)

    def test_original_movement_listener_activates_and_removal_stops_reaction(self):
        # Original eYg353389 is REVERSED and its native Qd5 rebinds the
        # triggering target to the displaced NPC. This fixture's source trace
        # produces caster routes at channels30 and40; the verified selector
        # activates this row on channel30 only. Install on player Qf without
        # changing its native subscription or criteria.
        self.dispatcher.execute(EffectInvocation(353389, 1, 7, 7, (0, 0, 0)))
        groups = self.f.preview.native_owned_group_effects
        listener = next(
            uid
            for uid, row in groups.items()
            if row["invocation"]["reference"] == 353389
        )
        sources = []
        clone_trace = []
        original_replay = type(self.dispatcher.replay_event).__call__
        diagnostics = []
        original_diagnose = self.dispatcher._diagnose

        def replay(instance, source, **kwargs):
            sources.append(source)
            authority = kwargs["authority"]

            def executable(effect, invocation, event_source):
                try:
                    accepted = authority.executable(effect, invocation, event_source)
                except Exception as error:
                    clone_trace.append(
                        ("guard_error", invocation.reference, str(error))
                    )
                    raise
                clone_trace.append(
                    (
                        "guard",
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        accepted,
                    )
                )
                return accepted

            def condition_context(effect, invocation, event_source):
                context = authority.condition_context(effect, invocation, event_source)
                passed = evaluate_condition(effect["criteria"], context)
                clone_trace.append(
                    (
                        "criteria",
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        passed,
                    )
                )
                return context

            kwargs["authority"] = replace(
                authority,
                executable=executable,
                condition_context=condition_context,
            )
            return original_replay(instance, source, **kwargs)

        def diagnose(invocation, **details):
            if invocation.reference in (353389, 353390):
                diagnostics.append((invocation.reference, details))
            return original_diagnose(invocation, **details)

        with patch.object(
            type(self.dispatcher.replay_event), "__call__", replay
        ), patch.object(self.dispatcher, "_diagnose", diagnose):
            self.dispatcher.execute(
                EffectInvocation(
                    326111, 1, 7, -7, (0, 0, 0), native_explicit_target=True
                )
            )

        row = groups[listener]
        listener_entry = next(
            entry
            for entry in self.dispatcher.native_retention.view().entries
            if entry.uid == listener
        )
        definition = self.dispatcher.native_retention.metadata["effects"]["353389"]
        child_effect = self.dispatcher.effects["353390"]
        child_timing = native_definition_timing(child_effect, 1)
        child_definition = self.dispatcher.native_retention.definition(
            child_effect,
            EffectInvocation(353390, 1, 7, -7, (2, 0, 0)),
        )
        selection_trace = []
        for source in sources:
            if source.manager_actor_id != listener_entry.manager_id:
                continue
            action = subscription_selection(
                masks=row["native_subscription_masks"],
                event_ids=source.event_ids,
                channel=source.channel,
                global_subscription=definition["event_global_subscription"],
                reversed_subscription=definition["event_reverse_subscription"],
                flags=row["native_effect_flags"],
                source_present=True,
                source_suppresses_level_one=source.suppresses_level_one,
                source_suppresses_all=source.suppresses_all,
                source_suppressed=source.suppressed,
                source_is_self=source.uid == listener,
                source_parent_is_self=source.source_parent_uid == listener,
            )
            caster, target = subscription_actor_ids(
                target_code=definition["event_target_code"],
                caster_code=definition["event_caster_code"],
                original_caster=row["invocation"]["caster_id"],
                original_target=row["invocation"]["target_id"],
                manager_actor=listener_entry.manager_id,
                source_caster=source.caster_id,
                source_target=source.target_id,
                source_present=True,
            )
            selection_trace.append(
                (source.channel, source.event_ids, action, caster, target)
            )

        def executions():
            matched = 0
            for opcode, body in self.packets:
                for offset in (18, 19):
                    try:
                        fields = _identity_fields(body[offset:])
                    except (ValueError, KeyError, IndexError):
                        continue
                    if fields.get(3) == 353390:
                        matched += 1
                        break
            return matched

        child_packets = []
        for opcode, body in self.packets:
            for offset in (18, 19):
                try:
                    fields = _identity_fields(body[offset:])
                except (ValueError, KeyError):
                    continue
                if fields.get(3) == 353390:
                    child_packets.append((opcode, fields))
                    break
        self.assertIs(definition["subscription"], True)
        # This is a persistent but unsubscribed child. Native aTR cannot retain
        # it as an observer, so its evaluated runner is emitted through eIK=false
        # as 12613 rather than as a child 13497 observer packet.
        self.assertIs(child_definition["subscription"], False)
        self.assertIs(child_timing["retained"], True)
        self.assertIs(child_timing["delay"], False)
        self.assertEqual(
            selection_trace,
            [
                (10, (0, 185, 188), None, 7, -7),
                (20, (0, 185, 188), None, 7, -7),
                (30, (0, 185, 188), "activate", 7, -7),
                (40, (0, 185, 188), None, 7, -7),
                (30, (2128,), None, 7, -7),
            ],
        )
        self.assertTrue(
            any(row[2] == "activate" for row in selection_trace),
            f"listener selection did not activate: {selection_trace!r}",
        )
        self.assertTrue(
            any(
                action == "activate" and caster == 7 and target == -7
                for _, _, action, caster, target in selection_trace
            ),
            f"native Qd5 actor rebinding changed: {selection_trace!r}",
        )
        self.assertTrue(
            child_packets,
            f"listener_uid={listener}; manager={listener_entry.manager_id}; "
            f"flags={row.get('native_effect_flags')!r}; masks={row.get('native_subscription_masks')!r}; "
            f"definition={definition!r}; selection={selection_trace!r}; "
            f"diagnostics={diagnostics!r}; child_packets={child_packets!r}; "
            f"group_packet_count={executions()}",
        )
        signed = lambda value: value - (1 << 64) if value >= (1 << 63) else value
        self.assertEqual([opcode for opcode, _ in child_packets], [12613] * 3)
        child_uids = [fields.get(1, 0) for _, fields in child_packets]
        self.assertTrue(all(uid > listener for uid in child_uids), child_uids)
        self.assertEqual(child_uids, sorted(set(child_uids)))
        self.assertTrue(
            all(
                (
                    fields.get(3),
                    signed(fields.get(6, 0)),
                )
                == (353390, 7)
                for _, fields in child_packets
            ),
            child_packets,
        )
        self.assertEqual(
            {signed(fields.get(7, 0)) for _, fields in child_packets},
            set(self.f.preview.actors),
            child_packets,
        )
        observer_children = []
        for opcode, body in self.packets:
            if opcode != 13497:
                continue
            for offset in (18, 19):
                try:
                    fields = _identity_fields(body[offset:])
                except (ValueError, KeyError, IndexError):
                    continue
                if fields.get(3) == 353390:
                    observer_children.append(fields)
                    break
        self.assertEqual(observer_children, [])
        self.assertTrue(
            any(
                row[0] == "guard" and row[1] == 353389 and row[-1] is True
                for row in clone_trace
            ),
            f"native clone guard did not accept listener: {clone_trace!r}",
        )
        self.assertTrue(
            any(
                row[0] == "criteria" and row[1] == 353389 and row[-1] is True
                for row in clone_trace
            ),
            f"native listener criteria did not pass: {clone_trace!r}",
        )
        self.assertFalse(
            any(
                reference == 353390 and details.get("status") == "skipped_condition"
                for reference, details in diagnostics
            ),
            diagnostics,
        )
        self.dispatcher.native_retention.remove_group(listener)
        previous = executions()
        self.dispatcher.execute(
            EffectInvocation(358000, 1, 7, -7, (2, 0, 0), native_explicit_target=True)
        )
        self.assertEqual(executions(), previous)
