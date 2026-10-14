"""Native eZc subscriptions retain fresh identity before reflection activation."""
import unittest

from test_combat_subscription_runners import fields
from wakfu_server.combat_subscription_runners import (
    DEFERRED_RUNNERS,
    SUBSCRIPTION_FAMILIES,
    deferred_payload,
)


class DeferredReflection309Tests(unittest.TestCase):
    def fixture(self):
        return dict(
            uid=91,
            base_uid=90,
            generic_effect=68565,
            caster_id=7,
            target_id=7,
            cell=(1, 2, 0),
            timing_payload=b"",
            container_type=1,
            container_id=842,
        )

    def test_reflection_is_registered_as_its_actual_native_runner(self):
        self.assertEqual(DEFERRED_RUNNERS[309], "eZc")
        self.assertIn(309, SUBSCRIPTION_FAMILIES)

    def test_fresh_reflection_uses_inherited_base_wire_without_calculation(self):
        args = self.fixture()
        before = dict(args)
        payload = deferred_payload(family=309, **args)
        # Installed eZc has only super() and empty C(Qe), with no wire override.
        self.assertEqual(payload, deferred_payload(family=421, **args))
        parsed = fields(payload)
        self.assertEqual(parsed[3], 68565)
        self.assertEqual(parsed[4], 0)
        self.assertNotIn(8, parsed)
        self.assertEqual((parsed[9], parsed[10]), (1, 842))
        self.assertEqual(args, before)

    def test_unknown_runner_and_unpaired_container_still_reject(self):
        with self.assertRaisesRegex(ValueError, "Unaudited deferred"):
            deferred_payload(family=999999, **self.fixture())
        args = self.fixture()
        args["container_id"] = None
        with self.assertRaisesRegex(ValueError, "Missing paired"):
            deferred_payload(family=309, **args)


if __name__ == "__main__":
    unittest.main()
