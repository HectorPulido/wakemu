import copy
import unittest
from unittest.mock import patch
from wakfu_server.combat_initialization_policy import (
    partition_unsupported_equipment,
    warning_text,
)
from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.equipment_stats import effective_character, bonuses
from wakfu_server.wire import proto_field
from wakfu_server.health import maximum


class DevelopmentInitializationTests(unittest.TestCase):
    def fixture(self):
        character = dict(
            id=1,
            breed=8,
            level=200,
            hp=100,
            max_hp=maximum(8, 200),
            inventory_items=[
                dict(uid=900, character_id=1, reference=31361, quantity=1)
            ],
            builds={
                0: dict(
                    equipment=proto_field(
                        10, proto_field(8, 900) + proto_field(16, 17)
                    ).hex()
                )
            },
        )
        character = effective_character(character)
        actor = Actor(
            1,
            0,
            (0, 0, 0),
            100,
            7,
            3,
            0,
            200,
            owner_id=1,
            controlled=True,
            max_hp=character["max_hp"],
        )
        other = Actor(
            2,
            1,
            (1, 0, 0),
            100,
            6,
            3,
            0,
            200,
            owner_id=2,
            controlled=True,
            max_hp=maximum(8, 200),
        )
        fight = Fight(
            5, [actor, other], {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        return character, fight

    def initialize(self, character, fight, warnings, enabled):
        return initialize_fight_snapshots(
            fight,
            characters={
                1: character,
                2: dict(character, id=2, builds={}, inventory_items=[]),
            },
            monsters={},
            wp_resources={1: (8, 8), 2: (6, 6)},
            running_effects={1: (), 2: ()},
            initial_effect_uid=1,
            dev_skip_unsupported=enabled,
            initialization_warnings=warnings,
        )

    def test_real_marfil_strict_rejects_without_partial_snapshot(self):
        character, fight = self.fixture()
        before = copy.deepcopy(fight.__dict__)
        warnings = []
        with self.assertRaisesRegex(ValueError, "379699"):
            self.initialize(character, fight, warnings, False)
        self.assertEqual(fight.actors[1].effect_stats, before["actors"][1].effect_stats)
        self.assertEqual(fight.native_effect_uid_next, before["native_effect_uid_next"])
        self.assertEqual(warnings, [])

    def test_real_marfil_development_preserves_supported_bonuses(self):
        character, fight = self.fixture()
        self.assertEqual(bonuses(character)["stats"], {2: 1, 4: 2})
        warnings = []
        self.initialize(character, fight, warnings, True)
        self.assertEqual(
            (fight.actors[1].effect_stats[2], fight.actors[1].effect_stats[4]), (7, 8)
        )
        self.assertEqual(fight.native_effect_uid_next, 1)
        self.assertEqual(tuple(fight.actors[1].state_ledger.entries), ())
        self.assertEqual(
            [(w["reference"], w["effect_id"], w["generic"]) for w in warnings],
            [(31361, 379699, 304)],
        )
        self.assertIn("379699", warning_text(warnings[0]))
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual(fight.state_wire_payloads, {})

    def test_unrelated_validation_still_rejects_atomically(self):
        character, fight = self.fixture()
        warnings = []
        before = copy.deepcopy(fight.__dict__)
        with patch(
            "wakfu_server.combat_actor_snapshot.build_player_snapshot",
            side_effect=ValueError("invalid owned snapshot"),
        ):
            with self.assertRaisesRegex(ValueError, "invalid owned snapshot"):
                self.initialize(character, fight, warnings, True)
        self.assertEqual(fight.actors[1].effect_stats, before["actors"][1].effect_stats)
        self.assertEqual(fight.native_effect_uid_next, before["native_effect_uid_next"])
        self.assertEqual(warnings, [])

    def test_unknown_template_and_aptitude_failures_are_never_skipped(self):
        effects = [
            dict(reason="missing-effect-template", uid=900, reference=31361),
            dict(reason="unsupported-native-effect", effect_id=1, generic=304),
        ]
        self.assertEqual(
            partition_unsupported_equipment(effects, enabled=True), (effects, [])
        )
        with self.assertRaises(ValueError):
            partition_unsupported_equipment([], enabled=1)

    def test_visible_rejection_is_bounded_and_escapes_client_markup(self):
        from wakfu_server.combat_initialization_policy import safe_rejection_text

        text = safe_rejection_text(ValueError("<b>bad</b>\n" + "x" * 600))
        self.assertNotIn("<b>", text)
        self.assertNotIn("\n", text)
        self.assertIn("&lt;b&gt;", text)
        self.assertLess(len(text), 560)
