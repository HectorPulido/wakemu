import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_root_ko_scene import root_required_ko_ally_scene


class NativeRootKoSceneTests(unittest.TestCase):
    def test_actual_native_duna_and_hipoliro_root_conjuncts_request_real_ko_scene(self):
        # Original roots 166893 and 235556/238448 share this exact native criterion.
        root = {"criteria": 'IsOffPlay("target") and not IsEnnemy()'}
        self.assertEqual(root_required_ko_ally_scene([root]), "knocked_out_ally")
        self.assertEqual(
            root_required_ko_ally_scene([root, dict(root)]), "knocked_out_ally"
        )

    def test_mixed_root_or_optional_ko_branch_does_not_require_corpse_scene(self):
        required = {"criteria": 'IsOffPlay("target") and not IsEnnemy()'}
        for roots in (
            [],
            [None],
            [{}],
            [required, {}],
            [{"criteria": 'IsOffPlay("target") or not IsEnnemy()'}],
            [{"criteria": 'IsOffPlay("caster") and not IsEnnemy()'}],
            [{"criteria": 'not IsOffPlay("target") and not IsEnnemy()'}],
        ):
            with self.subTest(roots=roots):
                self.assertIsNone(root_required_ko_ally_scene(roots))
