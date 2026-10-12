"""Resource rejections retain detached facts without changing combat state."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_cast import _validate_target


class ResourceRejectionDiagnosticsTests(unittest.TestCase):
    def test_each_insufficient_resource_reports_exact_deficit_without_payment(self):
        for resource in ("ap", "mp", "wp"):
            with self.subTest(resource=resource):
                actor = SimpleNamespace(ap=3, mp=3)
                costs = {"ap": 2, "mp": 2, "wp": 2}
                costs[resource] = 5
                before = dict(costs)
                context = SimpleNamespace(
                    actors={"caster": SimpleNamespace(fight_properties=frozenset())}
                )
                with self.assertRaisesRegex(
                    ValueError, "Insufficient authoritative spell resources"
                ) as raised:
                    _validate_target(
                        {}, actor, None, 3, costs, {}, (), 1, None, 1, context
                    )
                diagnostic = raised.exception.native_resource_diagnostic
                self.assertEqual(diagnostic["available"], dict(ap=3, mp=3, wp=3))
                self.assertEqual(diagnostic["required"], before)
                self.assertEqual(diagnostic["deficits"], {resource: 2})
                self.assertEqual(
                    raised.exception.cast_validation_code, "insufficient_resources"
                )
                self.assertEqual(costs, before)
                self.assertEqual((actor.ap, actor.mp), (3, 3))
                costs[resource] = 99
                self.assertEqual(diagnostic["required"][resource], 5)


if __name__ == "__main__":
    unittest.main()
