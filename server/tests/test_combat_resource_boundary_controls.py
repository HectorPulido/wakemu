"""Boundary policy controls: real timeout/cast and native extra-turn primitive.

The extra-turn test qualifies feq scheduling, not a currently published Xelor
spell granting property37. The original server refill boundary is unproved.
"""
import struct
import unittest

import test_xelor_runtime_pipeline as xelor_helpers
import test_combat_fight_property as property_helpers
import test_combat_state as state_helpers
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_fight_property import NativeFightPropertyHandler
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_stat_handler import StatExecutionContext


class ResourceBoundaryControlTests(unittest.TestCase):
    def test_actual_paid_slowdown_timeout_preserves_victim_budget_once(self):
        helper = xelor_helpers.XelorRuntimePipelineTests()
        data = helper.fixture()
        target_before = data[2].actors[-7].ap
        tx = helper.cast(data, 775, data[2].actors[-7].position)
        data = helper.adopt(data, tx.fight)
        character, monster, fight, deck, rng = data
        target_after = fight.actors[-7].ap
        self.assertLess(target_after, target_before)
        caster_paid = fight.actors[7].ap
        wp_paid = fight.actors[7].effect_stats[4]
        hp_after = fight.actors[-7].hp
        callbacks = []
        now = [0.0]

        def end(preview, **boundary):
            callbacks.append((preview.current.id, preview.current.ap))
            return prepare_server_turn_end(
                character, {-7: monster}, preview, deck, rng=rng, **boundary
            )

        runtime = RuntimeMessages(
            fight,
            clock=lambda: now[0],
            turn_end_provider=end,
            turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                character, {-7: monster}, preview, deck, rng=rng, **boundary
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=rng,
            )[0],
        )
        # The fixture already delivered its native start. Arm the real idle
        # clock without replaying the owned start event or changing authority.
        runtime._arm_turn()
        now[0] = runtime.turn_deadline
        previous_turn = fight.turn_id
        self.assertTrue(runtime.expire_current_once())
        self.assertEqual(callbacks, [(7, caster_paid)])
        self.assertEqual(
            fight.actors[7].effect_stats[4],
            min(fight.actors[7].effect_maxima[4], wp_paid + 3),
        )
        self.assertEqual(fight.actors[-7].hp, hp_after)
        self.assertEqual(runtime.expire_current_once(), [])
        self.assertEqual(len(callbacks), 1)
        runtime.acknowledge_turn(struct.pack(">i", previous_turn))
        self.assertEqual(fight.current.id, -7)
        self.assertEqual(fight.actors[-7].ap, target_after)
        self.assertEqual(fight.actors[7].ap, fight.actors[7].max_ap)

    def test_native_extra_turn_primitive_refills_each_completed_budget(self):
        class TimelineAuthority(property_helpers.Authority):
            property_side_effect = OrdinaryActorAuthority.property_side_effect

        fight = state_helpers.FightStateTests().fight()
        fight.ready(1)
        initial_order = list(fight.order)
        actor = fight.current
        actor.effect_stats = {2: actor.ap, 3: actor.mp}
        actor.effect_minima = {2: 0, 3: 0}
        handler = NativeFightPropertyHandler(
            fight,
            [],
            action_id=3,
            allocate_uid=lambda: 901,
            context=lambda *_: StatExecutionContext(
                True, True, None, True, property_helpers.TIME
            ),
            authority=TimelineAuthority(),
        )
        self.assertTrue(
            handler(
                {"effect_class": 447},
                {"parameters": [37]},
                EffectInvocation(348444, 1, actor.id, actor.id, actor.position),
            )
        )
        self.assertEqual(fight.order, [100, 100, 200])
        for _ in range(2):
            fight.spend(1, 100, ap=2)
            self.assertEqual(actor.ap, 4)
            fight.end_turn(1, 100, actor.turn_count)
            self.assertEqual(actor.ap, 6)
        self.assertEqual(fight.current.id, 200)
        fight.end_server_turn(200, fight.turn_id)
        self.assertEqual(fight.order, initial_order)
        self.assertIsNone(fight.native_base_turn_order)
        self.assertEqual((fight.current.id, fight.current.ap), (100, 6))

    def test_refill_uses_native_ap_mp_notification_order(self):
        # A primitive PA/eWr control. Its source-proved snapshot is supplied by
        # the existing PA fixture; this is not a class gameplay qualification.
        import test_combat_resource_pa_notifications as pa_helpers
        from wakfu_server.combat_resource_pa_notifications import attach_ap_listener

        fight = state_helpers.FightStateTests().fight()
        fight.ready(1)
        actor = fight.current
        _, native_snapshot = pa_helpers.ResourcePANotificationTests().fixture()
        for name, value in vars(native_snapshot).items():
            if name != "id":
                setattr(actor, name, value)
        attach_ap_listener(fight, actor, 99)
        fight.spend(1, actor.id, ap=2)
        self.assertEqual((actor.ap, actor.mp), (4, 1))
        fight.end_turn(1, actor.id, actor.turn_count)
        self.assertEqual((actor.ap, actor.mp), (6, 3))
        self.assertEqual((actor.max_ap, actor.max_mp), (6, 3))
        self.assertEqual(fight.native_resource_pa_listeners[actor.id][0]["rBg"], 0)
