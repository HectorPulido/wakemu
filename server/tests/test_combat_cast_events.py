import unittest
from copy import deepcopy
from types import SimpleNamespace
from wakfu_server.combat_active_spell import active_spell_id, active_spell_scope
from wakfu_server.combat_cast_events import cast_event_scope
from wakfu_server.combat_conditions import ConditionContext, evaluate_condition
from wakfu_server.combat_global_pv_collections import (
    global_pv_iterator,
    initialize_global_pv_collections,
)
from wakfu_server.combat_native_events import subscription_selection


class CastEventsTests(unittest.TestCase):
    def fixture(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7), -7: SimpleNamespace(id=-7)},
            native_active_spell_id=None,
            native_effect_areas={},
            native_owned_group_effects={},
        )
        initialize_global_pv_collections(fight, (7, -7))
        seen = []
        retention = SimpleNamespace(fight=fight)

        def replay(event, **kwargs):
            event.validate()
            seen.append(
                (
                    event.event_ids[0],
                    event.channel,
                    event.manager_actor_id,
                    active_spell_id(fight),
                )
            )
            self.assertIsNone(event.uid)
            self.assertIsNone(event.caster_id)
            self.assertIsNone(event.target_id)
            return (True,)

        dispatcher = SimpleNamespace(
            native_retention=retention,
            native_clone_authority=object(),
            replay_event=replay,
        )
        plan = dict(actor_id=7, spell_id=4820, evaluation_level=200)
        return fight, dispatcher, plan, seen

    def test_before_and_success_after_keep_current_spell_and_native_global_order(self):
        fight, dispatcher, plan, seen = self.fixture()
        expected = [(6, 7), (60, 7)] + [
            (61, identity) for identity in global_pv_iterator(fight, caster_id=7)
        ]
        with active_spell_scope(fight, 4820, level=200), cast_event_scope(
            dispatcher, plan
        ):
            seen.append(("roots", active_spell_id(fight)))
        self.assertEqual(
            seen,
            [(1024, channel, identity, 4820) for channel, identity in expected]
            + [("roots", 4820)]
            + [(1025, channel, identity, 4820) for channel, identity in expected],
        )
        self.assertEqual(active_spell_id(fight), -1)

    def test_callback_failure_and_root_failure_do_not_deliver_success_after(self):
        for fail_before in (False, True):
            fight, dispatcher, plan, seen = self.fixture()
            if fail_before:

                def fail(event, **kwargs):
                    seen.append(event.event_ids[0])
                    raise ValueError("class callback failed")

                dispatcher.replay_event = fail
            with self.assertRaises(ValueError):
                with active_spell_scope(fight, 4820, level=200), cast_event_scope(
                    dispatcher, plan
                ):
                    raise ValueError("native root failed")
            self.assertFalse(
                any(
                    (item == 1025 or isinstance(item, tuple) and item[0] == 1025)
                    for item in seen
                )
            )
            self.assertEqual(active_spell_id(fight), -1)

    def test_nested_cast_keeps_separate_active_spell_boundaries(self):
        fight, dispatcher, plan, seen = self.fixture()
        child = dict(actor_id=7, spell_id=4810, evaluation_level=100)
        with active_spell_scope(fight, 4820, level=200), cast_event_scope(
            dispatcher, plan
        ):
            with active_spell_scope(fight, 4810, level=100), cast_event_scope(
                dispatcher, child, origin="nested"
            ):
                self.assertEqual(active_spell_id(fight), 4810)
            self.assertEqual(active_spell_id(fight), 4820)
        self.assertEqual(
            [(row[0], row[3]) for row in seen if row[1] == 6],
            [(1024, 4820), (1024, 4810), (1025, 4810), (1025, 4820)],
        )

    def test_mismatched_active_container_and_unknown_origin_reject_before_events(self):
        fight, dispatcher, plan, seen = self.fixture()
        with active_spell_scope(fight, 4820, level=1):
            with self.assertRaises(ValueError):
                with cast_event_scope(dispatcher, plan):
                    pass
        with self.assertRaises(ValueError):
            with cast_event_scope(dispatcher, plan, origin="restore"):
                pass
        self.assertEqual(seen, [])

    def test_native_external_masks_route_local_reverse_global_without_source(self):
        for global_subscription, reversed_subscription, accepted in (
            (False, False, 6),
            (False, True, 60),
            (True, False, 61),
        ):
            actual = [
                channel
                for channel in (6, 60, 61)
                if subscription_selection(
                    masks=[None] * 5 + [[1025], None],
                    event_ids=(1025,),
                    channel=channel,
                    global_subscription=global_subscription,
                    reversed_subscription=reversed_subscription,
                    flags=[],
                    source_present=False,
                )
                == "activate"
            ]
            self.assertEqual(actual, [accepted])

    def test_original_cra_active_spell_branches_see_after_boundary_context(self):
        # Original 350554 -> 352071/352075 eligibility, without criterion overrides.
        first = "GetActiveSpellId() == 4816 or GetActiveSpellId() == 4809 or GetActiveSpellId() == 4820"
        second = "GetActiveSpellId() == 4811 or GetActiveSpellId() == 4817 or GetActiveSpellId() == 4810 or GetActiveSpellId() == 4821 or GetActiveSpellId() == 4818"
        for spell, expected in (
            (4820, (True, False)),
            (4810, (False, True)),
            (6967, (False, False)),
        ):
            fight, dispatcher, plan, seen = self.fixture()
            plan["spell_id"] = spell
            conditions = ConditionContext(
                {}, active_spell_id_query=lambda: active_spell_id(fight)
            )
            evaluated = []
            replay = dispatcher.replay_event

            def observe(event, **kwargs):
                if event.event_ids == (1025,) and event.channel == 6:
                    evaluated.append(
                        (
                            evaluate_condition(first, conditions),
                            evaluate_condition(second, conditions),
                        )
                    )
                return replay(event, **kwargs)

            dispatcher.replay_event = observe
            with active_spell_scope(fight, spell, level=200), cast_event_scope(
                dispatcher, plan
            ):
                pass
            self.assertEqual(evaluated, [expected])

    def test_unpublished_preview_failure_leaves_original_and_rng_unchanged(self):
        import random

        original, _, _, _ = self.fixture()
        original.resources = {2: 6}
        original.random = random.Random(17)
        before = original.random.getstate()
        preview = deepcopy(original)
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=preview),
            native_clone_authority=object(),
        )

        def fail(event, **kwargs):
            preview.resources[2] -= 1
            preview.random.random()
            raise ValueError("callback rejected transaction")

        dispatcher.replay_event = fail
        with self.assertRaises(ValueError):
            with active_spell_scope(preview, 4820, level=200), cast_event_scope(
                dispatcher, dict(actor_id=7, spell_id=4820, evaluation_level=200)
            ):
                pass
        self.assertEqual(original.resources, {2: 6})
        self.assertEqual(original.random.getstate(), before)

    def test_success_after_callback_failure_discards_preview_without_scope_leak(self):
        fight, dispatcher, plan, seen = self.fixture()
        original = deepcopy(fight)
        replay = dispatcher.replay_event

        def fail_after(event, **kwargs):
            if event.event_ids == (1025,):
                raise ValueError("post-cast class state rejected")
            return replay(event, **kwargs)

        dispatcher.replay_event = fail_after
        with self.assertRaises(ValueError):
            with active_spell_scope(fight, 4820, level=200), cast_event_scope(
                dispatcher, plan
            ):
                fight.pending_state_change = True
        self.assertFalse(hasattr(original, "pending_state_change"))
        self.assertEqual(active_spell_id(fight), -1)
