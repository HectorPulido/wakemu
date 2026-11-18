"""Reviewed mission toolkit bindings are validated and planned fail-closed."""

import copy
import unittest

from wakfu_server.achievements import mission_toolkit_contract as contract
from wakfu_server.achievements import mission_toolkit_planner as planner


def objective(identity, *, variable=None, threshold=None, criteria=""):
    row = {"d": identity, "ckc": criteria, "cke": ""}
    if variable is not None:
        row["ckf"] = [
            {
                "ckm": f'GetAchievementVariable("counter-{variable}") >= {threshold}',
                "ckn": [variable],
            }
        ]
    return row


def quest(identity, objectives, *, visible=False, criteria=""):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": visible,
        "cjI": criteria,
        "cjJ": objectives,
        "cjK": [],
    }


def profile(*, bindings=(), links=(), activations=()):
    return {
        "version": 1,
        "id": "synthetic-reviewed-profile",
        "evidence": ["unit-test synthetic fixture"],
        "bindings": list(bindings),
        "links": list(links),
        "activations": list(activations),
    }


def binding(
    identity,
    quest_id,
    objective_id,
    kind,
    *,
    count="operation",
    variable=None,
    reference=44,
    maps=None,
    instances=None,
):
    row = {
        "id": identity,
        "quest_id": quest_id,
        "objective_id": objective_id,
        "event": {"kind": kind},
        "count": count,
    }
    if reference is not None:
        row["event"]["reference"] = reference
    if variable is not None:
        row["variable_id"] = variable
    if maps is not None:
        row["maps"] = maps
    if instances is not None:
        row["instances"] = instances
    return row


def state(*, running=(), completed=(), objectives=(), variables=None, tracking=()):
    return {
        "variables": {} if variables is None else dict(variables),
        "tracking": list(tracking),
        "recent": [],
        "completion_dates": {},
        "running": list(running),
        "completed": list(completed),
        "objectives": list(objectives),
    }


