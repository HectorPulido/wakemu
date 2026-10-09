import unittest
from types import SimpleNamespace
from wakfu_server.combat_aura_removal import aura_removal_snapshot, remove_native_auras
from wakfu_server.combat_retained_effects import (
    NativeRetainedEffectView,
    NativeRetainedRemoval,
    RetainedEffect,
)


class AuraRemovalTests(unittest.TestCase):
    def fixture(self):
        # Keep the actual view/removal types while isolating population setup;
        # complete production ownership is covered by central runtime tests.
        view = object.__new__(NativeRetainedEffectView)
        view.fight = SimpleNamespace()
        view.entries = tuple(
            RetainedEffect(
                uid,
                7,
                family,
                100 + uid,
                manager_id=manager,
                definition_dispellable=False,
            )
            for uid, family, manager in (
                (1, 338, 7),
                (2, 310, 7),
                (3, 314, 8),
                (4, 314, 7),
            )
        )
        view.by_uid = {entry.uid: entry for entry in view.entries}
        return view

    def test_actual_family_pair_and_owning_qf_subsequence(self):
        view = self.fixture()
        self.assertEqual(aura_removal_snapshot(view, 7), (1, 4))
        self.assertEqual(aura_removal_snapshot(view, 8), (3,))

    def test_snapshot_removes_in_order_without_dispellability_gate(self):
        view = self.fixture()
        removal = NativeRetainedRemoval(view)
        live = {1, 4}
        removed = []
        for family in (314, 338):
            removal.register(
                family,
                exists=lambda uid: uid in live,
                validate=lambda entry: None,
                remove=lambda uid: (removed.append(uid), live.remove(uid)),
            )
        result = remove_native_auras(view, removal, 7)
        self.assertEqual(tuple(entry.uid for entry in result), (1, 4))
        self.assertEqual(removed, [1, 4])

    def test_missing_second_family_rejects_before_first_mutation(self):
        view = self.fixture()
        removal = NativeRetainedRemoval(view)
        removed = []
        removal.register(
            338,
            exists=lambda uid: True,
            validate=lambda entry: None,
            remove=removed.append,
        )
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            remove_native_auras(view, removal, 7)
        self.assertEqual(removed, [])


class AuraRemovalRunnerTests(unittest.TestCase):
    fixture = AuraRemovalTests.fixture

    def test_actual_handler_phases_remove_snapshot_before_application_and_register_before_l3(
        self,
    ):
        from random import Random
        from wakfu_server.combat_aura_removal import NativeAuraRemovalHandler
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_execution_context import constructed_execution_context

        view = self.fixture()
        fight = view.fight
        fight.id, fight.phase = 12, "active"
        fight.actors, fight.owned_stat_effects = {7: SimpleNamespace()}, {}
        removal = NativeRetainedRemoval(view)
        live, order = {1, 4}, []
        for family in (314, 338):
            removal.register(
                family,
                exists=lambda uid: uid in live,
                validate=lambda entry: None,
                remove=lambda uid: (order.append(("remove", uid)), live.remove(uid)),
            )
        retention = SimpleNamespace(
            view=lambda: view,
            removal=lambda current: removal,
            container=lambda invocation: ({"container_type": 1}, 555),
            register_applied_stat=lambda effect, invocation, uid: order.append(
                ("register", uid)
            ),
        )
        handler = NativeAuraRemovalHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 55,
            context=lambda effect, invocation: StatExecutionContext(
                True, True, None, True, b""
            ),
            retention=retention,
            rng=Random(1).random,
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda effect, invocation, **kwargs: order.append(
                ("phase", kwargs["channel"])
            )
        )
        invocation = EffectInvocation(
            100,
            1,
            8,
            7,
            (0, 0, 0),
            native_context_hex=constructed_execution_context().payload().hex(),
        )
        self.assertTrue(
            handler(
                dict(effect_class=316, target_masks=[None] * 7),
                dict(parameters=[]),
                invocation,
            )
        )
        self.assertEqual(
            order,
            [
                ("phase", 1),
                ("phase", 2),
                ("remove", 1),
                ("remove", 4),
                ("register", 55),
                ("phase", 3),
                ("phase", 4),
            ],
        )
        self.assertEqual(handler.packets[0][0], 13497)
        self.assertEqual(fight.owned_stat_effects[55]["family"], "eZF")
        self.assertEqual(handler.prepared, {})
