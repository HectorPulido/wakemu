"""Bounded ownership and public removal/export seam regression."""
import pathlib
import tempfile
import types
import unittest
from unittest.mock import patch

from wakfu_server import combat_closed_fight_observation as observer
from wakfu_server.combat_shared import Registry
from wakfu_server import performance_monitor


class Node:
    pass


class ObservationTests(unittest.TestCase):
    def test_removal_releases_graph_and_export_reports_weak_liveness(self):
        fight = Node()
        fight.id = 444
        fight.actors = {191: object()}
        runtime = Node()
        runtime.fight = fight
        shared = Node()
        shared.fight = fight
        shared.runtime = runtime
        shared.participants = {}
        shared.join_aliases = {}
        registry = Node()
        registry.fights = {444: shared}
        registry.by_actor = {191: 444}
        registry.by_character = {191: 444}
        registry.join_aliases = {}
        observer._ROWS.clear()
        with patch.object(observer, "ENABLED", True):
            Registry._remove_locked(registry, shared)
            row = observer.snapshot()["removed"][0]
            self.assertTrue(row["fight_alive"])
            self.assertTrue(row["runtime_alive"])
            self.assertEqual(
                row["registry_counts_at_removal"],
                dict(fights=0, actors=0, characters=0),
            )
            del shared, runtime, fight
            row = observer.snapshot()["removed"][0]
            self.assertFalse(row["fight_alive"])
            self.assertFalse(row["runtime_alive"])
            profiler = types.SimpleNamespace(snapshot=lambda: {})
            gc_monitor = types.SimpleNamespace(
                history_snapshot=lambda: [], long_pause_history_snapshot=lambda: []
            )
            with tempfile.TemporaryDirectory() as tmp:
                import json

                path = pathlib.Path(tmp) / "report.json"
                performance_monitor.write_report(profiler, path, gc_monitor=gc_monitor)
                self.assertFalse(
                    json.loads(path.read_text())["closed_fight_ownership"]["removed"][
                        0
                    ]["fight_alive"]
                )

    def test_disabled_and_bounded_storage_do_not_own_graphs(self):
        observer._ROWS.clear()
        with patch.object(observer, "ENABLED", False):
            observer.record_removed(None, None)
            self.assertIsNone(observer.snapshot())
            self.assertEqual(len(observer._ROWS), 0)
        with patch.object(observer, "ENABLED", True):
            for uid in range(20):
                fight = Node()
                fight.id = uid
                runtime = Node()
                registry = types.SimpleNamespace(
                    fights={}, by_actor={}, by_character={}
                )
                observer.record_removed(
                    registry, types.SimpleNamespace(fight=fight, runtime=runtime)
                )
            del fight, runtime
            rows = observer.snapshot()["removed"]
            self.assertEqual([r["fight_id"] for r in rows], list(range(4, 20)))
            self.assertTrue(
                all(not r["fight_alive"] and not r["runtime_alive"] for r in rows)
            )


if __name__ == "__main__":
    unittest.main()