class MissionToolkitCoreTests(unittest.TestCase):
    character = {"id": 7, "map_id": 1385, "level": 20}
    store = object()

    def plan(self, current, definitions, declaration, event):
        return planner.plan(
            current,
            definitions,
            declaration,
            event,
            character=self.character,
            store=self.store,
            now_ms=123456,
        )

    def test_counter_operation_and_quantity_use_native_threshold(self):
        definitions = [quest(1, [objective(11, variable=70, threshold=3)])]
        declaration = profile(
            bindings=[binding("harvest", 1, 11, "resource_harvest", variable=70)]
        )
        current = state(running=[1])
        after, _, completed_objectives, completed = self.plan(
            current,
            definitions,
            declaration,
            {"kind": "resource_harvest", "reference": 44, "quantity": 9},
        )
        self.assertEqual(after["variables"]["70"], 1)
        self.assertEqual(completed_objectives, [])
        self.assertEqual(completed, [])
        after, _, completed_objectives, completed = self.plan(
            after,
            definitions,
            declaration,
            {"kind": "resource_harvest", "reference": 44, "quantity": 9},
        )
        self.assertEqual(after["variables"]["70"], 2)
        self.assertEqual(completed_objectives, [])
        self.assertEqual(completed, [])
        after, _, completed_objectives, completed = self.plan(
            after,
            definitions,
            declaration,
            {"kind": "resource_harvest", "reference": 44, "quantity": 9},
        )
        self.assertEqual(after["variables"]["70"], 3)
        self.assertEqual(completed_objectives, [11])
        self.assertEqual(completed, [1])

        quantity_profile = profile(
            bindings=[
                binding(
                    "craft", 1, 11, "craft_completed", count="quantity", variable=70
                )
            ]
        )
        after, _, completed_objectives, completed = self.plan(
            state(running=[1]),
            definitions,
            quantity_profile,
            {"kind": "craft_completed", "reference": 44, "quantity": 3},
        )
        self.assertEqual(after["variables"]["70"], 3)
        self.assertEqual(completed_objectives, [11])
        self.assertEqual(completed, [1])

        five_unit_event = profile(
            bindings=[
                binding(
                    "quantity-five",
                    1,
                    11,
                    "craft_completed",
                    count="quantity",
                    variable=70,
                )
            ]
        )
        after, _, completed_objectives, completed = self.plan(
            state(running=[1]),
            definitions,
            five_unit_event,
            {"kind": "craft_completed", "reference": 44, "quantity": 5},
        )
        # Once the objective reaches its native threshold of three, excess
        # quantity does not inflate the completed objective's counter.
        self.assertEqual(after["variables"]["70"], 3)
        self.assertEqual(completed_objectives, [11])
        self.assertEqual(completed, [1])

    def test_quantity_increment_can_complete_multiple_shared_counter_objectives(self):
        definitions = [
            quest(
                1,
                [
                    objective(11, variable=70, threshold=3),
                    objective(12, variable=70, threshold=5),
                ],
            )
        ]
        declaration = profile(
            bindings=[
                binding(
                    "quantity-three",
                    1,
                    11,
                    "craft_completed",
                    count="quantity",
                    variable=70,
                ),
                binding(
                    "quantity-five",
                    1,
                    12,
                    "craft_completed",
                    count="quantity",
                    variable=70,
                ),
            ]
        )
        after, _, objectives, completed = self.plan(
            state(running=[1]),
            definitions,
            declaration,
            {"kind": "craft_completed", "reference": 44, "quantity": 5},
        )
        self.assertEqual(after["variables"]["70"], 5)
        self.assertEqual(objectives, [11, 12])
        self.assertEqual(completed, [1])

    def test_quantity_increment_is_not_capped_when_native_criteria_are_unknown(self):
        definitions = [
            quest(
                1,
                [
                    objective(
                        11,
                        variable=70,
                        threshold=3,
                        criteria="UnknownMissionPredicate(1)",
                    )
                ],
            )
        ]
        declaration = profile(
            bindings=[
                binding(
                    "quantity-five",
                    1,
                    11,
                    "craft_completed",
                    count="quantity",
                    variable=70,
                )
            ]
        )
        after, intents, objectives, completed = self.plan(
            state(running=[1]),
            definitions,
            declaration,
            {"kind": "craft_completed", "reference": 44, "quantity": 5},
        )
        self.assertEqual(after["variables"]["70"], 5)
        self.assertEqual(after["running"], [1])
        self.assertEqual(after["objectives"], [])
        self.assertEqual((intents, objectives, completed), ([], [], []))

    def test_completed_objective_replay_has_no_plan_effects(self):
        definitions = [quest(1, [objective(11, variable=70, threshold=3)])]
        declaration = profile(
            bindings=[
                binding(
                    "quantity-five",
                    1,
                    11,
                    "craft_completed",
                    count="quantity",
                    variable=70,
                )
            ]
        )
        before = state(completed=[1], objectives=[11], variables={"70": 3})
        after, intents, objectives, completed = self.plan(
            before,
            definitions,
            declaration,
            {"kind": "craft_completed", "reference": 44, "quantity": 5},
        )
        self.assertEqual(after, before)
        self.assertEqual((intents, objectives, completed), ([], [], []))

    def test_inactive_or_nonmatching_event_leaves_counter_untouched(self):
        definitions = [quest(1, [objective(11, variable=70, threshold=1)])]
        declaration = profile(
            bindings=[
                binding(
                    "scoped",
                    1,
                    11,
                    "resource_harvest",
                    variable=70,
                    reference=44,
                    maps=[1385],
                )
            ]
        )
        current = state(variables={"70": 2})
        for event, character in (
            (
                {"kind": "resource_harvest", "reference": 44, "quantity": 1},
                self.character,
            ),
            (
                {"kind": "resource_harvest", "reference": 45, "quantity": 1},
                self.character,
            ),
            (
                {"kind": "resource_harvest", "reference": 44, "quantity": 1},
                {**self.character, "map_id": 99},
            ),
        ):
            with self.subTest(event=event, character=character):
                after, intents, objectives, completed = planner.plan(
                    current,
                    definitions,
                    declaration,
                    event,
                    character=character,
                    store=self.store,
                    now_ms=123456,
                )
                self.assertEqual(after, current)
                self.assertEqual((intents, objectives, completed), ([], [], []))

    def test_direct_craft_completion_and_parent_child_dependency(self):
        definitions = [
            quest(1, [objective(11)]),
            quest(2, [objective(21)]),
        ]
        declaration = profile(
            bindings=[binding("make", 1, 11, "craft_completed")],
            links=[{"parent_quest_id": 2, "objective_id": 21, "child_quest_id": 1}],
        )
        after, _, objectives, completed = self.plan(
            state(running=[1, 2]),
            definitions,
            declaration,
            {"kind": "craft_completed", "reference": 44, "quantity": 1},
        )
        self.assertEqual(objectives, [11, 21])
        self.assertEqual(completed, [1, 2])
        self.assertEqual(after["completed"], [1, 2])

    def test_matching_activation_seeds_counter_and_autotracks(self):
        definitions = [quest(3, [objective(31, variable=71, threshold=2)])]
        declaration = profile(
            activations=[
                {
                    "id": "activate-3",
                    "quest_id": 3,
                    "event": {"kind": "map_enter", "reference": 44},
                    "maps": [1385],
                }
            ]
        )
        after, _, objectives, completed = self.plan(
            state(),
            definitions,
            declaration,
            {"kind": "map_enter", "reference": 44, "quantity": 1},
        )
        self.assertEqual(after["running"], [3])
        self.assertEqual(after["variables"]["71"], 0)
        self.assertEqual(after["tracking"], [3])
        self.assertEqual((objectives, completed), ([], []))

    def test_completed_parent_event_activates_required_followup(self):
        definitions = [
            quest(1, [objective(11)]),
            quest(3, [objective(31, variable=71, threshold=2)]),
        ]
        declaration = profile(
            bindings=[binding("finish-1", 1, 11, "craft_completed")],
            activations=[
                {
                    "id": "activate-after-1",
                    "quest_id": 3,
                    "event": {"kind": "quest_completed", "reference": 1},
                    "requires_completed": [1],
                }
            ],
        )
        after, _, objectives, completed = self.plan(
            state(running=[1]),
            definitions,
            declaration,
            {"kind": "craft_completed", "reference": 44, "quantity": 1},
        )
        self.assertEqual(completed, [1])
        self.assertEqual(objectives, [11])
        self.assertEqual(after["running"], [3])
        self.assertIn(1, after["completed"])
        self.assertEqual(after["tracking"], [3])
        self.assertEqual(after["variables"]["71"], 0)

    def test_instance_scopes_match_zero_and_reject_other_instances(self):
        definitions = [
            quest(1, [objective(11)]),
            quest(2, [objective(21)]),
        ]
        scoped_binding = profile(
            bindings=[binding("instance-zero", 1, 11, "craft_completed", instances=[0])]
        )
        event = {"kind": "craft_completed", "reference": 44, "quantity": 1}
        at_public_instance = {**self.character, "instance_id": 0}
        after, _, objectives, completed = planner.plan(
            state(running=[1]),
            definitions,
            scoped_binding,
            event,
            character=at_public_instance,
            store=self.store,
            now_ms=123456,
        )
        self.assertEqual((objectives, completed), ([11], [1]))
        self.assertIn(1, after["completed"])

        in_private_instance = {**self.character, "instance_id": 1}
        untouched, _, objectives, completed = planner.plan(
            state(running=[1]),
            definitions,
            scoped_binding,
            event,
            character=in_private_instance,
            store=self.store,
            now_ms=123456,
        )
        self.assertEqual(untouched["objectives"], [])
        self.assertEqual((objectives, completed), ([], []))

        scoped_activation = profile(
            activations=[
                {
                    "id": "instance-zero-activation",
                    "quest_id": 2,
                    "event": {"kind": "map_enter", "reference": 44},
                    "instances": [0],
                }
            ]
        )
        enter = {"kind": "map_enter", "reference": 44, "quantity": 1}
        activated, _, _, _ = planner.plan(
            state(),
            definitions,
            scoped_activation,
            enter,
            character=at_public_instance,
            store=self.store,
            now_ms=123456,
        )
        self.assertEqual(activated["running"], [2])
        rejected, _, _, _ = planner.plan(
            state(),
            definitions,
            scoped_activation,
            enter,
            character=in_private_instance,
            store=self.store,
            now_ms=123456,
        )
        self.assertEqual(rejected["running"], [])

        for instances in ([], [0, 0], [-1], [True], [2**63]):
            declaration = profile(
                bindings=[
                    binding(
                        "invalid-instance-scope",
                        1,
                        11,
                        "craft_completed",
                        instances=instances,
                    )
                ]
            )
            with self.subTest(instances=instances), self.assertRaises(ValueError):
                contract.validate(declaration, definitions)

        max_instance = profile(
            bindings=[
                binding(
                    "max-instance-scope",
                    1,
                    11,
                    "craft_completed",
                    instances=[2**63 - 1],
                )
            ]
        )
        self.assertEqual(contract.validate(max_instance, definitions), max_instance)

    def test_malformed_or_conflicting_profiles_and_events_fail_closed(self):
        native = [
            quest(
                1,
                [
                    objective(11, variable=70, threshold=2),
                    objective(12, variable=70, threshold=4),
                ],
            ),
            quest(2, [objective(21)]),
        ]
        base = binding("first", 1, 11, "resource_harvest", variable=70)
        invalid_profiles = [
            profile(bindings=[dict(base, variable_id=999)]),
            profile(
                links=[
                    {"parent_quest_id": 1, "objective_id": 11, "child_quest_id": 2},
                    {"parent_quest_id": 1, "objective_id": 11, "child_quest_id": 2},
                ]
            ),
            profile(
                activations=[
                    {
                        "id": "bad-requirement",
                        "quest_id": 2,
                        "event": {"kind": "map_enter"},
                        "requires_completed": [[1]],
                    }
                ]
            ),
            profile(
                activations=[
                    {
                        "id": "bad-map",
                        "quest_id": 2,
                        "event": {"kind": "map_enter"},
                        "maps": [[1385]],
                    }
                ]
            ),
        ]
        for declaration in invalid_profiles:
            with self.subTest(declaration=declaration), self.assertRaises(ValueError):
                contract.validate(declaration, native)

        for declaration, event in (
            (
                profile(bindings=[base, dict(base, id="overlap")]),
                {"kind": "resource_harvest", "reference": 44, "quantity": 1},
            ),
            (
                profile(
                    bindings=[
                        base,
                        binding(
                            "conflict",
                            1,
                            12,
                            "resource_harvest",
                            count="quantity",
                            variable=70,
                        ),
                    ]
                ),
                {"kind": "resource_harvest", "reference": 44, "quantity": 5},
            ),
        ):
            with self.subTest(declaration=declaration), self.assertRaises(ValueError):
                self.plan(state(running=[1]), native, declaration, event)

        declaration = profile(bindings=[base])
        current = state(running=[1])
        for event in (
            {"kind": "resource_harvest", "reference": 44},
            {"kind": "resource_harvest", "reference": 44, "quantity": True},
            {"kind": "resource_harvest", "reference": 44, "quantity": 32768},
        ):
            with self.subTest(event=event), self.assertRaises(ValueError):
                self.plan(current, native, declaration, event)

        with self.assertRaises(ValueError):
            self.plan(
                state(running=[1], variables={"70": 2**63 - 1}),
                native,
                declaration,
                {"kind": "resource_harvest", "reference": 44, "quantity": 1},
            )

    def test_alternative_child_links_are_allowed_but_exact_duplicate_is_rejected(self):
        native = [
            quest(1, [objective(11)]),
            quest(2, [objective(21)]),
            quest(3, [objective(31)]),
        ]
        declaration = profile(
            links=[
                {"parent_quest_id": 2, "objective_id": 21, "child_quest_id": 1},
                {"parent_quest_id": 2, "objective_id": 21, "child_quest_id": 3},
            ]
        )
        self.assertEqual(contract.validate(declaration, native), declaration)
        duplicate = copy.deepcopy(declaration)
        duplicate["links"].append(copy.deepcopy(duplicate["links"][0]))
        with self.assertRaisesRegex(ValueError, "Conflicting or unsupported"):
            contract.validate(duplicate, native)

    def test_publication_rejects_only_overlapping_binding_scopes(self):
        native = [
            quest(
                1,
                [
                    objective(11),
                    objective(12, variable=70, threshold=3),
                    objective(13, variable=70, threshold=5),
                ],
            )
        ]

        def declaration(
            identity,
            objective_id=11,
            *,
            reference=44,
            maps=None,
            instances=None,
            kind="craft_completed",
            count="operation",
            variable=None,
        ):
            return binding(
                identity,
                1,
                objective_id,
                kind,
                count=count,
                variable=variable,
                reference=reference,
                maps=maps,
                instances=instances,
            )

        rejected = [
            # Wildcard reference intersects any specific reference.
            [declaration("wildcard", reference=None), declaration("specific")],
            # Same event and objective intersect in both location dimensions.
            [
                declaration("maps-a", maps=[1, 2], instances=[0]),
                declaration("maps-b", maps=[2, 3], instances=[0]),
            ],
            # One native variable cannot have competing count semantics.
            [
                declaration("operation", 12, count="operation", variable=70),
                declaration("quantity", 13, count="quantity", variable=70),
            ],
        ]
        for rows in rejected:
            declaration_profile = profile(bindings=rows)
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                contract.validate(declaration_profile, native)

        accepted = [
            # Explicitly disjoint event references.
            [declaration("ref-a", reference=44), declaration("ref-b", reference=45)],
            # Disjoint map scopes prevent two otherwise identical bindings.
            [declaration("map-a", maps=[1]), declaration("map-b", maps=[2])],
            # Disjoint instance scopes prevent two otherwise identical bindings.
            [
                declaration("instance-a", instances=[0]),
                declaration("instance-b", instances=[1]),
            ],
            # Shared variable and same policy can represent two native thresholds.
            [
                declaration("threshold-three", 12, count="quantity", variable=70),
                declaration("threshold-five", 13, count="quantity", variable=70),
            ],
        ]
        for rows in accepted:
            declaration_profile = profile(bindings=rows)
            with self.subTest(rows=rows):
                self.assertEqual(
                    contract.validate(declaration_profile, native), declaration_profile
                )

    def test_unknown_native_criteria_do_not_complete_objective(self):
        definitions = [quest(1, [objective(11, criteria="UnknownMissionPredicate(1)")])]
        declaration = profile(
            bindings=[binding("unknown-criteria", 1, 11, "craft_completed")]
        )
        original = state(running=[1])
        after, intents, objectives, completed = self.plan(
            original,
            definitions,
            declaration,
            {"kind": "craft_completed", "reference": 44, "quantity": 1},
        )
        self.assertEqual(after["variables"], {})
        self.assertEqual(after["objectives"], [])
        self.assertEqual(after["running"], [1])
        self.assertEqual((intents, objectives, completed), ([], [], []))


if __name__ == "__main__":
    unittest.main()
