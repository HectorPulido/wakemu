import unittest
from itertools import count
from types import SimpleNamespace
from wakfu_server.spells import encode_deck
from wakfu_server.spells import owned_spell_records
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_character_copy_runtime_book import (
    copied_class_source_deck,
    copied_class_book,
)


class CopiedDeckSourceTests(unittest.TestCase):
    def authority(self, blob):
        return OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=7, level=200)},
            monsters={},
            decks={7: frozenset((623, 0))},
            deck_caps={7: 200},
            excluded_decks={7: frozenset()},
            catalog={},
            deck_blobs={7: blob},
        )

    def test_raw_fzf_preserves_slot_order_blanks_and_actual_cap(self):
        blob = encode_deck((0, 623, 0), (0,), 200)
        authority = self.authority(blob)
        self.assertEqual(
            copied_class_source_deck(authority, 7),
            dict(active=[0, 623, 0], passive=[0], level_cap=200),
        )
        self.assertEqual(authority.decks[7], frozenset((623, 0)))
        self.assertEqual(authority.deck_blobs[7], blob)

    def test_flattened_criteria_set_cannot_replace_fzf_bytes(self):
        authority = self.authority(encode_deck((623,), (), 200))
        authority.deck_blobs = None
        with self.assertRaisesRegex(ValueError, "raw fzf deck"):
            copied_class_source_deck(authority, 7)

    def test_changed_slot_membership_or_cap_requires_source_revalidation(self):
        authority = self.authority(encode_deck((0, 623), (), 200))
        authority.deck_caps[7] = 1
        with self.assertRaisesRegex(ValueError, "deck authority"):
            copied_class_source_deck(authority, 7)
        authority.deck_caps[7] = 200
        authority.decks[7] = frozenset((0,))
        with self.assertRaisesRegex(ValueError, "deck authority"):
            copied_class_source_deck(authority, 7)

    def test_copy_selection_consumes_actual_authority_schema_and_raw_deck(self):
        ordinary = self.authority(encode_deck((0, 623), (), 200))
        metadata = NativeActorAuthority(
            {},
            True,
            frozenset((0, 623)),
            frozenset(),
            False,
            7,
            0,
            {},
            True,
            native_real_level=200,
            native_actor_type=0,
            native_is_ehp=True,
        )

        class Authority:
            def __call__(self, fight, actor):
                return metadata

        authority = Authority()
        authority.ordinary = ordinary
        actor = SimpleNamespace(id=7)
        fight = SimpleNamespace(actors={7: actor})
        definitions = {
            str(reference): dict(maximum_level=200)
            for _, reference, _ in owned_spell_records(ordinary.characters[7])
        }
        identities = count(10000)
        copied, proof = copied_class_book(
            fight,
            actor,
            authority,
            allocate_uid=lambda: next(identities),
            definitions=definitions,
        )
        self.assertEqual([(row.reference, row.level) for row in copied], [(623, 200)])
        self.assertEqual(proof["available_references"], [0, 623])
        self.assertEqual(proof["selector_cap"], 200)
        self.assertFalse(hasattr(metadata, "verified"))
