"""Native class and suffix routing for the shared cqd13220 opcode."""
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server import cosmetic_learning


class ItemLearningRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        cls.rules = _rules()
        cls.by_class = {}
        for item_ref, row in cls.rules.items():
            cls.by_class.setdefault(row.get("use_action_class"), (item_ref, row))

    def body_for(self, native_class):
        item_ref, row = self.by_class[native_class]
        action = row["use_action_id"]
        body = struct.pack(">iq", action, 7)
        if native_class in ("bHv", "bIi"):
            body += struct.pack(">q", 9) if native_class == "bHv" else b"\x00" * 8
        return body

    def test_all_nine_learning_classes_and_planting_keep_their_native_suffix_sizes(
        self,
    ):
        expected = {"bHv", "bIA", "bIB", "bIs", "bIt", "bIv", "bIw", "bIx", "bIz"}
        for native_class in expected:
            with self.subTest(native_class=native_class):
                self.assertEqual(
                    cosmetic_learning.request_action_class(self.body_for(native_class)),
                    native_class,
                )
        self.assertEqual(
            cosmetic_learning.request_action_class(self.body_for("bIi")), "bIi"
        )

        with self.assertRaises(ValueError):
            cosmetic_learning.request_action_class(self.body_for("bHv")[:12])
        with self.assertRaises(ValueError):
            cosmetic_learning.request_action_class(self.body_for("bIt") + b"\x00" * 8)
        with self.assertRaises(ValueError):
            cosmetic_learning.request_action_class(self.body_for("bIi")[:12])

    def test_unknown_ambiguous_and_invalid_mimic_targets_are_rejected(self):
        with self.assertRaises(ValueError):
            cosmetic_learning.request_action_class(struct.pack(">iq", 2**30, 7))

        body = self.body_for("bIt")
        action_id = struct.unpack_from(">i", body)[0]
        ambiguous = dict(self.rules)
        ambiguous[-1] = {
            "use_action_class": "bIA",
            "use_action_id": action_id,
            "use_has_criteria": False,
        }
        with patch(
            "wakfu_server.haven_bag_furniture_knowledge._rules", return_value=ambiguous
        ):
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                cosmetic_learning.request_action_class(body)

        mimic = bytearray(self.body_for("bHv"))
        struct.pack_into(">q", mimic, 12, 0)
        with self.assertRaisesRegex(ValueError, "mimic target"):
            cosmetic_learning.request_action_class(bytes(mimic))

    def test_dispatch_selects_the_handler_from_native_class_and_never_routes_bii_to_learning(
        self,
    ):
        module_names = {
            "bHv": "wakfu_server.mimisymbic_learning",
            "bIA": "wakfu_server.haven_ranch_building_knowledge",
            "bIB": "wakfu_server.recipe_learning",
            "bIv": "wakfu_server.haven_bag_view_learning",
            "bIw": "wakfu_server.emote_learning",
            "bIx": "wakfu_server.haven_bag_furniture_knowledge",
            "bIz": "wakfu_server.recipe_learning",
        }
        for native_class, module_name in module_names.items():
            with self.subTest(native_class=native_class):
                handler = Mock(return_value={"class": native_class})
                with patch(
                    "importlib.import_module",
                    return_value=SimpleNamespace(learn=handler),
                ) as import_module:
                    result = cosmetic_learning.learn_item(
                        object(), 1, 2, 3, self.body_for(native_class)
                    )
                self.assertEqual(result, {"class": native_class})
                import_module.assert_called_once_with(module_name)
                handler.assert_called_once()

        for native_class, kind in (("bIs", "title"), ("bIt", "cosmetic")):
            with self.subTest(native_class=native_class):
                with patch(
                    "wakfu_server.cosmetic_learning.learn",
                    return_value={"kind": kind},
                ) as handler:
                    result = cosmetic_learning.learn_item(
                        object(), 1, 2, 3, self.body_for(native_class)
                    )
                self.assertEqual(result, {"kind": kind})
                self.assertEqual(handler.call_args.kwargs, {"kind": kind})

        with patch("importlib.import_module") as import_module:
            with self.assertRaisesRegex(ValueError, "Planting requires"):
                cosmetic_learning.learn_item(object(), 1, 2, 3, self.body_for("bIi"))
        import_module.assert_not_called()
