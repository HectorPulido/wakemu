"""The duel controller must be explicitly enabled per bot."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bot-service"))

from wakfu_bots.behaviors import BehaviorRegistry
from wakfu_bots.config import Profiles


class FriendlyDuelBehaviorTests(unittest.TestCase):
    def test_capability_is_opt_in_and_only_duel_is_added(self):
        base = {
            "bot_id": "duelist",
            "character": {"name": "Duelist", "breed": 15, "sex": 0},
            "enabled": True,
            "capabilities": [],
            "behaviors": {"friendly_duel": {}},
        }
        with tempfile.TemporaryDirectory() as directory:
            profiles = Profiles(Path(directory) / "profiles.json")
            duelist = profiles.put("duelist", base)
            registry = BehaviorRegistry()
            self.assertEqual(["duel"], registry.world_capabilities(duelist))
            self.assertEqual(
                [], registry.decide(duelist, {"type": "other", "payload": {}})
            )
            with self.assertRaises(ValueError):
                profiles.validate(
                    {**base, "behaviors": {"friendly_duel": {"auto": True}}}
                )
            ordinary = profiles.validate(
                {
                    **base,
                    "behaviors": {
                        "announcer": {"interval_seconds": 30, "text": "Hello"}
                    },
                }
            )
            self.assertEqual(["chat"], registry.world_capabilities(ordinary))


if __name__ == "__main__":
    unittest.main()
