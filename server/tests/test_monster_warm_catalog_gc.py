"""Warm catalog freezing never changes native execution or leaves GC disabled."""
import unittest
from unittest.mock import patch
import consume_monster_fullbook_completions as consumer


class WarmCatalogGCTests(unittest.TestCase):
    def test_preload_collect_freeze_then_restore_gc_in_order(self):
        calls = []
        with patch.object(consumer.gc, "isenabled", return_value=True), patch.object(
            consumer.gc, "disable", side_effect=lambda: calls.append("disable")
        ), patch.object(
            consumer.gc, "collect", side_effect=lambda: calls.append("collect")
        ), patch.object(
            consumer.gc, "freeze", side_effect=lambda: calls.append("freeze")
        ), patch.object(
            consumer.gc, "enable", side_effect=lambda: calls.append("enable")
        ):
            consumer.freeze_warm_catalogs([lambda: calls.append("catalog")])
        self.assertEqual(calls, ["disable", "catalog", "collect", "freeze", "enable"])

    def test_preload_failure_propagates_and_restores_previous_gc(self):
        def broken():
            raise ValueError("actual catalog failure")

        with patch.object(consumer.gc, "isenabled", return_value=True), patch.object(
            consumer.gc, "disable"
        ), patch.object(consumer.gc, "freeze") as freeze, patch.object(
            consumer.gc, "enable"
        ) as enable:
            with self.assertRaisesRegex(ValueError, "actual catalog failure"):
                consumer.freeze_warm_catalogs([broken])
            freeze.assert_not_called()
            enable.assert_called_once_with()
