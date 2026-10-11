"""Instant native state PL objects survive only through actual owned children."""
import unittest
from contextlib import contextmanager

from wakfu_server.combat.combat_state import Actor, Fight
from wakfu_server.combat.combat_state_handler import (
    NativeStateHandler,
    StateCarrierContext,
)
from wakfu_server.combat.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat.combat_native_container import (
    state_container_scope,
    capture_owned_state_container,
    resolve_state_container,
)
from wakfu_server.spell_audit import states_catalog


class InstantStateSubscriptionTests(unittest.TestCase):
    def test_instant_carrier_registers_native_child_and_keeps_only_owned_pl_snapshot(
        self,
    ):
        catalog = states_catalog()
        native = catalog["states"]["2354"]
        self.assertEqual(
            (native["duration_base"], native["realtime_duration_base"]), (0, 0)
        )
        (child_id,) = native["effect_ids"]
        self.assertEqual(catalog["effects"][str(child_id)]["effect_class"], 330)
        self.assertEqual(
            catalog["effects"][str(child_id)]["target_masks"][5], [1033, 1036]
        )
        actor = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        enemy = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        fight = Fight(
            77,
            [actor, enemy],
            {actor.position, enemy.position},
            {0: {actor.position}, 1: {enemy.position}},
        )
        fight.ready(3)
        registered = []

        @contextmanager
        def applied(entry):
            self.assertFalse(entry.retained)
            with state_container_scope(fight, {entry.uid: entry}):
                yield

        def register(invocation):
            entry = resolve_state_container(fight, invocation.state_uid)
            self.assertEqual((entry.reference, entry.level), (2354, 1))
            fight.native_owned_group_effects[501] = dict(state_uid=entry.uid)
            capture_owned_state_container(fight, entry.uid)
            registered.append(invocation)

        packets = []
        handler = NativeStateHandler(
            fight,
            packets,
            catalog,
            action_id=1,
            allocate_uid=lambda: 200,
            execute_child=lambda inv: self.fail("Subscribed child must register"),
            register_subscription=register,
            applied_state_scope=applied,
            context=lambda *args: StateCarrierContext(
                0, 0, False, None, None, False, False, False, 0, None
            ),
        )
        self.assertTrue(
            handler.apply_reference(
                {}, EffectInvocation(2226, 1, 7, 7, actor.position), 2354, 1
            )
        )
        self.assertEqual(actor.state_ledger.entries, ())
        self.assertEqual(fight.state_wire_payloads, {})
        self.assertEqual(packets, [])
        self.assertEqual(len(registered), 1)
        self.assertEqual(resolve_state_container(fight, 200).reference, 2354)
        del fight.native_owned_group_effects[501]
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            resolve_state_container(fight, 200)
