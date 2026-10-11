import unittest

from wakfu_server.items.sublimation_eligibility import (
    CLIENT_JAR_SHA256,
    pattern,
    special_target,
)


class Rows:
    def __init__(self, row):
        self.row = row

    def execute(self, query, parameters):
        return self

    def fetchone(self):
        return self.row


class SublimationEligibilityTests(unittest.TestCase):
    def test_native_slots_are_independent_and_special_patterns_are_colorless(self):
        for kind, colors, tag in (
            ("BASIC", [1, 2, 3], 24),
            ("EPIC", [], 32),
            ("RELIC", [], 32),
        ):
            with self.subTest(kind=kind):
                result = pattern(
                    Rows(
                        dict(
                            pattern_type=kind,
                            slot_colors=colors,
                            client_jar_sha256=CLIENT_JAR_SHA256,
                        )
                    ),
                    1,
                )
                self.assertEqual(
                    (result["kind"], result["colors"], result["tag"]),
                    (kind, tuple(colors), tag),
                )

    def test_rejects_malformed_or_unaccredited_patterns(self):
        valid = dict(
            pattern_type="BASIC",
            slot_colors=[1, 2, 3],
            client_jar_sha256=CLIENT_JAR_SHA256,
        )
        for change in (
            dict(slot_colors=[]),
            dict(slot_colors=[True]),
            dict(slot_colors=[5]),
            dict(slot_colors=[1] * 5),
            dict(pattern_type="EPIC"),
            dict(pattern_type="UNKNOWN"),
            dict(client_jar_sha256="0" * 64),
        ):
            with self.subTest(change=change), self.assertRaisesRegex(
                ValueError, "Malformed"
            ):
                pattern(Rows(dict(valid, **change)), 1)

    def test_exact_native_epic_and_relic_rarities(self):
        for kind, rarity in (("EPIC", 7), ("RELIC", 5)):
            valid = dict(
                pattern_type=kind,
                rarity_code=rarity,
                item_level=50,
                client_jar_sha256=CLIENT_JAR_SHA256,
            )
            self.assertEqual(special_target(Rows(valid), 1, kind=kind), valid)
            for change in (
                dict(rarity_code=5 if rarity == 7 else 7),
                dict(rarity_code=True),
                dict(item_level=-1),
                dict(item_level=True),
                dict(pattern_type="BASIC"),
                dict(client_jar_sha256="0" * 64),
            ):
                with self.subTest(kind=kind, change=change), self.assertRaisesRegex(
                    ValueError, "Malformed"
                ):
                    special_target(Rows(dict(valid, **change)), 1, kind=kind)
            with self.assertRaisesRegex(ValueError, "Target rarity"):
                special_target(
                    Rows(valid), 1, kind="RELIC" if kind == "EPIC" else "EPIC"
                )

    def test_missing_or_disabled_authority_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "enabled native pattern"):
            pattern(Rows(None), 1)
        with self.assertRaisesRegex(ValueError, "Target rarity"):
            special_target(Rows(None), 1, kind="EPIC")
