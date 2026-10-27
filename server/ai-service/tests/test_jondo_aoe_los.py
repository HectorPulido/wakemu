"""Native-shaped inverse aims acquire actual bridge LOS without inventing it."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_jondo_bridge as bridge_tests
from wakfu_ai.bridge.jondo_aoe_los import inverse_aoe_pairs
from wakfu_ai.bridge.jondo_snapshot import build_snapshot
from wakfu_server.combat_effect_targets import area_offsets


SHAPES = (
    ("anu", "circle-2"),
    ("anw", "cross-h2b2-g2d2"),
    ("anx", "crossDiag-h2b2-g2d2"),
)


def row_for(shape):
    offsets = area_offsets(dict(area_class=shape[0], area_native=shape[1]))
    return dict(
        kind="damage",
        amount=20,
        target="enemy",
        element="fire",
        nativeReference=100,
        nativeInArea=True,
        fixedCells=[list(offset) for offset in sorted(offsets)],
    )


class InverseAoeLosTests(unittest.TestCase):
    def snapshot(
        self,
        shape,
        *,
        blocked=False,
        missing=False,
        budget_ms=500,
        mutate=False,
        projected_row=None,
        aim_center=None
    ):
        fixture = bridge_tests.JondoSnapshotLosTests()
        oracle, _, _ = fixture.fixture()
        fight = oracle.runtime.fight
        fight.current.mp = 0
        fight.current.spell_ap_cost_modifiers = {}
        fight.actors[2].position = (3, 0, 0)
        fight.walkable.update((x, y, 0) for x in range(-4, 7) for y in range(-4, 5))
        fight.edges = ()
        oracle.owned_spells = lambda f: {99: 1}
        original_factory = oracle.factory

        def factory(*args):
            native, adapter = original_factory(*args)
            adapter.cast_condition = lambda *args: {}
            return native, adapter

        oracle.factory = factory
        row = row_for(shape) if projected_row is None else projected_row
        offset = (1, 1) if shape[0] == "anx" else (1, 0)
        center = (3 - offset[0], -offset[1], 0) if aim_center is None else aim_center
        before = deepcopy(fight)
        table = dict(
            levels=[[0, 6, [100]]],
            costs=[[2, 0, 0]],
            categories=[],
            line_of_sight=True,
            linear=False,
            free_cell=False,
            range_modifiable=False,
        )
        rule = dict(
            roots=[100],
            costs=dict(ap=2, mp=0, wp=0),
            minimum=0,
            maximum=6,
            line_of_sight=True,
            linear=False,
            free_cell=False,
        )
        calls = []

        def rays(map_id, origin, target, **kwargs):
            calls.append((origin, target))
            if tuple(target) == center and mutate:
                oracle.identity = "changed-during-supplemental-ray"
            if tuple(target) == center and missing:
                raise ValueError("Native ray evidence unavailable")
            return ((not (tuple(target) == center and blocked), frozenset()),)

        with patch(
            "wakfu_ai.bridge.jondo_snapshot.source",
            return_value=dict(nativeIdentity="source", catalogRevision="a" * 64),
        ), patch(
            "wakfu_ai.bridge.jondo_snapshot.effective_affiliation",
            side_effect=lambda f, a: a.team,
        ), patch(
            "wakfu_server.combat_native_spell_casting.native_casting_table",
            return_value=(table, 0),
        ), patch(
            "wakfu_server.combat_native_spell_casting.definition", return_value=rule
        ), patch(
            "wakfu_server.combat_casting_range.resolve_range",
            side_effect=lambda rule, *args: rule,
        ), patch(
            "wakfu_server.combat_spell_usage.limits",
            return_value=dict(per_turn=0, per_target=0, interval=0),
        ), patch.dict(
            "sys.modules",
            {
                "wakfu_server.combat_npc_attack": SimpleNamespace(
                    npc_runtime_catalog=lambda **kwargs: SimpleNamespace()
                )
            },
        ), patch(
            "wakfu_ai.bridge.jondo_snapshot.semantic_rows", return_value=([row], [])
        ), patch(
            "wakfu_ai.bridge.jondo_snapshot.utility_targets", return_value={}
        ), patch(
            "wakfu_ai.bridge.jondo_capabilities.project_support", return_value={}
        ), patch(
            "wakfu_server.combat_los.protocol_catalog.exists", return_value=True
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays", side_effect=rays
        ):
            result = build_snapshot(oracle, budget_ms=budget_ms)
        self.assertEqual(vars(fight), vars(before))
        indices = {tuple(cell["xyz"]): cell["id"] for cell in result["board"]["cells"]}
        facts = {(a, b): value for a, b, value in result["board"]["lineOfSight"]}
        return (
            result,
            center,
            facts.get((indices[fight.current.position], indices[center])),
            calls,
        )

    def test_actual_snapshot_native_circle_cross_diagonal_clear_and_blocked_centers(
        self,
    ):
        for shape in SHAPES:
            for blocked in (False, True):
                with self.subTest(shape=shape, blocked=blocked):
                    result, center, visible, calls = self.snapshot(
                        shape, blocked=blocked
                    )
                    self.assertIs(visible, not blocked)
                    self.assertIn(((0, 0, 0), center), calls)
                    # Ordinary occupied aims are measured before optional centers.
                    self.assertLess(
                        calls.index(((0, 0, 0), (3, 0, 0))),
                        calls.index(((0, 0, 0), center)),
                    )
                    self.assertLessEqual(len(calls), 80)

    def test_missing_native_center_evidence_remains_omitted(self):
        for shape in SHAPES:
            with self.subTest(shape=shape):
                _, _, visible, _ = self.snapshot(shape, missing=True)
                self.assertIsNone(visible)

    def test_source_mutation_during_additional_ray_rejects_complete_snapshot(self):
        with self.assertRaisesRegex(ValueError, "Native source changed"):
            self.snapshot(SHAPES[0], mutate=True)

    def fixture(self):
        cells = tuple((x, y, 0) for x in range(-5, 7) for y in range(-5, 6))
        indices = {cell: index for index, cell in enumerate(cells)}
        actor = dict(id=1, hp=20, team=1, cell=indices[-4, 0, 0])
        enemy = dict(
            id=2,
            hp=20,
            team=0,
            cell=indices[0, 0, 0],
            extraCells=[indices[x, y, 0] for x in range(-1, 2) for y in range(-1, 2)],
        )
        enemy2 = dict(id=3, hp=20, team=0, cell=indices[3, 0, 0])
        spells = [
            dict(
                rows=[row_for(SHAPES[0])],
                needsLineOfSight=True,
                minRange=0,
                maxRange=20,
                inLine=False,
            )
        ]
        return cells, indices, [actor, enemy, enemy2], spells

    def pairs(self, **kwargs):
        cells, indices, actors, spells = self.fixture()
        with patch("wakfu_ai.bridge.jondo_aoe_los.clock_now", return_value=0):
            return inverse_aoe_pairs(
                spells,
                actors,
                cells,
                indices,
                [(-4, 0, 0), (-4, 1, 0)],
                {(x, y, 0) for x in range(-1, 2) for y in range(-1, 2)} | {(3, 0, 0)},
                actor_id=1,
                deadline=1,
                **kwargs
            )

    def test_distinct_enemy_priority_body_overlap_not_counted_as_many_recipients(self):
        pairs = self.pairs(max_pairs=1)
        self.assertEqual(pairs, [((-4, 0, 0), (2, 0, 0))])

    def test_work_center_pair_and_soft_deadline_bounds_preserve_partial_facts(self):
        self.assertEqual(len(self.pairs(max_pairs=3)), 3)
        self.assertLessEqual(
            len({target for _, target in self.pairs(max_centers=2)}), 2
        )
        cells, indices, actors, spells = self.fixture()
        with patch("wakfu_ai.bridge.jondo_aoe_los.clock_now", return_value=1):
            self.assertEqual(
                inverse_aoe_pairs(
                    spells,
                    actors,
                    cells,
                    indices,
                    [(-4, 0, 0)],
                    set(),
                    actor_id=1,
                    deadline=1,
                ),
                [],
            )
        with patch("wakfu_ai.bridge.jondo_aoe_los.check") as checked:
            self.pairs(max_work=64)
            self.assertEqual(checked.call_count, 1)
        _, center, visible, calls = self.snapshot(SHAPES[0], budget_ms=0)
        self.assertIsNone(visible)
        self.assertNotIn(((0, 0, 0), center), calls)
        self.assertIn(((0, 0, 0), (3, 0, 0)), calls)

    def test_non_area_no_los_hidden_and_range_line_restrictions(self):
        cells, indices, actors, spells = self.fixture()
        for change in (
            "not_area",
            "no_los",
            "hidden",
            "out_of_range",
            "ally_only",
            "self_only",
        ):
            with self.subTest(change=change):
                books, roster = deepcopy(spells), deepcopy(actors)
                if change == "not_area":
                    books[0]["rows"][0]["nativeInArea"] = False
                if change == "no_los":
                    books[0]["needsLineOfSight"] = False
                if change == "hidden":
                    for enemy in roster[1:]:
                        enemy["hidden"] = True
                if change == "out_of_range":
                    books[0]["maxRange"] = 0
                if change == "ally_only":
                    books[0]["rows"][0]["target"] = "ally"
                if change == "self_only":
                    books[0]["rows"][0]["target"] = "self"
                with patch("wakfu_ai.bridge.jondo_aoe_los.clock_now", return_value=0):
                    actual = inverse_aoe_pairs(
                        books,
                        roster,
                        cells,
                        indices,
                        [(-4, 0, 0)],
                        {(-4, 0, 0)},
                        actor_id=1,
                        deadline=1,
                    )
                self.assertEqual(actual, [])
        spells[0].update(inLine=True, minRange=2, maxRange=5)
        with patch("wakfu_ai.bridge.jondo_aoe_los.clock_now", return_value=0):
            actual = inverse_aoe_pairs(
                spells,
                actors,
                cells,
                indices,
                [(-4, 0, 0), (-4, 1, 0)],
                set(),
                actor_id=1,
                deadline=1,
            )
        for origin, center in actual:
            self.assertTrue(origin[0] == center[0] or origin[1] == center[1])
            self.assertTrue(
                2 <= abs(origin[0] - center[0]) + abs(origin[1] - center[1]) <= 5
            )


if __name__ == "__main__":
    unittest.main()
