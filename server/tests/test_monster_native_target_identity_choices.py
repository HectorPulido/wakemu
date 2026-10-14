import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_target_identity_choices import positive_target_breed_choices


class NativeTargetIdentityChoiceTests(unittest.TestCase):
    def test_actual_tornado_native_breed_disjunction_preserves_source_order(self):
        criterion = 'IsBreedId("target", 1721) or IsBreedId("target", 2257) or IsBreedId("target", 3438) or IsBreedId("target", 3729) or IsBreedId("target", 3769)'
        self.assertEqual(
            positive_target_breed_choices(criterion), [1721, 2257, 3438, 3729, 3769]
        )
        self.assertEqual(
            positive_target_breed_choices(
                '(IsBreedId("target",1) or IsBreedId("target",1)) or IsBreedId("target",2)'
            ),
            [1, 2],
        )

    def test_optional_unknown_negated_and_conflicting_shapes_are_not_projected(self):
        for criterion in (
            'IsBreedId("target",1)',
            'IsBreedId("target",1) or IsEnnemy()',
            'IsBreedId("target",1) or not IsBreedId("target",2)',
            'IsBreedId("target",1) or IsBreedId("caster",2)',
            'IsBreedId("target",1) or IsBreedId("target",True)',
            '(IsBreedId("target",1) and IsBreedId("target",2)) or IsBreedId("target",3)',
        ):
            with self.subTest(criterion=criterion):
                self.assertEqual(positive_target_breed_choices(criterion), [])
        self.assertEqual(
            positive_target_breed_choices(
                'IsBreedId("target",1) or IsBreedId("target",2)', limit=1
            ),
            [],
        )
        with self.assertRaises(ValueError):
            positive_target_breed_choices("", limit=True)
