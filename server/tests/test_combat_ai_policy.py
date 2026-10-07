"""Validation and encounter-freezing tests for native tactical profiles."""
import copy
import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from wakfu_server.combat_ai_policy import encounter_profiles, validate_profile


def profile(name="default", version=1, policy=None, forecast=None):
    return {
        "profile": name,
        "version": version,
        "policy": {} if policy is None else policy,
        "forecast_limits": {} if forecast is None else forecast,
    }


class RowsDB:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params):
        return iter(copy.deepcopy(self.rows))


class RowsStore:
    def __init__(self, rows):
        self.rows = rows
        self.reads = 0

    @contextmanager
    def connection(self):
        self.reads += 1
        yield RowsDB(self.rows)


class CombatAiPolicyTests(unittest.TestCase):
    def test_profile_rejects_invalid_types_bounds_names_and_nonfinite_values(self):
        invalid_rows = [
            profile(name="Upper"),
            profile(version=True),
            profile(version=0),
            profile(policy={"depth": True}),
            profile(policy={"depth": 17}),
            profile(policy={"beam": 65}),
            profile(forecast={"max_previews": 257}),
            profile(forecast={"budget_ms": 0}),
            profile(policy={"weights": {"damage": -0.1}}),
            profile(policy={"weights": {"unknown_metric": 1}}),
            profile(policy={"featureWeights": {"threat": float("nan")}}),
            profile(policy={"featureWeights": {"threat": float("inf")}}),
            profile(policy={"extra": 1}),
            profile(forecast={"timeout": 20}),
        ]
        for row in invalid_rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                validate_profile(row)

    def test_valid_identity_is_canonical_and_includes_policy(self):
        base = profile(
            policy={"weights": {"damage": 2}, "featureWeights": {"threat": -0.5}},
            forecast={"depth": 3, "max_previews": 80, "budget_ms": 1200},
        )
        reordered = profile(
            policy={"featureWeights": {"threat": -0.5}, "weights": {"damage": 2}},
            forecast={"budget_ms": 1200, "max_previews": 80, "depth": 3},
        )
        first = validate_profile(base)
        self.assertEqual(first, validate_profile(reordered))
        changed = copy.deepcopy(base)
        changed["policy"]["weights"]["damage"] = 3
        self.assertNotEqual(first["identity"], validate_profile(changed)["identity"])

    @staticmethod
    def runtime(fight_id=10):
        actors = {
            -10: SimpleNamespace(id=-10, controlled=False),
            7: SimpleNamespace(id=7, controlled=True),
        }
        return SimpleNamespace(fight=SimpleNamespace(id=fight_id, actors=actors))

    @staticmethod
    def rows(default=None, overrides=None):
        rows = [dict(default or profile(), monster_reference=None)]
        rows.extend(overrides or [])
        return rows

    def test_default_and_monster_override_are_bound_once_per_encounter(self):
        default = profile("default", policy={"weights": {"damage": 1}})
        override = profile("aggressive", 2, policy={"weights": {"damage": 5}})
        store = RowsStore(self.rows(default, [dict(override, monster_reference=501)]))
        runtime = self.runtime()
        monsters = {-10: {"ref": 501}}

        first = encounter_profiles(runtime, store, monsters)
        self.assertEqual(first[None]["profile"], "default")
        self.assertEqual(first[501]["profile"], "aggressive")
        self.assertEqual(store.reads, 1)

        first[501]["policy"]["weights"]["damage"] = 999
        store.rows[:] = self.rows(profile("updated", 3), [])
        again = encounter_profiles(runtime, store, monsters)
        self.assertEqual(again[501]["policy"]["weights"]["damage"], 5)
        self.assertEqual(store.reads, 1)

        new_encounter = self.runtime(fight_id=11)
        updated = encounter_profiles(new_encounter, store, monsters)
        self.assertEqual(updated[None]["profile"], "updated")
        self.assertNotIn(501, updated)
        self.assertEqual(store.reads, 2)

    def test_invalid_override_does_not_publish_partial_encounter_cache(self):
        default = profile("default")
        invalid_override = profile("broken", policy={"depth": 17})
        store = RowsStore(
            self.rows(default, [dict(invalid_override, monster_reference=501)])
        )
        runtime = self.runtime()

        with self.assertRaises(ValueError):
            encounter_profiles(runtime, store, {-10: {"ref": 501}})
        self.assertFalse(hasattr(runtime, "tactical_profiles"))

        store.rows = self.rows(
            default, [dict(profile("safe", 1), monster_reference=501)]
        )
        result = encounter_profiles(runtime, store, {-10: {"ref": 501}})
        self.assertEqual(result[501]["profile"], "safe")
        self.assertEqual(store.reads, 2)


if __name__ == "__main__":
    unittest.main()
