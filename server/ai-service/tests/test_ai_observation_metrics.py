"""Tactical metadata projections exclude validated opaque native receipts."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from test_query_search import FakeNativeSession
from wakfu_ai.planning.actor_roles import actor_role_profile
from wakfu_ai.planning.query_search import _metrics


def observation(receipt="receipt-a", revision=97):
    session = FakeNativeSession(spells=[], cells=[(0, 0, 0)], edges=[])
    raw = deepcopy(session.root_state)
    raw.update(key=receipt, stateRevision=revision)
    raw["actorRepertoires"] = {
        "1": dict(
            actorId=1,
            sourceState=receipt,
            stateRevision=revision,
            unknownDependencies=[],
            spells=[
                dict(
                    spellId=5,
                    level=1,
                    costOptions=[dict(ap=1, mp=0, wp=0)],
                    advisoryCapabilities=dict(
                        spellId=5,
                        level=1,
                        minimum=0,
                        maximum=2,
                        tags=["damage", "heal"],
                        allyTarget=True,
                        unknownDependencies=[],
                        conditional=False,
                    ),
                )
            ],
        )
    }
    return raw


class ObservationMetricsTests(unittest.TestCase):
    def test_full_metrics_equal_when_only_validated_receipts_differ(self):
        first, second = observation(), observation("receipt-b", 98)
        first["runtimeIdentity"] = "a" * 64
        second["runtimeIdentity"] = "b" * 64
        self.assertEqual(_metrics(first, 1), _metrics(second, 1))
        self.assertNotEqual(first["key"], second["key"])
        self.assertNotEqual(first["runtimeIdentity"], second["runtimeIdentity"])

    def test_stale_metadata_is_rejected_and_source_receipts_are_untouched(self):
        raw = observation()
        before = deepcopy(raw)
        projected = _metrics(raw, 1)["actorRepertoires"]["1"]
        self.assertNotIn("sourceState", projected)
        self.assertNotIn("stateRevision", projected)
        self.assertEqual(raw, before)
        self.assertIsNot(projected, raw["actorRepertoires"]["1"])
        for field, invalid in (
            ("sourceState", "foreign-receipt"),
            ("stateRevision", 98),
        ):
            with self.subTest(field=field):
                stale = deepcopy(raw)
                stale["actorRepertoires"]["1"][field] = invalid
                self.assertEqual(_metrics(stale, 1)["actorRepertoires"], {})

    def test_projection_preserves_actor_roles_and_all_semantic_metadata(self):
        raw = observation()
        expected = actor_role_profile(raw, 1)
        metrics = _metrics(raw, 1)
        self.assertIn("damage_ranged", expected["useful_roles"])
        self.assertEqual(actor_role_profile(metrics, 1), expected)
        source = raw["actorRepertoires"]["1"]
        for field in set(source) - {"sourceState", "stateRevision"}:
            self.assertEqual(metrics["actorRepertoires"]["1"][field], source[field])


if __name__ == "__main__":
    unittest.main()
