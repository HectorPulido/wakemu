import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server import combat_definitions as candidate
from wakfu_server.combat_published_catalogs import (
    PublishedStaticMapping,
    _SEAL,
    static_row_scalar,
)


class StateProfileScalarTests(unittest.TestCase):
    def test_sealed_ranges_reuse_existing_cache_with_fresh_results_and_custom_fallback(
        self,
    ):
        state = dict(
            maximum_level=10,
            duration_base=2,
            duration_per_level=1,
            realtime_duration_base=0,
            realtime_duration_per_level=0,
            clock_actor="target",
            tick_at_turn_end=False,
            additive=True,
            replace=False,
            refresh=True,
            protected=False,
            skip_turn_timer=False,
            effect_ids=[1, 2, 3],
        )
        rows = {
            "1": {"minimum_level": 0, "maximum_level": 10},
            "2": {"minimum_level": 5, "maximum_level": 10},
            "3": {"minimum_level": 0, "maximum_level": 1},
        }
        reads = []
        reader = SimpleNamespace(
            representation="native_json",
            record_bytes=lambda key: (
                reads.append(key),
                json.dumps(rows[key]).encode(),
            )[1],
        )
        effects = PublishedStaticMapping(
            {
                "revision": "scalar-test-unique",
                "collection": "state-effects",
                "count": 3,
            },
            reader,
            _seal=_SEAL,
        )
        catalog = {"states": {"9": state}, "effects": effects}

        # Independent original expression retains Python's short circuit and lookups.
        def legacy(catalog, level):
            return [
                root
                for root in catalog["states"]["9"]["effect_ids"]
                if catalog["effects"][str(root)]["minimum_level"]
                <= level
                <= catalog["effects"][str(root)]["maximum_level"]
            ]

        static_row_scalar.cache_clear()
        self.addCleanup(static_row_scalar.cache_clear)
        expected = legacy(catalog, 2)
        self.assertEqual(reads, ["1", "1", "2", "3", "3"])
        reads.clear()
        first = candidate.state_profile(catalog, 9, 2)
        self.assertEqual(first["effects"], expected)
        self.assertEqual(reads, ["1", "1", "2", "3", "3"])
        reads.clear()
        second = candidate.state_profile(catalog, 9, 2)
        self.assertEqual(first, second)
        self.assertEqual(reads, [])
        self.assertIsNot(first, second)
        self.assertIsNot(first["effects"], second["effects"])
        first["effects"].append(999)
        self.assertEqual(candidate.state_profile(catalog, 9, 2)["effects"], expected)
        self.assertEqual(effects["1"], rows["1"])
        mutable = effects["1"]
        mutable["maximum_level"] = -999
        self.assertEqual(effects["1"], rows["1"])
        log = []

        class Custom(dict):
            def __getitem__(self, key):
                log.append(key)
                return super().__getitem__(key)

        custom = {"states": {"9": deepcopy(state)}, "effects": Custom(deepcopy(rows))}
        self.assertEqual(candidate.state_profile(custom, 9, 2)["effects"], expected)
        self.assertEqual(log, ["1", "1", "2", "3", "3"])
        custom["effects"]["1"]["maximum_level"] = 1
        log.clear()
        self.assertEqual(candidate.state_profile(custom, 9, 2)["effects"], [])
        self.assertEqual(log, ["1", "1", "2", "3", "3"])
        conversions = []

        class Root:
            def __str__(self):
                conversions.append("str")
                return "1"

        root = Root()
        special = {"states": {"9": dict(state, effect_ids=[root])}, "effects": effects}
        reads.clear()
        self.assertEqual(candidate.state_profile(special, 9, 2)["effects"], [root])
        self.assertEqual(conversions, ["str", "str"])
        self.assertEqual(reads, ["1", "1"])
        # A custom state's clamped non-exact-int level must also use legacy reads.
        special = {
            "states": {"9": dict(state, maximum_level=True, effect_ids=[1])},
            "effects": effects,
        }
        reads.clear()
        self.assertIs(candidate.state_profile(special, 9, 2)["level"], True)
        self.assertEqual(reads, ["1", "1"])
        for bad in (
            {},
            {"minimum_level": None, "maximum_level": 10},
            {"minimum_level": 0},
        ):
            for sealed in (False, True):
                static_row_scalar.cache_clear()
                rows["1"] = bad
                target = effects if sealed else deepcopy(rows)
                scoped = {
                    "states": {"9": dict(state, effect_ids=[1])},
                    "effects": target,
                }
                with self.assertRaises((KeyError, TypeError)) as old:
                    legacy(scoped, 2)
                with self.assertRaises(type(old.exception)):
                    candidate.state_profile(scoped, 9, 2)
        static_row_scalar.cache_clear()
        rows.pop("1")
        with self.assertRaises(KeyError):
            candidate.state_profile(catalog, 9, 2)
