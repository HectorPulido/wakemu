import json, unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import (
    EffectDispatcher,
    EffectInvocation,
    UnsupportedEffectExecution,
)
from wakfu_server.combat_retained_runtime import (
    NativeRetainedRuntime,
    native_retained_condition_effects,
)
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_stat_handler import NativeStatHandler
from wakfu_server.combat_event_replay import (
    NativeEventReplay,
    NativeCloneAuthority,
    NativeTriggerHistory,
    healing_event_source,
)
from wakfu_server.combat_conditions import ConditionActor, ConditionContext
from wakfu_server.combat_healing_effect import direct_healing
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server import native_catalog


class NativeEventReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol/native-event-replay-fixture.json"
            )
        )

    def setUp(self):
        actors = [
            Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1),
        ]
        self.fight = Fight(
            77, actors, {a.position for a in actors}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        # Retained-event callbacks now resolve the real QI population. Build
        # it at the same fresh placement boundary as production, from the
        # fixture's serialized two-cell arena and constructor-assigned slots.
        for actor in actors:
            actor.physical_radius = 0
        self.fight.native_qi_snapshot = dict(
            x=0, y=0, width=2, height=1, cell_masks=[0, 0]
        )
        from wakfu_server.combat_qi_fight import (
            install_fresh_actor_slots,
            prepare_fresh_actor_slots,
        )

        install_fresh_actor_slots(
            self.fight,
            prepare_fresh_actor_slots(
                self.fight,
                physical_radii={actor.id: actor.physical_radius for actor in actors},
            ),
        )
        self.fight.ready(3)
        self.fight.native_effect_uid_next = 900
        self.effects = deepcopy(self.fixture["effects"])
        self.packets = []
        timing = NativeEffectTimingProvider({})
        self.retention = NativeRetainedRuntime(
            self.fight,
            self.packets,
            plan=dict(spell_id=6266, evaluation_level=1),
            state_catalog={},
            action_id=1,
            timing=timing,
            metadata=deepcopy(self.fixture["retained_metadata"]),
        )
        stat = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            allocate_uid=self.fight.allocate_effect_uid,
            context=lambda effect, inv: timing.stat(self.fight, {}, effect, inv),
        )
        self.retention.stat_handler = stat
        self.dispatcher = EffectDispatcher(
            self.effects,
            {400: self.retention.wrap(stat)},
            resolve=lambda effect, inv: (inv,),
            condition_context=lambda inv: self.conditions(),
            probability_accepts=lambda probability, inv: probability == 100,
            group_cells=lambda *args: (),
            actor_position=lambda id: self.fight.actors[id].position,
            group_retention=self.retention,
        )
        self.replay = NativeEventReplay(self.dispatcher, self.retention)
        self.authority = NativeCloneAuthority(
            lambda effect, inv, source: self.fight.actors[inv.target_id].hp > 0,
            lambda effect, inv, source: self.conditions(),
        )
        self.dispatcher.execute(EffectInvocation(308265, 1, 7, 7, (0, 0, 0)))

    def test_external_null_source_preserves_listener_actors_and_allocates_clone(self):
        from wakfu_server.combat_event_replay import NativeExternalEvent

        row = self.fight.native_owned_group_effects[900]
        row["native_subscription_masks"][5] = [1003]
        self.retention.metadata["effects"]["308265"][
            "event_reverse_subscription"
        ] = False
        contexts = []
        activations = []
        registered_container = row["native_retained_container"]
        from wakfu_server.fight_checkpoint_store import snapshot

        import json

        checkpoint = json.loads(json.dumps(snapshot(self.fight)))
        checkpoint_group = checkpoint["native_owned_group_effects"]["900"]
        self.assertEqual(
            checkpoint_group["native_retained_container"], registered_container
        )
        authority = NativeCloneAuthority(
            lambda effect, inv, source: True,
            lambda effect, inv, source: (contexts.append(inv) or self.conditions()),
        )
        execute_activation = self.dispatcher.execute_activation

        def capture_activation(invocation, **kwargs):
            activations.append(invocation.native_retained_container)
            return execute_activation(invocation, **kwargs)

        self.dispatcher.execute_activation = capture_activation
        self.replay(NativeExternalEvent(7, (1003,), 6), authority=authority)
        self.assertTrue(contexts)
        self.assertTrue(all(i.native_trigger_context is None for i in contexts))
        self.assertTrue(all((i.caster_id, i.target_id) == (7, 7) for i in contexts))
        self.assertEqual(activations, [registered_container])
        self.assertEqual(activations[0]["level"], 1)
        self.assertGreater(self.fight.native_effect_uid_next, 901)

    def test_replay_container_rejects_missing_or_mismatched_spell_level_authority(self):
        from dataclasses import replace

        entry = next(item for item in self.retention.view().entries if item.uid == 900)
        row = self.fight.native_owned_group_effects[900]
        invocation = EffectInvocation(**row["invocation"])
        missing = dict(row)
        missing.pop("native_retained_container")
        with self.assertRaisesRegex(ValueError, "Missing retained PL snapshot"):
            self.retention.replay_container(missing, entry, invocation)

        bad_level = dict(row)
        bad_level["native_retained_container"] = dict(
            row["native_retained_container"], level=True
        )
        with self.assertRaisesRegex(ValueError, "Invalid retained spell PL"):
            self.retention.replay_container(bad_level, entry, invocation)

        bad_identity = dict(row)
        bad_identity["native_retained_container"] = dict(
            row["native_retained_container"], id=entry.container_id + 1
        )
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.retention.replay_container(bad_identity, entry, invocation)

        absent = replace(
            entry,
            container_present=False,
            container_type=None,
            container_id=None,
            container_is_spell=None,
            spell_protected=None,
        )
        self.assertEqual(
            self.retention.replay_container(
                {"invocation": row["invocation"]}, absent, invocation
            ),
            {"present": False},
        )

        state_owned = replace(invocation, state_uid=123)
        state_entry = replace(entry, owner_uid=123)
        self.assertIsNone(
            self.retention.replay_container(
                {"native_retained_container": None}, state_entry, state_owned
            )
        )

    def conditions(self):
        actor = ConditionActor(
            retained_effect_ids=frozenset(
                row[0] for row in native_retained_condition_effects(self.fight, 7)
            )
        )
        return ConditionContext({"caster": actor, "target": actor})

    def test_copy_characteristic_activation_forwards_allocated_clone_uid(self):
        # Reuse the fixture's native activation envelope; substitute the runner
        # family to exercise the central eWZ handoff independently of PA maths.
        reference = 359836
        effect = deepcopy(self.effects[str(reference)])
        effect["effect_class"] = 1001
        self.dispatcher.effects[str(reference)] = effect
        calls, allocations = [], []

        def execute(effect, values, invocation):
            calls.append(invocation)
            return True

        self.dispatcher.handlers[1001] = execute

        def allocate():
            allocations.append(902)
            return 902

        invocation = EffectInvocation(reference, 40, 7, 7, (0, 0, 0), base_uid=901)
        self.assertTrue(
            self.dispatcher.execute_activation(
                invocation,
                source=self.source(),
                condition_context=lambda *args: self.conditions(),
                executable=True,
                allocate_uid=allocate,
            )
        )
        self.assertEqual(allocations, [902])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].native_running_uid, 902)
        self.assertEqual(calls[0].base_uid, 901)

    def test_trigger_clone_has_fresh_tree_for_distinct_caster_and_restores_scope(self):
        reference = 359836
        effect = deepcopy(self.effects[str(reference)])
        effect["effect_class"] = 1001
        self.dispatcher.effects[str(reference)] = effect
        history = NativeTriggerHistory()
        calls = []

        def activate(caster):
            key = history.enter(reference, caster, 7)
            if key is None:
                return False
            try:
                return self.dispatcher.execute_activation(
                    EffectInvocation(
                        reference, 40, caster, 7, (0, 0, 0), state_uid=77, base_uid=901
                    ),
                    source=self.source(),
                    condition_context=lambda *args: self.conditions(),
                    executable=True,
                    allocate_uid=self.fight.allocate_effect_uid,
                )
            finally:
                history.leave(key)

        def execute(effect, values, invocation):
            calls.append(invocation.caster_id)
            self.assertFalse(activate(invocation.caster_id))
            if invocation.caster_id == 7:
                self.assertTrue(activate(-7))
            return True

        self.dispatcher.handlers[1001] = execute
        self.assertTrue(activate(7))
        self.assertEqual(calls, [7, -7])
        self.assertEqual(history.active, set())
        self.assertEqual(self.dispatcher._active_execution_keys, ())
        self.assertEqual(self.dispatcher._active_ancestors, ())

    def test_real_feline_impact_400_clone_uses_one_uid_without_server_duplication(
        self,
    ):
        reference = 359836  # Native Impacto Felino 5249 subscription.
        invocation = EffectInvocation(reference, 40, 7, 7, (0, 0, 0))
        self.assertTrue(self.dispatcher.execute(invocation))
        listener_uid = 901
        row = self.fight.native_owned_group_effects[listener_uid]
        self.assertEqual(row["effect_class"], 400)
        original = _identity_fields(bytes.fromhex(row["payload"]))
        self.assertEqual((original[1], original[2]), (901, 901))
        self.assertNotIn(listener_uid, self.fight.owned_stat_effects)
        # Delivery of native subscription event1002, channel6; source IDs are explicit.
        source = replace(self.source(), event_ids=(1002,), channel=60)
        packets_before = len(self.packets)
        self.assertEqual(self.replay(source, authority=self.authority), (True,))
        self.assertEqual(self.fight.native_effect_uid_next, 903)
        self.assertIn(listener_uid, self.fight.native_owned_group_effects)
        self.assertEqual(set(self.fight.owned_stat_effects), set())
        packet = self.packets[packets_before][1]
        # The clone inherits the source runner's retained timing, so the
        # evaluated cvX12613 retains it (eIK=false) without rerunning gameplay.
        import struct

        self.assertEqual(self.packets[packets_before][0], 12613)
        self.assertEqual(packet[12], 0)
        payload_length = struct.unpack_from(">h", packet, 17)[0]
        cloned = _identity_fields(packet[19 : 19 + payload_length])
        self.assertEqual((cloned[1], cloned[2], cloned[3]), (902, 901, reference))

    def test_400_removal_routes_both_retained_listener_and_executed_marker(self):
        self.dispatcher.execute(EffectInvocation(359836, 40, 7, 7, (0, 0, 0)))
        self.dispatcher.execute(EffectInvocation(308267, 1, 7, 7, (0, 0, 0)))
        self.assertIn(901, self.fight.native_owned_group_effects)
        self.assertIn(902, self.fight.owned_stat_effects)
        removal = self.retention.removal(self.retention.view())
        removal.remove((901, 902))
        self.assertNotIn(901, self.fight.native_owned_group_effects)
        self.assertNotIn(902, self.fight.owned_stat_effects)
        self.retention.view()

    def source(self, uid=800):
        reference = self.fixture["source"]
        effect = self.effects[str(reference)]
        invocation = EffectInvocation(reference, 1, 7, 7, (0, 0, 0))
        packet = direct_healing(
            77,
            1,
            uid=uid,
            generic_effect=reference,
            effect_class=25,
            caster_id=7,
            target_id=7,
            restored=1,
        )
        source = healing_event_source(
            effect,
            invocation,
            packet,
            channel=30,
            manager_actor_id=7,
            source_suppressed=False,
            definition_suppresses_level_one=False,
            extra_dynamic_event_ids=(),
        )
        self.assertEqual(
            list(source.event_ids), self.fixture["native_source_event_ids"]
        )
        return source

    def test_real_healing_event_activates_catalog_group_and_child_once(self):
        self.assertEqual(self.replay(self.source(), authority=self.authority), (True,))
        self.assertEqual(
            set(self.fight.native_owned_group_effects), set()
        )  # PK.aZS=1 exhausted; clone never retained.
        self.assertEqual(len(self.fight.owned_stat_effects), 1)
        child = next(iter(self.fight.owned_stat_effects.values()))
        fields = _identity_fields(bytes.fromhex(child["payload"]))
        self.assertEqual(
            (fields[1], fields[2], fields[3]), (child["uid"], child["uid"], 308267)
        )
        self.assertIsNone(child["state_uid"])
        self.assertEqual(self.replay(self.source(801), authority=self.authority), ())
        self.assertEqual(
            len(self.fight.owned_stat_effects), 1
        )  # Real HasEffectWithSpecificId guard.

    def test_recipient_manager_and_suppression_are_not_inferred(self):
        self.assertEqual(
            self.replay(
                replace(self.source(), manager_actor_id=-7), authority=self.authority
            ),
            (),
        )
        self.assertEqual(
            self.replay(
                replace(self.source(), suppressed=True), authority=self.authority
            ),
            (),
        )
        self.assertEqual(self.fight.native_effect_uid_next, 901)

    def test_failed_child_rolls_back_when_preview_is_discarded(self):
        original = deepcopy(self.fight)
        preview = deepcopy(self.fight)
        self.retention.fight = preview
        old = self.dispatcher.handlers[400]
        self.dispatcher.handlers[400] = lambda *args: (_ for _ in ()).throw(
            UnsupportedEffectExecution("Injected child failure")
        )
        with self.assertRaises(UnsupportedEffectExecution):
            self.replay(self.source(), authority=self.authority)
        self.assertEqual(
            self.fight.native_effect_uid_next, original.native_effect_uid_next
        )
        self.assertEqual(
            self.fight.native_retained_records, original.native_retained_records
        )
        self.assertEqual(self.replay.history.active, set())
        self.dispatcher.handlers[400] = old

    def test_native_qj_active_triple_guard_is_released(self):
        history = NativeTriggerHistory()
        key = history.enter(308265, 7, -7)
        self.assertIsNone(history.enter(308265, 7, -7))
        other = history.enter(308265, -7, 7)
        self.assertIsNotNone(other)
        history.leave(key)
        again = history.enter(308265, 7, -7)
        self.assertIsNotNone(again)
        history.leave(again)
        history.leave(other)

    def test_native_qj_history_is_shared_across_nested_replay_instances(self):
        first, nested = NativeTriggerHistory(), NativeTriggerHistory()
        key = first.enter(359737, -7, -7)
        try:
            self.assertIsNone(nested.enter(359737, -7, -7))
            other_target = nested.enter(359737, -7, 7)
            other_effect = nested.enter(359738, -7, -7)
            self.assertIsNotNone(other_target)
            self.assertIsNotNone(other_effect)
            nested.leave(other_effect)
            nested.leave(other_target)
        finally:
            first.leave(key)
        self.assertEqual(nested.active, set())
        again = nested.enter(359737, -7, -7)
        self.assertIsNotNone(again)
        nested.leave(again)

    def test_native_qj_nested_callback_failure_releases_shared_key(self):
        outer, nested = NativeTriggerHistory(), NativeTriggerHistory()
        with self.assertRaisesRegex(RuntimeError, "callback failed"):
            key = outer.enter(359737, -7, -7)
            try:
                self.assertIsNone(nested.enter(359737, -7, -7))
                raise RuntimeError("callback failed")
            finally:
                outer.leave(key)
        self.assertEqual(nested.active, set())
        key = nested.enter(359737, -7, -7)
        self.assertIsNotNone(key)
        nested.leave(key)

    def test_automatic_emitter_replays_real_source_with_applied_packet_identity(self):
        from wakfu_server.combat_event_replay import (
            NativeHealingEventAuthority,
            NativeHealingEventEmitter,
        )

        invocation = EffectInvocation(self.fixture["source"], 1, 7, 7, (0, 0, 0))
        effect = self.effects[str(invocation.reference)]
        packet = direct_healing(
            77,
            1,
            uid=800,
            generic_effect=invocation.reference,
            effect_class=25,
            caster_id=7,
            target_id=7,
            restored=1,
        )
        authority = NativeHealingEventAuthority(
            lambda *args: (self.source(),), self.authority
        )
        emit = NativeHealingEventEmitter(
            self.replay, authority, preview=self.fight, plan={}
        )
        self.assertEqual(emit(effect, invocation, packet), ((True,),))
        self.assertEqual(len(self.fight.owned_stat_effects), 1)
        self.assertEqual(set(self.fight.native_owned_group_effects), set())

    def test_emitter_rejects_foreign_delivery_before_any_clone(self):
        from wakfu_server.combat_event_replay import (
            NativeHealingEventAuthority,
            NativeHealingEventEmitter,
        )

        invocation = EffectInvocation(self.fixture["source"], 1, 7, 7, (0, 0, 0))
        packet = direct_healing(
            77,
            1,
            uid=800,
            generic_effect=invocation.reference,
            effect_class=25,
            caster_id=7,
            target_id=7,
            restored=1,
        )
        authority = NativeHealingEventAuthority(
            lambda *args: (self.source(801),), self.authority
        )
        emit = NativeHealingEventEmitter(
            self.replay, authority, preview=self.fight, plan={}
        )
        with self.assertRaisesRegex(ValueError, "does not belong"):
            emit(self.effects[str(invocation.reference)], invocation, packet)
        self.assertEqual(self.fight.native_effect_uid_next, 901)
        self.assertEqual(self.fight.owned_stat_effects, {})

    def test_probability_rejection_keeps_listener_count_and_uid(self):
        self.dispatcher.probability_accepts = lambda *args: False
        self.assertEqual(self.replay(self.source(), authority=self.authority), (False,))
        self.assertEqual(
            self.fight.native_owned_group_effects[900]["execution_count"], 1
        )
        self.assertEqual(self.fight.native_effect_uid_next, 901)

    def test_listener_depletes_after_accepted_clone_even_when_children_return_false(
        self,
    ):
        self.dispatcher.handlers[400] = lambda *args: False
        self.assertEqual(self.replay(self.source(), authority=self.authority), (False,))
        self.assertEqual(self.fight.native_owned_group_effects, {})
        self.assertEqual(self.fight.native_effect_uid_next, 902)
        self.assertEqual(self.packets[-1][0], 13560)


if __name__ == "__main__":
    unittest.main()
