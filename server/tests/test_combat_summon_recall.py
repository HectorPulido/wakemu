"""Bounded eWz/eWA source contract tests; no spell catalogs or services."""
import unittest
from types import SimpleNamespace
from wakfu_server.characters.captured_roster import OwnedCapturedRoster
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_summon_recall import (
    NativeSummonRecallHandler,
    _symbiote_owner_and_target,
)
from wakfu_server.combat_pr_completion import (
    PRCompletionWatcher,
    WakemuPRCompletionPolicy,
    fresh_pr_completion_authority,
)
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    global_fighter_registered,
    global_fighter_guards,
)
from copy import deepcopy


class NativeSummonRecallTests(unittest.TestCase):
    def fixture(
        self,
        *,
        hp_minimum=5,
        source_owner=7,
        target_owner=7,
        roster=True,
        executable=True
    ):
        owner = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 20, 3, True)
        target = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 8, 20)
        target.native_controller_id = target_owner
        fight = Fight(
            77,
            [owner, target],
            {owner.position, target.position},
            {0: {owner.position}, 1: {target.position}},
        )
        fight.ready(3)
        fight.native_pr_completion_authority = fresh_pr_completion_authority()
        target.hp = target.effect_stats_hp = 80
        target.effect_stats = {1: 80, 14: 8}
        target.effect_minima = {1: hp_minimum, 14: 0}
        target.effect_maxima = {1: 100, 14: 20}
        target.effect_base_minima = dict(target.effect_minima)
        target.effect_base_maxima = dict(target.effect_maxima)
        target.effect_percentages = {1: 0, 14: 0}
        target.effect_frozen = frozenset()
        owner_meta = SimpleNamespace(
            targeting={"is_eGj": True, "dpu_id": source_owner, "dpr_id": source_owner},
            native_is_ehp=True,
            native_captured_roster=OwnedCapturedRoster(owner.id) if roster else None,
            native_controller_id=owner.id,
        )
        target_meta = SimpleNamespace(
            targeting={"is_eGj": True, "dpu_id": target_owner, "dpr_id": target_owner},
            native_is_ehp=None,
            native_captured_roster=None,
            native_controller_id=target_owner,
        )

        def actor_authority(_, actor):
            return owner_meta if actor.id == owner.id else target_meta

        counts = {65: 2, 66: 1, 19: 2, 12: 1, 6: 1}
        authority = SimpleNamespace(property_counts=lambda _fight, _actor: dict(counts))
        packets, phases = [], []
        handler = NativeSummonRecallHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=lambda: 101,
            context=lambda *_: StatExecutionContext(
                executable, True, None, False, b"", None
            ),
            rng=lambda: 0,
            authority=authority,
            actor_authority=actor_authority,
        )

        class Events:
            def phase(self, effect, invocation, **kwargs):
                phases.append(kwargs["channel"])

            def register_applied(self, *_):
                raise AssertionError("eWA is not a retained stat effect")

        handler.event_lifecycle = Events()
        effect = dict(effect_class=859, target_masks=[[] for _ in range(7)])
        invocation = EffectInvocation(12345, 20, owner.id, target.id, target.position)
        return fight, owner, target, packets, phases, handler, effect, invocation

    def test_recall_clears_one_each_property_and_applies_hp_minimum_and_ko_max_zero(
        self,
    ):
        (
            fight,
            owner,
            target,
            packets,
            phases,
            handler,
            effect,
            invocation,
        ) = self.fixture()
        invocation = handler.prepare(effect, {}, invocation)
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual((target.hp, target.effect_stats[1]), (5, 5))
        self.assertEqual(
            (
                target.effect_base_maxima[14],
                target.effect_maxima[14],
                target.effect_stats[14],
            ),
            (0, 0, 0),
        )
        self.assertEqual(target.native_fight_property_counts, {65: 1, 19: 1, 6: 1})
        self.assertEqual(phases, [1, 2, 3, 4])
        self.assertEqual([packet[0] for packet in packets], [12613])
        self.assertEqual(
            fight.native_pr_completion_authority["completed"],
            [
                {
                    "running_uid": 101,
                    "parent_uid": None,
                    "effect_reference": 12345,
                    "effect_class": 859,
                    "caster_id": owner.id,
                    "target_id": target.id,
                    "native_parent_index": None,
                }
            ],
        )
        self.assertFalse(
            any(event["kind"].startswith("summon_recall_") for event in fight.events)
        )
        # eWA doesn't call eHU/QI/fdt/global-PV removers or free a captured slot.
        self.assertEqual(owner.id, target.native_controller_id)
        self.assertFalse(hasattr(fight, "native_pve_departures"))

    def test_recall_hp_minimum_updates_a_proven_fresh_raw_current(self):
        fight, _, target, _, _, handler, effect, invocation = self.fixture(hp_minimum=0)
        from wakfu_server.combat_hp_raw import (
            SOURCE as HP_RAW_SOURCE,
            hp_raw_current,
            install_fresh_hp_operand,
        )

        install_fresh_hp_operand(
            target,
            dict(
                producer=HP_RAW_SOURCE,
                actor_id=target.id,
                raw_current=80,
            ),
        )
        self.assertEqual(hp_raw_current(target), 80)
        invocation = handler.prepare(effect, {}, invocation)

        self.assertTrue(handler(effect, {}, invocation))

        self.assertEqual((target.hp, hp_raw_current(target)), (0, 0))

    def test_missing_symbiote_component_or_wrong_direct_controller_rejects_atomically(
        self,
    ):
        for changes, message in (
            ({"roster": False}, "eHP.drI"),
            ({"target_owner": 8}, "target.dpr"),
        ):
            fight, _, target, packets, _, handler, effect, invocation = self.fixture(
                **changes
            )
            before = (target.hp, dict(target.effect_stats), dict(target.effect_maxima))
            with self.assertRaisesRegex(ValueError, message):
                handler(effect, {}, handler.prepare(effect, {}, invocation))
            self.assertEqual(
                before, (target.hp, target.effect_stats, target.effect_maxima)
            )
            self.assertEqual(packets, [])

    def test_native_nonexecution_does_not_change_target_or_emit_application(self):
        fight, _, target, packets, _, handler, effect, invocation = self.fixture(
            executable=False
        )
        before = (target.hp, dict(target.effect_stats), dict(target.effect_maxima))
        invocation = handler.prepare(effect, {}, invocation)
        self.assertFalse(handler(effect, {}, invocation))
        self.assertEqual(before, (target.hp, target.effect_stats, target.effect_maxima))
        self.assertEqual(packets, [])

    def test_pr_completion_watchers_run_after_properties_before_hp_and_ko(self):
        fight, owner, target, packets, _, handler, effect, invocation = self.fixture()
        observed = []

        def observe(slot):
            def observer(notice):
                observed.append(
                    (
                        slot,
                        notice,
                        dict(target.native_fight_property_counts),
                        target.hp,
                        target.effect_stats[14],
                        target.effect_maxima[14],
                    )
                )

            return observer

        fight.native_pr_completion_authority["watchers"].append(
            PRCompletionWatcher(on_i=observe("i"), on_j=observe("j"))
        )
        invocation = handler.prepare(effect, {}, invocation)
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual([row[0] for row in observed], ["i", "j"])
        _, notice, properties, hp_before, ko_before, ko_maximum_before = observed[0]
        self.assertIs(observed[0][1], observed[1][1])
        self.assertEqual(notice.running_uid, 101)
        self.assertIsNone(notice.parent_uid)
        self.assertEqual(notice.effect_reference, 12345)
        self.assertEqual(properties, {65: 1, 19: 1, 6: 1})
        self.assertEqual((hp_before, ko_before, ko_maximum_before), (80, 8, 20))
        self.assertEqual((target.hp, target.effect_stats[14]), (5, 0))

    def test_pr_callback_failure_keeps_original_fight_and_private_outbox_uncommitted(
        self,
    ):
        original, _, _, _, _, _, effect, invocation = self.fixture()
        preview = deepcopy(original)
        target = preview.actors[invocation.target_id]
        packets, phases = [], []
        handler = NativeSummonRecallHandler(
            preview,
            packets,
            action_id=5,
            allocate_uid=lambda: 101,
            context=lambda *_: StatExecutionContext(True, True, None, False, b"", None),
            rng=lambda: 0,
            authority=SimpleNamespace(
                property_counts=lambda _fight, _actor: {65: 1, 66: 1, 19: 1, 12: 1}
            ),
            actor_authority=lambda _fight, actor: SimpleNamespace(
                targeting={
                    "is_eGj": True,
                    "dpu_id": 7 if actor.id == -7 else 7,
                    "dpr_id": 7 if actor.id == -7 else 7,
                },
                native_is_ehp=actor.id == 7,
                native_captured_roster=OwnedCapturedRoster(7)
                if actor.id == 7
                else None,
                native_controller_id=actor.id if actor.id == 7 else 7,
            ),
        )

        def fail(_notice):
            raise RuntimeError("observer failed")

        preview.native_pr_completion_authority["watchers"].append(
            PRCompletionWatcher(on_i=fail)
        )
        before_original = (
            original.actors[-7].hp,
            getattr(original.actors[-7], "native_fight_property_counts", None),
        )
        with self.assertRaisesRegex(RuntimeError, "observer failed"):
            handler(effect, {}, invocation)
        self.assertEqual(packets, [])
        self.assertEqual(
            (
                original.actors[-7].hp,
                getattr(original.actors[-7], "native_fight_property_counts", None),
            ),
            before_original,
        )
        self.assertEqual((target.hp, target.effect_stats[1]), (80, 80))

    def test_hp_minimum_death_keeps_fighter_registered_off_play(self):
        fight, owner, target, packets, _, handler, effect, invocation = self.fixture(
            hp_minimum=0
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        invocation = handler.prepare(effect, {}, invocation)
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(target.hp, 0)
        self.assertTrue(global_fighter_registered(fight, target.id))
        self.assertEqual(
            global_fighter_guards(fight, target.id),
            {"baF": False, "baG": True, "baK": False},
        )


class WakemuPRCompletionPolicyTests(unittest.TestCase):
    def test_unknown_or_malformed_watcher_authority_rejects(self):
        with self.assertRaisesRegex(
            ValueError, "Unknown Wakemu PR notification policy"
        ):
            WakemuPRCompletionPolicy(
                {"source": "restored-unknown", "watchers": [], "completed": []}
            )
        authority = fresh_pr_completion_authority()
        authority["watchers"].append(object())
        policy = WakemuPRCompletionPolicy(authority)
        from wakfu_server.combat_pr_completion import PRCompletionNotice

        notice = PRCompletionNotice(1, None, 2, 859, 7, -7)
        with self.assertRaisesRegex(ValueError, "Unknown Wakemu PR watcher"):
            policy.notify(notice)
        self.assertEqual(authority["completed"], [])


if __name__ == "__main__":
    unittest.main()
