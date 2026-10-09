from dataclasses import replace
from types import SimpleNamespace
import unittest
from wakfu_server.combat_character_copy_book import CopyBookAction
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_character_copy_codec import (
    CopiedAppearance,
    CopyCharacteristic,
    CopiedCharacterDescriptor,
    encode_copy_descriptor,
    encode_copy_additional,
    connected_copy_appearance,
    character_copy_payload,
)


class CharacterCopyCodecTests(unittest.TestCase):
    def descriptor(self):
        return CopiedCharacterDescriptor(
            1620,
            "Copied Héctor",
            1,
            295,
            200,
            17,
            -1,
            7,
            False,
            100,
            CopiedAppearance(7, 12345, bytes.fromhex("08011002"), ((-3, 9876),)),
            (CopyBookAction(123456789012, 6266, 200, False, True, False),),
            (CopyCharacteristic(1, 140, 330, 0, 10000),),
        )

    def test_original_native_vJ_up_bytes_with_nonempty_book_stats_categories(self):
        self.assertEqual(
            encode_copy_descriptor(self.descriptor()).hex(),
            "0654000e436f706965642048c3a963746f7200000001000000000000012700c811"
            "0100000064000030390004080110020100010000001cbe991a140000187a00c8"
            "0001010000008c0000014a00000000000027100001fd0000269400ffffffff000000000000000700",
        )

    def test_original_native_boundaries_and_explicit_empty_collections(self):
        d = replace(
            self.descriptor(),
            reference=-32768,
            name=None,
            minimum_hp=-(1 << 31),
            actor_id=-(1 << 63),
            level=-32768,
            obstacle_index=-128,
            direction=9,
            owner_id=(1 << 63) - 1,
            from_symbiot=True,
            percentage=(1 << 31) - 1,
            appearance=CopiedAppearance(7, -(1 << 31), bytes.fromhex("08011002"), ()),
            book=(),
            characteristics=(),
        )
        self.assertEqual(
            encode_copy_descriptor(d).hex(),
            "80000000800000008000000000000000800080017fffffff80000000000408011002"
            "0100000000000000000000097fffffffffffffff01",
        )

    def test_eZo_level_trailer_preserves_order_and_skips_zero_level(self):
        d = self.descriptor()
        zero = replace(d.book[0], uid=99, reference=100, level=0)
        negative = replace(d.book[0], uid=100, reference=101, level=-1)
        d = replace(d, book=(zero, d.book[0], negative))
        self.assertEqual(
            encode_copy_additional(d, include_levels=True),
            encode_copy_descriptor(d)
            + bytes.fromhex("020000187a000000c800000065ffffffff"),
        )
        self.assertEqual(
            encode_copy_additional(d, include_levels=False), encode_copy_descriptor(d)
        )

    def test_connected_source_requires_actual_character_and_model_categories(self):
        actor = SimpleNamespace(
            id=7,
            native_copy_appearance_source=dict(
                source_id=7,
                producer="owned.character.dS.don.v1",
                model=12345,
                categories=[[-3, 9876]],
            ),
        )
        authority = SimpleNamespace(characters={7: dict(id=7, appearance={"sex": 1})})
        fight = SimpleNamespace(actors={7: actor})
        source = connected_copy_appearance(authority, fight, actor)
        self.assertEqual((source.model, source.categories), (12345, ((-3, 9876),)))
        del actor.native_copy_appearance_source
        with self.assertRaisesRegex(ValueError, "provenance"):
            connected_copy_appearance(authority, fight, actor)

    def test_unknown_or_out_of_domain_descriptor_rejected(self):
        with self.assertRaises(ValueError):
            encode_copy_descriptor(replace(self.descriptor(), level=32768))
        with self.assertRaises(ValueError):
            encode_copy_descriptor(replace(self.descriptor(), characteristics=None))

    def test_ordinary_model_selection_uses_source_sex_and_cloth_byte(self):
        class Authority:
            characters = {
                7: dict(id=7, breed=15, appearance=dict(sex=1, clothIndex=255))
            }

            def __call__(self, fight, actor):
                return NativeActorAuthority(
                    {},
                    True,
                    frozenset(),
                    frozenset(),
                    False,
                    15,
                    0,
                    {},
                    True,
                    native_actor_type=0,
                    native_is_ehp=True,
                )

        actor = SimpleNamespace(id=7)
        calls = []

        def model(breed, sex, cloth):
            calls.append((breed, sex, cloth))
            return 151

        source = connected_copy_appearance(
            Authority(), SimpleNamespace(actors={7: actor}), actor, model_query=model
        )
        self.assertEqual(calls, [(15, 1, -1)])
        self.assertEqual((source.model, source.categories), (151, ()))

    def test_actual_actor_identity_is_separate_from_constructor_descriptor(self):
        from wakfu_server.combat.combat_summon import summon_additional_payload

        d = replace(self.descriptor(), actor_id=-1)
        body = character_copy_payload(
            descriptor=d,
            include_levels=False,
            uid=20,
            base_uid=20,
            effect_reference=100,
            caster_id=7,
            cell=(1, 2, 0),
            timing_payload=b"",
            actual_actor_id=295,
        )
        self.assertIn(encode_copy_descriptor(d), body)
        self.assertIn(summon_additional_payload(295), body)
        self.assertEqual(d.actor_id, -1)
