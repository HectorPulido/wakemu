import json
import unittest
from itertools import count
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server import native_catalog


class StatHandlerTests(unittest.TestCase):
    def test_resource_loss_uses_native_raw_oo_overflow_and_removes_owned_delta(self):
        from wakfu_server.combat_resource_pa_notifications import RAW_SOURCE

        actor = self.fight.actors[7]
        actor.effect_stats[2] = actor.ap
        actor.effect_base_maxima = {2: actor.max_ap, 3: actor.max_mp}
        actor.effect_base_minima = {2: 0, 3: 0}
        actor.effect_percentages = {2: 0, 3: 0}
        actor.effect_resource_raw_currents = {2: actor.ap, 3: actor.mp}
        actor.native_resource_raw_current_source = RAW_SOURCE
        # PA.oo uses int32 raw subtraction, unlike an effective-only clamp.
        self.assertTrue(
            self.handler(
                dict(effect_class=37, parameters=[-2147483647, 0]), {}, self.invocation
            )
        )
        self.assertEqual(actor.ap, 0)
        self.assertEqual(actor.effect_resource_raw_currents[2], 0)
        self.assertEqual(self.fight.owned_stat_effects[100]["actual"], 6)
        self.handler.remove(100)
        self.assertEqual((actor.ap, actor.effect_resource_raw_currents[2]), (6, 6))

    def test_runner_callback_reports_clamped_delta_after_application(self):
        from dataclasses import replace
        from wakfu_server.combat_runner_callbacks import runner_value_scope

        seen = []
        with runner_value_scope(
            lambda inv, value: seen.append(
                (value, self.fight.actors[7].effect_stats[20], len(self.packets))
            )
        ) as token:
            self.handler(
                dict(effect_class=120, parameters=[30, 0]),
                {},
                replace(self.invocation, native_value_scope=token),
            )
        self.assertEqual(seen, [(20, 100, 1)])  # Requested30 is not aSg after clamp.

    def test_transferred_stat_gain_retains_and_removes_actual_value(self):
        from dataclasses import replace
        from wakfu_server.combat_value_transfer import transfer_value_context

        invocation = replace(
            self.invocation, native_context_hex=transfer_value_context(b"", 5).hex()
        )
        self.handler(dict(effect_class=120, parameters=[30, 0]), {}, invocation)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 85)
        self.assertEqual(self.fight.owned_stat_effects[100]["actual"], 5)
        messages = {}
        _identity_fields(
            bytes.fromhex(self.fight.owned_stat_effects[100]["payload"]),
            messages=messages,
        )
        self.assertEqual(_identity_fields(messages[8], integer_fields=(25,))[25], 30)
        self.handler.remove(100)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)

    def test_null_runner_transferred_value_does_not_mutate_stats(self):
        from dataclasses import replace
        from wakfu_server.combat_value_transfer import transfer_value_context

        invocation = replace(
            self.invocation, native_context_hex=transfer_value_context(b"", 17).hex()
        )
        self.handler(dict(effect_class=400, parameters=[]), {}, invocation)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)
        self.assertEqual(
            _identity_fields(
                bytes.fromhex(self.fight.owned_stat_effects[100]["payload"])
            )[4],
            17,
        )

    def setUp(self):
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        for a in (pc, npc):
            a.effect_stats = {20: 80, 4: 5}
            a.effect_maxima = {20: 100, 4: 6, 2: 6, 3: 3}
            a.effect_minima = {20: 0, 4: 0, 2: 0, 3: 0}
            a.effect_frozen = frozenset()
        self.registry = json.loads(
            native_catalog.read_text(DATA_ROOT / "effect-characteristic-registry.json")
        )
        self.packets = []
        uids = count(100)
        self.handler = NativeStatHandler(
            self.fight,
            self.packets,
            self.registry,
            action_id=1,
            allocate_uid=lambda: next(uids),
            context=lambda *a: StatExecutionContext(True, True, None, True, None),
        )
        self.invocation = EffectInvocation(
            123, 1, 7, 7, (0, 0, 0), base_uid=90, state_uid=90
        )

    def test_live_runner_l2_percent_and_l3_retirement_preserve_original_request(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from wakfu_server.combat_stat_effects import evaluated_effect_delivery

        for channel_to_change in (2, 3):
            with self.subTest(channel=channel_to_change):
                self.setUp()
                self.handler.rng = lambda: 0.5
                channels, sent = [], []

                def phase(effect, invocation, *, channel, runner_modifier, **kwargs):
                    channels.append(channel)
                    if channel == 1:
                        runner_modifier.mutate(1, 100, False)
                    elif channel == channel_to_change:
                        runner_modifier.mutate(1, 15, False)

                self.handler.event_lifecycle = SimpleNamespace(phase=phase)
                effect = dict(
                    effect_class=120, parameters=[10, 0, 1, 0], target_masks=[None] * 7
                )
                inv = self.handler.prepare(effect, {}, self.invocation)

                def capture(*args, **kwargs):
                    sent.append(_identity_fields(kwargs["running_effect_payload"])[4])
                    return evaluated_effect_delivery(*args, **kwargs)

                with patch(
                    "wakfu_server.combat_current_stat_consumer.evaluated_effect_delivery",
                    side_effect=capture,
                ):
                    self.assertTrue(self.handler(effect, {}, inv))
                actual = 20 if channel_to_change == 2 else 8
                self.assertEqual(self.fight.actors[7].effect_stats[20], 80 + actual)
                self.assertEqual(sent, [actual])
                entry = self.fight.owned_stat_effects[100]
                final = actual if channel_to_change == 2 else actual + 15
                self.assertEqual(entry["actual"], final)
                messages = {}
                fields = _identity_fields(
                    bytes.fromhex(entry["payload"]), messages=messages
                )
                self.assertEqual(fields[4], final)
                self.assertEqual(
                    _identity_fields(messages[8], integer_fields=(25,))[25], 10
                )
                self.assertEqual(channels, [1, 2, 3, 4])
                self.handler.remove(100)
                self.assertEqual(
                    self.fight.actors[7].effect_stats[20], 80 + actual - final
                )
                self.assertFalse(self.handler.current_runner_amounts)
                self.assertFalse(self.handler.prepared_current_stats)

    def test_zero_actual_loss_suppresses_pr_but_gain_preserves_notification(self):
        from types import SimpleNamespace

        for family in (120, 130):
            self.setUp()
            self.handler.rng = lambda: 0.5
            self.fight.actors[7].effect_frozen = frozenset({20})
            channels = []
            self.handler.event_lifecycle = SimpleNamespace(
                phase=lambda effect, invocation, **kwargs: channels.append(
                    kwargs["channel"]
                )
            )
            effect = dict(
                effect_class=family, parameters=[10, 0], target_masks=[None] * 7
            )
            inv = self.handler.prepare(effect, {}, self.invocation)
            self.assertTrue(self.handler(effect, {}, inv))
            self.assertEqual(channels, [1, 2, 3, 4])
            self.assertEqual(self.fight.owned_stat_effects[100]["actual"], 0)
            self.assertEqual(len(self.packets), 1 if family == 120 else 0)
            self.assertEqual(self.fight.actors[7].effect_stats[20], 80)

    def test_direct_and_clone_null_emit_native_masks_once_with_actual_uid(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from wakfu_server.combat_stat_effects import owned_effect_payload
        from wakfu_server.combat_value_transfer import transfer_value_context

        for clone_uid in (None, 777):
            with self.subTest(clone_uid=clone_uid):
                self.setUp()
                if clone_uid is not None:
                    # A cloned eXE listener copies its retained base payload;
                    # make that native source explicit instead of relying on
                    # the test's otherwise empty group-retention registry.
                    payload = owned_effect_payload(
                        uid=90,
                        base_uid=90,
                        generic_effect=self.invocation.reference,
                        caster_id=self.invocation.caster_id,
                        target_id=self.invocation.target_id,
                        value=0,
                        timing_payload=self.handler.context(
                            None, self.invocation
                        ).timing_payload,
                        execution_status=-1,
                        executed=False,
                    )
                    self.fight.native_owned_group_effects[90] = dict(
                        uid=90,
                        base_uid=90,
                        effect_class=400,
                        payload=payload.hex(),
                    )
                seen = []
                self.handler.event_lifecycle = SimpleNamespace(
                    phase=lambda effect, invocation, **kwargs: seen.append(kwargs)
                )
                invocation = replace(
                    self.invocation,
                    native_running_uid=clone_uid,
                    native_context_hex=transfer_value_context(b"", 17).hex(),
                )
                effect = dict(
                    effect_class=400,
                    parameters=[],
                    target_masks=[None] * 6 + [[2177, 2276]],
                )
                self.assertTrue(self.handler(effect, {}, invocation))
                self.assertEqual([x["channel"] for x in seen], [1, 2, 3, 4])
                self.assertEqual(
                    [x["uid"] for x in seen],
                    [100 if clone_uid is None else clone_uid] * 4,
                )
                self.assertEqual([x["value"] for x in seen], [17] * 4)
                self.assertEqual([x["_event_ids"] for x in seen], [(0, 2177, 2276)] * 4)
                self.assertEqual(self.fight.actors[7].effect_stats[20], 80)

    def test_current_stat_events_are_exact_native_prototype_plus_pk_extras(self):
        from types import SimpleNamespace

        self.handler.rng = lambda: 0.5
        seen = []
        self.handler.event_lifecycle = SimpleNamespace(
            phase=lambda effect, invocation, **kwargs: seen.append(kwargs["_event_ids"])
        )
        effect = dict(
            effect_class=193, parameters=[1, 0], target_masks=[None] * 6 + [[3000]]
        )
        inv = self.handler.prepare(effect, {}, self.invocation)
        self.assertTrue(self.handler(effect, {}, inv))
        self.assertEqual(seen, [(0, 67, 3000)] * 4)

    def test_clamped_gain_and_removal_use_actual_delta(self):
        effect = dict(effect_class=120, parameters=[30, 0])
        self.handler(effect, {}, self.invocation)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 100)
        entry = self.fight.owned_stat_effects[100]
        self.assertEqual((entry["actual"], entry["state_uid"]), (20, 90))
        messages = {}
        fields = _identity_fields(bytes.fromhex(entry["payload"]), messages=messages)
        self.assertEqual(fields[4], 20)
        self.assertEqual(
            _identity_fields(messages[8], integer_fields=(12, 25)), {12: 20, 25: 30}
        )
        self.handler.remove(100)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.assertEqual([p[0] for p in self.packets], [12613, 13560])

    def test_wp_and_ap_modify_authoritative_resources(self):
        self.handler(dict(effect_class=193, parameters=[3, 0]), {}, self.invocation)
        self.assertEqual(self.fight.actors[7].effect_stats[4], 6)
        self.fight.actors[7].ap = 2
        self.handler(dict(effect_class=33, parameters=[2, 0]), {}, self.invocation)
        self.assertEqual(self.fight.actors[7].ap, 4)
        self.handler.remove(101)
        self.assertEqual(self.fight.actors[7].ap, 2)

    def test_null400_does_not_change_characteristics(self):
        self.assertTrue(
            self.handler(dict(effect_class=400, parameters=[]), {}, self.invocation)
        )
        self.assertEqual(self.fight.actors[7].effect_stats[20], 80)
        self.assertEqual(self.fight.owned_stat_effects[100]["stat_id"], None)

    def test_resistance_cap_native_stack_refills_and_updates_owned_packet(self):
        actor = self.fight.actors[7]
        actor.effect_stats[27] = 0
        actor.effect_minima[27] = -1000
        actor.effect_maxima[27] = 1000
        for amount in (150, 100):
            self.handler(
                dict(effect_class=90, parameters=[amount, 0]), {}, self.invocation
            )
        self.assertEqual(actor.effect_stats[27], -200)
        self.assertEqual(
            [r["actual"] for r in self.fight.owned_stat_effects.values()], [150, 50]
        )
        self.handler.remove(100)
        self.assertEqual(actor.effect_stats[27], -100)
        remaining = self.fight.owned_stat_effects[101]
        self.assertEqual(remaining["actual"], 100)
        self.assertEqual(_identity_fields(bytes.fromhex(remaining["payload"]))[4], 100)
        self.handler.remove(101)
        self.assertEqual(actor.effect_stats[27], 0)
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.assertEqual([op for op, _ in self.packets], [12613, 12613, 13560, 13560])

    def test_cap_policy_covers_all_native_registered_resistance_actions(self):
        actor = self.fight.actors[7]
        for action in (90, 92, 93, 94, 95):
            stat = self.registry["effects"][str(action)]["fixed_stat_id"]
            actor.effect_stats[stat] = 0
            actor.effect_minima[stat] = -1000
            actor.effect_maxima[stat] = 1000
            for amount in (150, 100):
                self.handler(
                    dict(effect_class=action, parameters=[amount, 0]),
                    {},
                    self.invocation,
                )
            self.assertEqual(actor.effect_stats[stat], -200)
            owned = [
                r
                for r in self.fight.owned_stat_effects.values()
                if r["effect_class"] == action
            ]
            self.assertEqual([r["actual"] for r in owned], [150, 50])
        for uid in tuple(self.fight.owned_stat_effects):
            self.handler.remove(uid)
        for action in (90, 92, 93, 94, 95):
            self.assertEqual(
                actor.effect_stats[
                    self.registry["effects"][str(action)]["fixed_stat_id"]
                ],
                0,
            )

    def test_cap_precedes_value_transfer_and_keeps_original_request(self):
        from dataclasses import replace
        from wakfu_server.combat_value_transfer import transfer_value_context

        actor = self.fight.actors[7]
        actor.effect_stats[27] = 0
        actor.effect_minima[27] = -1000
        actor.effect_maxima[27] = 1000
        self.handler(dict(effect_class=90, parameters=[150, 0]), {}, self.invocation)
        inv = replace(
            self.invocation, native_context_hex=transfer_value_context(b"", 100).hex()
        )
        self.handler(dict(effect_class=90, parameters=[100, 0]), {}, inv)
        # C caps to50; eVt then overrides to100. There is no second cap.
        self.assertEqual(actor.effect_stats[27], -250)
        self.assertEqual(self.fight.owned_stat_effects[101]["actual"], 100)
        messages = {}
        _identity_fields(
            bytes.fromhex(self.fight.owned_stat_effects[101]["payload"]),
            messages=messages,
        )
        self.assertEqual(_identity_fields(messages[8], integer_fields=(25,))[25], 100)
        self.assertFalse(
            self.handler(
                dict(effect_class=90, parameters=[100, 0]), {}, self.invocation
            )
        )
        self.assertEqual(len(self.fight.owned_stat_effects), 2)

    def test_resistance_cap_is_rejected_without_mutation(self):
        with self.assertRaises(ValueError):
            self.handler(dict(effect_class=90, parameters=[30, 0]), {}, self.invocation)
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.owned_stat_effects, {})

    def test_initial_zero_rejects_without_allocating_owned_effect(self):
        self.assertFalse(
            self.handler(dict(effect_class=120, parameters=[0, 0]), {}, self.invocation)
        )
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.handler(dict(effect_class=120, parameters=[1, 0]), {}, self.invocation)
        self.assertIn(100, self.fight.owned_stat_effects)

    def test_clamped_zero_still_records_native_application(self):
        self.fight.actors[7].effect_stats[20] = 100
        self.assertTrue(
            self.handler(
                dict(effect_class=120, parameters=[30, 0]), {}, self.invocation
            )
        )
        self.assertEqual(self.fight.owned_stat_effects[100]["actual"], 0)
        self.assertEqual([packet[0] for packet in self.packets], [12613])
        self.handler.remove(100)
        self.assertEqual(self.fight.actors[7].effect_stats[20], 100)
