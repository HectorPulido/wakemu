from unittest.mock import patch
import unittest
from wakfu_server.combat_character_copy_models import native_class_copy_model


class CopyModelTests(unittest.TestCase):
    def test_published_original_class_model_source_is_complete(self):
        from wakfu_server.combat_character_copy_models import _models

        rows = _models()
        self.assertEqual(len(rows), 18)
        self.assertEqual(
            sum(len(models) for sexes in rows.values() for models in sexes.values()),
            9216,
        )
        self.assertEqual(native_class_copy_model(9, 0, 0), 90)
        self.assertEqual(native_class_copy_model(9, 1, 0), 91)

    def test_all_signed_cloth_values_select_the_original_index(self):
        models = list(range(-128, 128))
        with patch(
            "wakfu_server.combat_character_copy_models._models",
            return_value={"15": {"0": models, "1": list(reversed(models))}},
        ):
            for cloth in range(-128, 128):
                self.assertEqual(native_class_copy_model(15, 0, cloth), cloth)
                self.assertEqual(native_class_copy_model(15, 1, cloth), -1 - cloth)
            with self.assertRaises(ValueError):
                native_class_copy_model(9, 0, 0)

    def test_untyped_or_unknown_operands_are_rejected(self):
        for arguments in ((True, 0, 0), (15, 2, 0), (15, 0, 128), (15, 0, -129)):
            with self.assertRaises(ValueError):
                native_class_copy_model(*arguments)
