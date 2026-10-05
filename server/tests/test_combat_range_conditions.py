import unittest
from types import SimpleNamespace
from wakfu_server.combat_range_conditions import (
    RangeFighter,
    enemy_count,
    total_hp_percent,
    creation_in_play,
)
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class RangeConditionsTests(unittest.TestCase):
    def test_native_float_hp_includes_virtual_hp(self):
        self.assertEqual(
            total_hp_percent(
                {"HP": 81, "VIRTUAL_HP": 10}, {"HP": 101, "VIRTUAL_HP": 20}
            ),
            75.20661163330078,
        )
        self.assertEqual(
            total_hp_percent({"HP": 1, "VIRTUAL_HP": 0}, {"HP": 3, "VIRTUAL_HP": 0}),
            33.333335876464844,
        )
        self.assertEqual(
            total_hp_percent({"HP": 0, "VIRTUAL_HP": 0}, {"HP": 0, "VIRTUAL_HP": 0}), 0
        )
        with self.assertRaises(ValueError):
            total_hp_percent({"HP": 1}, {"HP": 3})

    def test_native_footprint_filters_and_nonpositive_max(self):
        rows = tuple(
            RangeFighter((x, y, 0), radius, team, play, prop, barrel)
            for x, y, radius, team, play, prop, barrel in (
                (3, 3, 1, 1, True, False, False),
                (1, 0, 0, 0, True, False, False),
                (2, 0, 0, 1, False, False, False),
                (2, 0, 0, 1, True, True, False),
                (2, 0, 0, 1, True, False, True),
            )
        )
        self.assertEqual(
            enemy_count(rows, affiliation=0, center=(0, 0, 0), minimum=4, maximum=4), 1
        )
        self.assertEqual(
            enemy_count(
                rows,
                affiliation=0,
                center=(0, 0, 0),
                minimum=100,
                maximum=0,
                aligned=True,
                los=True,
            ),
            1,
        )
        self.assertEqual(
            enemy_count(
                rows,
                affiliation=0,
                center=(0, 0, 0),
                minimum=0,
                maximum=4,
                aligned=True,
            ),
            0,
        )
        self.assertEqual(
            enemy_count(rows, affiliation=0, center=None, minimum=0, maximum=4), 0
        )

    def test_los_and_membership_are_explicit(self):
        row = RangeFighter((1, 0, 0), 0, 1, True, False, False)
        with self.assertRaises(ValueError):
            enemy_count(
                (row,), affiliation=0, center=(0, 0, 0), minimum=0, maximum=2, los=True
            )
        self.assertEqual(
            enemy_count(
                (row,),
                affiliation=0,
                center=(0, 0, 0),
                minimum=0,
                maximum=2,
                los=True,
                visible=lambda a, b: False,
            ),
            0,
        )
        preview = SimpleNamespace(events=[])
        actor = SimpleNamespace(id=1, hp=5)
        self.assertTrue(creation_in_play(preview, actor))
        actor.hp = 0
        self.assertIsNone(creation_in_play(preview, actor))
        preview.events = [{"kind": "death", "actor_id": 1}]
        self.assertFalse(creation_in_play(preview, actor))
        actor.hp = 5
        self.assertIsNone(creation_in_play(preview, actor))

    def test_parser_native_signatures_and_missing_target(self):
        actor = ConditionActor(
            characteristics={"HP": 81, "VIRTUAL_HP": 10},
            characteristic_maxima={"HP": 101, "VIRTUAL_HP": 20},
        )
        calls = []

        def query(*args):
            calls.append(args)
            return 2

        ctx = ConditionContext(
            {"caster": actor}, effect_target_absent=True, enemy_range_query=query
        )
        self.assertTrue(evaluate_condition('GetTotalHpInPercent("anything") > 75', ctx))
        self.assertTrue(evaluate_condition('GetTotalHpInPercent("target") == -1', ctx))
        self.assertTrue(
            evaluate_condition(
                'GetEnnemyCountInRange(1, 3, "target", True, False) == 2', ctx
            )
        )
        self.assertEqual(calls[-1], (1, 3, "target", True, False))
        for code in ("GetEnnemyCountInRange(1,2)==0", "GetTotalHpInPercent()==0"):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(code, ctx)


class NativeAdditionalRangeTests(unittest.TestCase):
    def test_allies_include_caster_exclude114_and_optional_inplay(self):
        from wakfu_server.combat_range_conditions import range_count

        rows = (
            RangeFighter((0, 0, 0), 0, 0, True, False, False),
            RangeFighter((1, 0, 0), 0, 0, False, False, False),
            RangeFighter((1, 0, 0), 0, 0, True, False, False, True),
            RangeFighter((1, 0, 0), 0, 1, True, False, False),
        )
        self.assertEqual(
            range_count(
                rows,
                relation="ally",
                affiliation=0,
                center=(0, 0, 0),
                minimum=0,
                maximum=3,
            ),
            1,
        )
        self.assertEqual(
            range_count(
                rows,
                relation="ally",
                affiliation=0,
                center=(0, 0, 0),
                minimum=0,
                maximum=3,
                in_play=False,
            ),
            2,
        )

    def test_state_counts_objects_exactlevel_owner_and_roster_filter(self):
        from wakfu_server.combat_range_conditions import range_count

        rows = (
            RangeFighter(
                (1, 0, 0), 0, 1, True, False, False, states=((3442, 1, 7), (3442, 2, 8))
            ),
            RangeFighter((2, 0, 0), 0, 0, False, False, False, states=((3442, 1, 7),)),
        )
        args = dict(
            relation="state",
            affiliation=0,
            center=(0, 0, 0),
            minimum=0,
            maximum=3,
            state_reference=3442,
        )
        self.assertEqual(range_count(rows, **args), 1)
        self.assertEqual(range_count(rows, **args, in_play=False), 2)
        self.assertEqual(range_count(rows, **args, state_level=2, state_caster=7), 0)
        self.assertEqual(range_count(rows, **args, state_level=2, state_caster=8), 1)

    def test_state_and_ally_native_constructor_signatures(self):
        calls = []

        def query(*args):
            calls.append(args)
            return 1

        ctx = ConditionContext({}, allies_range_query=query, state_range_query=query)
        self.assertTrue(
            evaluate_condition(
                'GetAlliesCountInRange(0,3,"caster",False,False,False)==1', ctx
            )
        )
        self.assertEqual(calls[-1], (0, 3, "caster", False, False, False))
        for code, expected in (
            (
                'GetStateCountInRange(3,"caster",3442)',
                (3, "caster", 3442, -1, True, ""),
            ),
            (
                'GetStateCountInRange(3,"caster",3442,2)',
                (3, "caster", 3442, 2, True, ""),
            ),
            (
                'GetStateCountInRange(3,"caster",3442,False,"target")',
                (3, "caster", 3442, -1, False, "target"),
            ),
            (
                'GetStateCountInRange(3,"caster",3442,"caster")',
                (3, "caster", 3442, -1, True, "caster"),
            ),
        ):
            self.assertTrue(evaluate_condition(code + "==1", ctx))
            self.assertEqual(calls[-1], expected)
        for code in (
            'GetStateCountInRange(3,"caster",3442,"caster",False)==1',
            "GetAlliesCountInRange(0,3)==1",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(code, ctx)
