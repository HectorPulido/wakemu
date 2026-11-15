"""World policy validation; native simulation coverage lives in weather_planner_contract.rs.

The Rust planner contracts exercise SQL cursor/restart, atomicity, overrides,
configuration, exact instances, and transition locking. Native weather unit
vectors cover deterministic climate and forecast encoding.
"""

import unittest

from wakfu_server import territory_weather_simulation as simulation

POLICY = dict(
    enabled=True,
    seed=20261011,
    day_seconds=86400,
    forecast_days=5,
    weather_weights=[60, 25, 12, 3],
    season_temperature_samples=[2, 12, 23, 12],
    temperature_variation=5,
    wind_samples=[13107, 22937, 42598, 62258],
)


class RegionalWeatherPolicyTests(unittest.TestCase):
    def test_world_rejects_invalid_operator_simulation_policy(self):
        for name, value in (
            ("enabled", 1),
            ("day_seconds", True),
            ("forecast_days", 256),
            ("weather_weights", [0, 0, 0, 0]),
            ("seed", -1),
            ("season_temperature_samples", [127] * 4),
            ("wind_samples", [65536] * 4),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                simulation.validate_policy(dict(POLICY, **{name: value}))

    def test_world_preserves_valid_operator_policy(self):
        self.assertEqual(simulation.validate_policy(POLICY), POLICY)


if __name__ == "__main__":
    unittest.main()
