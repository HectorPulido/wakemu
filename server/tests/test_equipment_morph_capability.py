"""Original morph book dependencies and fail-closed live capability guards."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.combat_definitions import effect_profile
from wakfu_server.combat_equipment_morph_parser import parse
from wakfu_server.combat_equipment_morph_capability import (
    UnknownMorphDependency,
    book_domain,
    dependency_witnesses,
    preflight,
    verify_invocation,
)

DATA = json.loads(
    (
        Path(__file__).parent
        / "fixtures/native_equipment_morph_characteristic_groups.json"
    ).read_text()
)


class EquipmentMorphCapabilityTests(unittest.TestCase):
    def test_all_actual_published_equipment_profiles_have_complete_zero_root_witnesses(
        self,
    ):
        from wakfu_server.combat_morph_dependencies import effect_catalog, zero_catalog
        from wakfu_server.combat_morph_spellbook import (
            native_morph_profiles,
            build_morph_book,
        )

        effects, zeros, profiles = (
            effect_catalog(),
            zero_catalog(),
            native_morph_profiles(),
        )
        for reference in DATA["sources"]["30530"]:
            effect = DATA["effects"][str(reference)]
            parsed = parse(effect, effect_profile(effect, 1))
            with self.subTest(profile=parsed["profile_id"]):
                book = build_morph_book(profiles[str(parsed["profile_id"])], 0)
                domain = book_domain(parsed)
                self.assertEqual([row["reference"] for row in domain], list(book))
                self.assertTrue(all(row["level_domain"] == (0, 0) for row in domain))
                expected = tuple(
                    dict.fromkeys(
                        (root, 0)
                        for spell in book
                        for root in zeros["spells"][str(spell)][2]
                    )
                )
                self.assertEqual(dependency_witnesses(parsed), expected)
                self.assertTrue(expected)
                self.assertTrue(
                    all(str(root) in effects["effects"] for root, _ in expected)
                )

    def test_own_level_domain_preserves_all_future_caps_without_zero_source_substitution(
        self,
    ):
        effect = dict(
            DATA["effects"]["340246"], parameter_count=2, parameters=[5371, 0, 1, 0]
        )
        parsed = parse(effect, effect_profile(effect, 1))
        domain = book_domain(parsed)
        self.assertTrue(domain)
        self.assertTrue(
            all(row["level_domain"] == (-32768, row["maximum_level"]) for row in domain)
        )
        with self.assertRaisesRegex(
            UnknownMorphDependency, "positive-level casting domain"
        ):
            dependency_witnesses(parsed)

    def test_uninitialized_fake_factory_and_unregistered_handler_never_approve(self):
        effect = DATA["effects"]["340246"]
        parsed = parse(effect, effect_profile(effect, 1))
        self.assertFalse(preflight(SimpleNamespace(), {}, parsed))
        self.assertFalse(
            verify_invocation(
                SimpleNamespace(handlers={}),
                effect,
                SimpleNamespace(target_id=1),
                None,
                parsed,
            )
        )
