import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_outcome_throughput import append_events, metrics


class OutcomeThroughputTests(unittest.TestCase):
    def test_event_and_entity_dedup_preserve_unique_delivery_counts(self):
        first = dict(
            event_id="one",
            kind="resolved_spell",
            ids=[7, 8],
            observed_at_utc="2026-10-13T16:00:00+00:00",
        )
        later = dict(
            event_id="two",
            kind="resolved_spell",
            ids=[8, 9],
            observed_at_utc="2026-10-13T16:01:00+00:00",
        )
        published = dict(
            event_id="three",
            kind="healthy_published_ref",
            ids=[10],
            observed_at_utc="2026-10-13T17:00:00+00:00",
        )
        events = append_events([first], [first, later, published, published])
        result = metrics(events, "2026-10-13T16:00:00+00:00")
        self.assertEqual(len(events), 3)
        self.assertEqual(result["resolved_spell"]["unique_new_count"], 3)
        self.assertEqual(
            result["resolved_spell"]["unique_new_resolved_spells_per_minute"], 3
        )
        self.assertEqual(
            result["healthy_published_ref"]["healthy_new_published_refs_per_hour"], 1
        )
