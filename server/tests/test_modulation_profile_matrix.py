"""Cross-breed modulation deck bounds without changing combat semantics."""
import copy
import unittest

from wakfu_server import builds, spells
from wakfu_server.characters import dungeon_modulation as modulation
from wakfu_server.wire import proto_field


class ModulationProfileMatrixTests(unittest.TestCase):
    def test_every_installed_breed_and_band_preserves_owned_sheet_and_legal_slots(self):
        breeds = sorted(
            {row["breed"] for row in spells.SPELLS.values() if row["breed"] > 0}
        )
        self.assertTrue(breeds)
        for breed in breeds:
            for owned_sheet_level in (20, 200):
                source = dict(
                    id=31,
                    breed=breed,
                    level=200,
                    active_build_index=1,
                    effective_level=owned_sheet_level,
                )
                source["builds"] = {
                    1: dict(
                        sheet=b"".join(
                            proto_field(tag, value)
                            for tag, value in (
                                (8, 1),
                                (18, b"Owned"),
                                (24, owned_sheet_level),
                                (56, 0),
                                (64, 0),
                            )
                        ).hex(),
                        equipment="",
                        aptitudes="",
                        deck=spells.default_deck(source).hex(),
                    )
                }
                before = copy.deepcopy(source)
                for cap in modulation.NATIVE_BANDS:
                    with self.subTest(breed=breed, sheet=owned_sheet_level, cap=cap):
                        projected = modulation.project(
                            source,
                            dict(
                                competitive=True,
                                maximum_level=cap,
                                instance_id=91,
                                selection_revision=3,
                            ),
                            modulation.DEFAULT_POLICY,
                        )
                        self.assertEqual(source, before)
                        level = min(200, cap)
                        self.assertEqual(projected["level"], 200)
                        self.assertEqual(projected["effective_level"], level)
                        self.assertEqual(
                            builds.effective_sheet_level(projected, 1),
                            owned_sheet_level,
                        )
                        index = projected["active_build_index"]
                        decoded = spells.validate_deck(
                            bytes.fromhex(projected["builds"][index]["deck"]),
                            breed,
                            level,
                        )
                        original = spells.validate_deck(
                            bytes.fromhex(source["builds"][1]["deck"]),
                            breed,
                            owned_sheet_level,
                        )
                        self.assertEqual(decoded["level_cap"], level)
                        for previous, current in zip(
                            original["active"], decoded["active"]
                        ):
                            self.assertIn(current, (0, previous))
