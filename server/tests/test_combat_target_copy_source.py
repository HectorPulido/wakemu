"""Target-copy keeps actual raw object UIDs across morph/grant overlays."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from wakfu_server.combat_state import Actor
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_spell_level import NativeSpellBook
from wakfu_server.combat_target_copy_source import target_copy_raw_records


class TargetCopySourceTests(unittest.TestCase):
    def fixture(self, levels):
        target = Actor(7, 0, (0, 0, 0), 10, 6, 3, 1, 20)
        fight = SimpleNamespace(actors={7: target})
        metadata = NativeActorAuthority(
            {},
            False,
            frozenset(),
            frozenset(),
            False,
            999,
            0,
            {},
            True,
            native_spellbook=NativeSpellBook(levels, False),
        )
        return fight, target, lambda fight, actor: metadata

    def test_actual_morph_order_borrowed_uids_removals_and_grants(self):
        fight, target, authority = self.fixture({20: 5, 10: 4, 40: 8})
        with patch(
            "wakfu_server.combat_morph_spellbook.morph_record",
            return_value={"levels": {20: 5, 30: 3, 10: 4}},
        ), patch(
            "wakfu_server.combat_spell_grant_book.removed_raw_uids", return_value={30}
        ), patch(
            "wakfu_server.combat_spell_grant.granted_spells",
            return_value={40: {"uid": 40, "reference": 40, "level": 8}},
        ):
            records, producer = target_copy_raw_records(fight, target, authority)
        self.assertEqual(records, ((20, 20, 5), (10, 10, 4), (40, 40, 8)))
        self.assertEqual(producer, "big.bPu.current_raw_book")

    def test_incomplete_raw_source_or_alias_never_uses_level_map_as_inventory(self):
        fight, target, authority = self.fixture({20: 5, 10: 4})
        with patch(
            "wakfu_server.combat_morph_spellbook.morph_record",
            return_value={"levels": {20: 5}},
        ), patch(
            "wakfu_server.combat_spell_grant_book.removed_raw_uids", return_value=set()
        ), patch(
            "wakfu_server.combat_spell_grant.granted_spells", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "disagrees"):
                target_copy_raw_records(fight, target, authority)
        alias = Actor(7, 0, (0, 0, 0), 10, 6, 3, 1, 20)
        with self.assertRaisesRegex(ValueError, "identity"):
            target_copy_raw_records(fight, alias, authority)
