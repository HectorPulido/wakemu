"""Policy profile snapshots preserve full database rows and encounter identity."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.native.native_profiles import encounter_profiles


class ProfileDB:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        return iter(deepcopy(self.rows))


class ProfileStore:
    def __init__(self, rows):
        self.db = ProfileDB(rows)
        self.entries = 0

    class Connection:
        def __init__(self, store):
            self.store = store

        def __enter__(self):
            self.store.entries += 1
            return self.store.db

        def __exit__(self, *_):
            return False

    def connection(self):
        return self.Connection(self)


def row(
    reference,
    profile,
    version,
    policy,
    *,
    future_blob=b"opaque\x00\xff",
    timestamp=None
):
    return {
        "monster_reference": reference,
        "profile": profile,
        "version": version,
        "policy": deepcopy(policy),
        "forecast_limits": {"native_depth": 2},
        "future_bytes": future_blob,
        "future_timestamp": timestamp
        or datetime(2026, 10, 7, 12, 30, tzinfo=timezone.utc),
        "future_metadata": {"format": 9, "nested": [b"preserved"]},
    }


def runtime():
    return type("Runtime", (), {})()


class NativeProfileTests(unittest.TestCase):
    def test_default_and_monster_binding_normalize_limits_but_keep_raw_columns(self):
        global_row = row(
            None,
            "steady",
            4,
            {"nodes": 80, "depth": 3, "limits": {"nodes": 20, "extension": 7}},
        )
        bound_row = row(777, "aggressive", 2, {"limits": {"beam": 5}})
        store = ProfileStore([global_row, bound_row])
        encounter = runtime()

        profiles = encounter_profiles(encounter, store, {3: {"id": 3, "ref": 777}})

        self.assertEqual(store.entries, 1)
        self.assertIn("REPEATABLE READ READ ONLY", store.db.statements[0][0])
        self.assertIsNone(store.db.statements[1][1])
        self.assertNotIn("WHERE", store.db.statements[1][0])
        self.assertEqual(profiles[None]["identity"].split(":")[:2], ["steady", "4"])
        self.assertEqual(profiles[777]["identity"].split(":")[:2], ["aggressive", "2"])
        self.assertEqual(
            profiles[None]["policy"]["limits"],
            {"depth": 3, "nodes": 20, "extension": 7},
        )
        self.assertEqual(profiles[None]["data"]["policy"]["nodes"], 80)
        self.assertEqual(profiles[None]["data"]["forecast_limits"], {"native_depth": 2})
        self.assertEqual(profiles[None]["data"]["future_bytes"], b"opaque\x00\xff")
        self.assertEqual(
            profiles[None]["data"]["future_timestamp"], global_row["future_timestamp"]
        )
        self.assertEqual(
            profiles[None]["data"]["future_metadata"], global_row["future_metadata"]
        )

    def test_reused_runtime_reloads_profiles_for_new_fight_uuid(self):
        from types import SimpleNamespace

        encounter = runtime()
        encounter.fight = SimpleNamespace(id=42, native_ai_fight_uuid="first")
        store = ProfileStore([row(None, "steady", 1, {})])
        encounter_profiles(encounter, store, {})
        encounter.fight.native_ai_fight_uuid = "second"
        store.db.rows = [row(None, "steady", 2, {})]
        profiles = encounter_profiles(encounter, store, {})
        self.assertEqual(store.entries, 2)
        self.assertEqual(profiles[None]["data"]["version"], 2)

    def test_future_column_changes_stable_profile_identity(self):
        timestamp = datetime(2026, 10, 7, tzinfo=timezone.utc)
        first = encounter_profiles(
            runtime(),
            ProfileStore(
                [row(None, "steady", 1, {}, future_blob=b"first", timestamp=timestamp)]
            ),
            {},
        )[None]
        second = encounter_profiles(
            runtime(),
            ProfileStore(
                [row(None, "steady", 1, {}, future_blob=b"second", timestamp=timestamp)]
            ),
            {},
        )[None]
        self.assertNotEqual(first["identity"], second["identity"])

    def test_future_registered_breed_uses_its_binding_frozen_before_it_exists(self):
        encounter = runtime()
        store = ProfileStore([row(None, "default", 1, {}), row(999, "summoner", 2, {})])
        before = encounter_profiles(encounter, store, {10: {"ref": 777}})
        after = encounter_profiles(
            encounter, store, {10: {"ref": 777}, 901: {"ref": 999}}
        )
        self.assertEqual(after[999]["identity"], before[999]["identity"])
        self.assertEqual(after[999]["data"]["profile"], "summoner")
        self.assertEqual(store.entries, 1)

    def test_profiles_freeze_once_for_encounter_and_unbound_future_summon_uses_default(
        self,
    ):
        encounter = runtime()
        store = ProfileStore(
            [row(None, "default", 3, {"depth": 2}), row(777, "boss", 1, {"depth": 4})]
        )
        first = encounter_profiles(encounter, store, {10: {"id": 10, "ref": 777}})
        frozen_identity = first[None]["identity"]
        # A newly registered summon introduces a reference after encounter
        # startup. The frozen profile map remains stable and selection falls
        # back to the already-frozen default profile.
        second = encounter_profiles(
            encounter, store, {10: {"id": 10, "ref": 777}, 11: {"id": 11, "ref": 999}}
        )
        selected = second.get(999, second[None])
        self.assertEqual(store.entries, 1)
        self.assertEqual(selected["identity"], frozen_identity)
        self.assertEqual(selected["data"]["profile"], "default")
        self.assertEqual(first, second)

    def test_default_profile_and_duplicate_bindings_are_required_to_be_unambiguous(
        self,
    ):
        with self.assertRaisesRegex(ValueError, "Missing default native AI profile"):
            encounter_profiles(runtime(), ProfileStore([row(777, "boss", 1, {})]), {})
        with self.assertRaisesRegex(ValueError, "Ambiguous native AI profile binding"):
            encounter_profiles(
                runtime(),
                ProfileStore(
                    [
                        row(None, "default", 1, {}),
                        row(777, "boss", 1, {}),
                        row(777, "other", 2, {}),
                    ]
                ),
                {1: {"id": 1, "ref": 777}},
            )


if __name__ == "__main__":
    unittest.main()
