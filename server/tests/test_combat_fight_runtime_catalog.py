import unittest
from unittest.mock import Mock
from wakfu_server.combat_fight_runtime_catalog import fight_runtime_catalog


class RuntimeCatalogTests(unittest.TestCase):
    def test_actual_npc_participants_select_existing_npc_definition_union(self):
        classes, npc = Mock(return_value=object()), Mock(return_value=object())
        actual = {-200: {"reference": 3539, "level": 156}}
        before = dict(actual)
        self.assertIs(
            fight_runtime_catalog(actual, None, class_catalog=classes, npc_catalog=npc),
            npc.return_value,
        )
        npc.assert_called_once_with()
        classes.assert_not_called()
        self.assertEqual(actual, before)

    def test_class_only_fight_preserves_original_catalog(self):
        classes, npc = Mock(return_value=object()), Mock()
        self.assertIs(
            fight_runtime_catalog({}, None, class_catalog=classes, npc_catalog=npc),
            classes.return_value,
        )
        classes.assert_called_once_with()
        npc.assert_not_called()

    def test_explicit_catalog_is_authoritative_even_when_falsey(self):
        classes, npc = Mock(), Mock()
        explicit = {}
        self.assertIs(
            fight_runtime_catalog(
                {-200: {}}, explicit, class_catalog=classes, npc_catalog=npc
            ),
            explicit,
        )
        classes.assert_not_called()
        npc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
