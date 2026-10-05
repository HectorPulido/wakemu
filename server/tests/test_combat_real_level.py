import unittest
from types import SimpleNamespace as Actor
from wakfu_server.combat_real_level import native_real_level


class RealLevelTests(unittest.TestCase):
    def context(self):
        return Actor(
            actors={
                "caster": Actor(
                    is_native_fighter=True, real_level=200, effective_level=20
                ),
                "target": Actor(
                    is_native_fighter=True, real_level=10, effective_level=10
                ),
                "eventTarget": Actor(is_native_fighter=True, real_level=60),
            }
        )

    def test_real_level_is_not_modulation_and_selectors_match_native(self):
        context = self.context()
        self.assertEqual(native_real_level(context), 200)
        self.assertEqual(native_real_level(context, "TARGET"), 10)
        self.assertEqual(native_real_level(context, "eventTarget"), 60)
        self.assertEqual(native_real_level(context, "EVENTTARGET"), 200)

    def test_missing_context_never_substitutes_effective_level(self):
        context = self.context()
        context.actors["caster"].real_level = None
        with self.assertRaises(ValueError):
            native_real_level(context)
        with self.assertRaises(ValueError):
            native_real_level(Actor(actors={}))

    def test_non_fighter_native_minus_one_and_unknown_type(self):
        context = self.context()
        context.actors["caster"].is_native_fighter = False
        self.assertEqual(native_real_level(context), -1)
        context.actors["caster"].is_native_fighter = None
        with self.assertRaises(ValueError):
            native_real_level(context)
