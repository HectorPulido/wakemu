"""Literal private exits and existing public fallbacks share step-return checks."""
from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase
from wakfu_server import owned_story_terminal_returns as returns

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server/maps/owned_story_profiles"


class NativePrivateStepReturnTests(TestCase):
    def test_note_return_uses_the_exact_original_private_exit(self):
        selected = json.loads((ROOT / "wild-estate-brak-723.v2.json").read_text())
        self.assertEqual(
            returns.policy(selected)["after_steps"], ["staff-sufokia-note"]
        )
        self.assertEqual(
            returns._step_destination(selected, selected["terminal_returns"]),
            dict(map_id=714, x=9, y=-3, z=0),
        )
        changed = deepcopy(selected)
        changed["terminal_returns"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "exact original source"):
            returns.policy(changed)

    def test_existing_kelba_public_fallback_is_unchanged(self):
        selected = json.loads((ROOT / "kelba-convoy-947.json").read_text())
        declaration = returns.policy(selected)
        self.assertEqual(
            returns._step_destination(selected, declaration)["map_id"], 943
        )
