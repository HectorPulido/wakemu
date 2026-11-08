"""Caster-only native delivery does not enumerate unrelated PV populations."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_global_pv_collections as module


class GlobalCasterLocalTests(unittest.TestCase):
    def fixture(self):
        fight = SimpleNamespace(
            actors={7: object(), -1: object()}, native_effect_areas={}
        )
        module.initialize_global_pv_collections(fight, (7, -1))
        return fight

    def test_native_caster_only_avoids_population_reads_and_preserves_fallback(self):
        class NoIteration(dict):
            def __iter__(self):
                raise AssertionError("Unrelated actor iteration")

        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                fight = self.fixture()
                if not explicit:
                    module.set_global_pv_mode(fight, "rRo")
                fight.actors = NoIteration(fight.actors)
                with patch.object(
                    module.NativeTroveLongMap,
                    "order",
                    side_effect=AssertionError("Unneeded Trove ordering"),
                ):
                    iterator = module.global_pv_iterator(
                        fight, caster_id=900, caster_only=True if explicit else None
                    )
                    # An area/detached PV caster need not be in fighter history.
                    fight.native_global_pv_collections["fighter_status"].clear()
                    self.assertEqual(list(iterator), [900])
        fight = self.fixture()
        calls = []
        original = module.native_global_event_iterator

        def custom(**kwargs):
            calls.append(kwargs["fighter_order"])
            return original(**kwargs)

        with patch.object(module, "native_global_event_iterator", custom):
            self.assertEqual(
                list(module.global_pv_iterator(fight, caster_id=900, caster_only=True)),
                [900],
            )
        self.assertTrue(calls[0])  # Custom provider keeps its actual segments.
        for mode, caster, message in (
            (1, 7, "Explicit native iterator"),
            (True, None, "Actual native PV caster"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                list(
                    module.global_pv_iterator(fight, caster_id=caster, caster_only=mode)
                )
        fight.native_global_pv_collections["source"] = "foreign"
        with self.assertRaisesRegex(ValueError, "producer"):
            module.global_pv_iterator(fight, caster_id=900, caster_only=True)


if __name__ == "__main__":
    unittest.main()
