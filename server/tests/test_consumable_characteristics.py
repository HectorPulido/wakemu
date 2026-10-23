"""Native food scalar projection without loading the combat catalog."""
import unittest
from wakfu_server.consumable_characteristics import bonuses


def effect(identity, runner, stat, params, values, *, level=1, children=()):
    return dict(
        id=identity,
        generic=330 if runner == "eYg" else 321 if runner == "eZi" else 0,
        runner=runner,
        stat_id=stat,
        params=params,
        values=values,
        level=level,
        criteria="",
        subscription=False,
        children=list(children),
        native_metadata=dict(native_target_selector={"class": "fcE", "mask": 2}),
    )


def state(
    effects, *, roots=None, level=1, clock="online", remaining_ms=1000, controls=()
):
    return dict(
        state_id=1,
        level=level,
        remaining_ms=remaining_ms,
        clock=clock,
        effect_ids=list(roots if roots is not None else [e["id"] for e in effects]),
        metadata=dict(
            native_effects={str(e["id"]): e for e in effects},
            counter_control_effect_ids=list(controls),
        ),
    )


class ConsumableCharacteristicTests(unittest.TestCase):
    def test_resource_reduction_preserves_native_family_and_raw_minimum(self):
        from wakfu_server.equipment_resource_bonuses import project

        node = effect(9057, "eWO", None, [1.0, 0.0], [1])
        node["generic"] = 56
        node["native_metadata"]["target_masks"] = [None] * 7
        result = bonuses(
            {"consumable_states": [state([node])]}, include_operations=True
        )
        self.assertEqual(result["unsupported"], [])
        self.assertEqual(result["resource_kinds"][0]["family"], "eWO")
        base = dict(
            current=6,
            raw_minimum=0,
            raw_maximum=6,
            percentage=0,
            minimum=0,
            maximum=6,
            hard_minimum=0,
            hard_maximum=2147483647,
        )
        final = project(result["stat_operations"], result["resource_kinds"], {2: base})[
            "final"
        ][2]
        self.assertEqual(
            (final["current"], final["maximum"], final["raw_minimum"]), (5, 5, -1)
        )

    def test_resource_increase_uses_original_cap_flag(self):
        from wakfu_server.equipment_resource_bonuses import project

        base = dict(
            current=15,
            raw_minimum=0,
            raw_maximum=15,
            percentage=0,
            minimum=0,
            maximum=15,
            hard_minimum=0,
            hard_maximum=2147483647,
        )
        for flags, expected in (([], 16), ([17], 18)):
            with self.subTest(flags=flags):
                node = effect(1, "eWN", 2, [3.0, 0.0, 1.0, 0.0, 0.0, 0.0], [3, 1, 0])
                node["native_metadata"]["native_effect_flags"] = flags
                result = bonuses(
                    {"consumable_states": [state([node])]}, include_operations=True
                )
                final = project(
                    result["stat_operations"], result["resource_kinds"], {2: base}
                )["final"][2]
                self.assertEqual(
                    (final["current"], final["maximum"]), (expected, expected)
                )

    def test_resource_metadata_cannot_be_inferred_from_a_scalar(self):
        for runner in ("eWN", "eWQ", "eWR"):
            with self.subTest(runner=runner):
                node = (
                    effect(1, runner, 2, [1.0, 0.0, 1.0, 0.0, 0.0, 0.0], [1, 1, 0])
                    if runner == "eWN"
                    else effect(1, runner, 2, [1.0, 0.0], [1])
                )
                result = bonuses(
                    {"consumable_states": [state([node])]}, include_operations=True
                )
                self.assertEqual(result["stats"], {})
                self.assertEqual(result["resource_kinds"], {})
                self.assertEqual(
                    result["unsupported"][0]["reason"],
                    "unsupported-consumable-resource-operation",
                )

    def test_attested_fight_boundary_groups_defer_children_without_world_benefit(self):
        for events, criterion in (
            ([1026], "GetFightModel() == 2"),
            ([1026, 1028], "(not IsBattleground())"),
        ):
            with self.subTest(events=events):
                reactive = effect(205959, "eYg", None, [], [], children=(205960,))
                reactive["subscription"] = True
                reactive["criteria"] = criterion
                reactive["native_metadata"]["target_masks"] = [None] * 5 + [
                    events,
                    None,
                ]
                child = effect(205960, "unknown-combat-only-child", None, [], [])
                row = state([reactive, child], roots=(205959,))
                row["metadata"]["combat_only_effect_ids"] = [205959]
                self.assertEqual(
                    bonuses({"consumable_states": [row]}),
                    dict(stats={}, unsupported=[]),
                )
                reactive["native_metadata"]["target_masks"][5] = [1030]
                with self.assertRaisesRegex(ValueError, "combat-only consumable event"):
                    bonuses({"consumable_states": [row]})

    def test_installed_wisdom_prospecting_hp_and_dynamic_characteristic_parameters(
        self,
    ):
        # Original exported effects66106,66109,183759 and295732 respectively.
        cases = (
            (effect(66106, "eWQ", 36, [100.0, 0.0], [100], level=12), 12, {36: 100}),
            (effect(66109, "eWQ", 33, [50.0, 0.0], [50], level=12), 12, {33: 50}),
            (
                effect(
                    183759,
                    "eWN",
                    1,
                    [20.0, 0.0, 1.0, 0.0, 0.0, 0.0],
                    [20, 1, 0],
                    level=5,
                ),
                5,
                {1: 20},
            ),
            (
                effect(
                    295732, "eWQ", None, [50.0, 0.0, 0.0, 0.0, 118.0, 0.0], [50, 0, 118]
                ),
                1,
                {118: 50},
            ),
        )
        for node, level, expected in cases:
            with self.subTest(effect=node["id"]):
                self.assertEqual(
                    bonuses({"consumable_states": [state([node], level=level)]}),
                    dict(stats=expected, unsupported=[]),
                )

    def test_event_zero_milliseconds_is_active_but_timed_zero_is_expired(self):
        node = effect(183770, "eWQ", 20, [10.0, 0.0], [10], level=5)
        for clock, expected in (("event", {20: 10}), ("online", {}), ("wall", {})):
            with self.subTest(clock=clock):
                row = state([node], level=5, clock=clock, remaining_ms=0)
                self.assertEqual(
                    bonuses({"consumable_states": [row]})["stats"], expected
                )

    def test_additive_counter_does_not_multiply_native_constant_bonus(self):
        node = effect(183770, "eWQ", 20, [10.0, 0.0], [10], level=5)
        for current_level in (1, 5, 30, 300):
            row = state([node], level=current_level, clock="event", remaining_ms=0)
            self.assertEqual(bonuses({"consumable_states": [row]})["stats"], {20: 10})

    def test_current_level_uses_native_parameter_increment_not_stale_export_value(self):
        node = effect(117769, "eWQ", 20, [0.0, 1.0], [5], level=5)
        self.assertEqual(
            bonuses({"consumable_states": [state([node], level=30)]})["stats"], {20: 30}
        )

    def test_exact_attested_counter_controls_are_not_projected_as_contextual_stats(
        self,
    ):
        scalar = effect(183770, "eWQ", 20, [10.0, 0.0], [10])
        control = effect(183772, "eYg", None, [0.0, 0.0], [0], children=(183773,))
        control["subscription"] = True
        removal = effect(183773, "eZi", None, [4436.0, 0.0], [4436])
        row = state(
            [scalar, control, removal],
            roots=(183770, 183772),
            controls=(183772, 183773),
        )
        self.assertEqual(
            bonuses({"consumable_states": [row]}), dict(stats={20: 10}, unsupported=[])
        )
        row["metadata"]["counter_control_effect_ids"] = [183770]
        with self.assertRaisesRegex(ValueError, "counter control"):
            bonuses({"consumable_states": [row]})

    def test_conditional_and_corrupt_native_amounts_are_not_fabricated(self):
        scalar = effect(66106, "eWQ", 36, [100.0, 0.0], [100])
        scalar["criteria"] = "HasState(1)"
        result = bonuses({"consumable_states": [state([scalar])]})
        self.assertEqual(result["stats"], {})
        self.assertEqual(len(result["unsupported"]), 1)
        scalar["criteria"] = ""
        scalar["values"] = [999]
        result = bonuses({"consumable_states": [state([scalar])]})
        self.assertEqual(result["stats"], {})
        self.assertEqual(len(result["unsupported"]), 1)

    def test_subtraction_and_unconditional_group_keep_native_sign_and_roots(self):
        parent = effect(61960, "eYg", None, [0.0, 0.0], [0], children=(67382,))
        scalar = effect(67382, "eWR", 27, [15.0, 0.0], [15])
        row = state([parent, scalar], roots=(61960,))
        self.assertEqual(
            bonuses({"consumable_states": [row]}), dict(stats={27: -15}, unsupported=[])
        )

    def test_missing_definition_and_recursive_graph_fail_closed(self):
        parent = effect(61960, "eYg", None, [0.0, 0.0], [0], children=(61960,))
        with self.assertRaisesRegex(ValueError, "effect tree"):
            bonuses({"consumable_states": [state([parent])]})
        with self.assertRaisesRegex(ValueError, "effect tree"):
            bonuses({"consumable_states": [state([parent], roots=(999,))]})

    def test_only_attested_combat_subscriptions_are_deferred_without_world_bonuses(
        self,
    ):
        scalar = effect(66106, "eWQ", 36, [100.0, 0.0], [100])
        reactive = effect(282786, "eYg", None, [10.0, 0.0], [10], children=(67474,))
        reactive["subscription"] = True
        reactive["native_metadata"]["target_masks"] = [None] * 5 + [[1001], None]
        healing = effect(67474, "eXs", 1, [5.0, 0.0, 2.0, 0.0, 4.0, 0.0], [5, 2, 4])
        row = state([scalar, reactive, healing], roots=(66106, 282786))
        self.assertEqual(len(bonuses({"consumable_states": [row]})["unsupported"]), 1)
        row["metadata"]["combat_only_effect_ids"] = [282786]
        self.assertEqual(
            bonuses({"consumable_states": [row]}), dict(stats={36: 100}, unsupported=[])
        )
        for invalid in (66106, 67474):
            row["metadata"]["combat_only_effect_ids"] = [invalid]
            with self.subTest(root=invalid), self.assertRaises(ValueError):
                bonuses({"consumable_states": [row]})
        row["metadata"]["combat_only_effect_ids"] = [282786]
        reactive["native_metadata"]["target_masks"][5] = [999999]
        with self.assertRaisesRegex(ValueError, "combat-only consumable event"):
            bonuses({"consumable_states": [row]})


if __name__ == "__main__":
    unittest.main()
