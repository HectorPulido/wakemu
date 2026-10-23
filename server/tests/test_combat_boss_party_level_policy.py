"""Versioned range reconstruction and immutable actual-participant selection."""
from fractions import Fraction
from types import SimpleNamespace
import unittest

from wakfu_server.combat_boss_party_level_policy import (
    RUSHU_PARTY_LEVEL,
    freeze_participant_levels,
)


class BossPartyLevelPolicyTests(unittest.TestCase):
    def test_frozen_owned_maximum_and_explicit_intermediate_range_policy(self):
        profile = dict(player_ids=[8, 7], player_team=0)
        actors = {
            7: SimpleNamespace(id=7, controlled=True, team=0, effective_level=230),
            8: SimpleNamespace(id=8, controlled=True, team=0, effective_level=215),
            9: SimpleNamespace(id=9, controlled=False, team=0, effective_level=245),
        }
        frozen = freeze_participant_levels(profile, actors)
        self.assertEqual(frozen.participants, ((7, 230), (8, 215)))
        self.assertEqual(RUSHU_PARTY_LEVEL.multiplier(frozen), Fraction(1))
        for level in range(231, 245):
            actors[8].effective_level = level
            self.assertEqual(
                RUSHU_PARTY_LEVEL.multiplier(
                    freeze_participant_levels(profile, actors)
                ),
                Fraction(6, 5),
            )
        actors[8].effective_level = 245
        self.assertEqual(
            RUSHU_PARTY_LEVEL.multiplier(freeze_participant_levels(profile, actors)),
            Fraction(6, 5),
        )
        # Later levels/population cannot change the previously frozen snapshot.
        self.assertEqual(RUSHU_PARTY_LEVEL.multiplier(frozen), Fraction(1))

    def test_invalid_or_foreign_participants_do_not_select_a_multiplier(self):
        profile = dict(player_ids=[7], player_team=0)
        actor = SimpleNamespace(id=7, controlled=True, team=0, effective_level=245)
        for changes in (
            dict(controlled=False),
            dict(team=1),
            dict(effective_level=True),
            dict(effective_level=246),
        ):
            with self.subTest(changes=changes):
                altered = SimpleNamespace(**(vars(actor) | changes))
                with self.assertRaisesRegex(
                    ValueError, "actual effective-level authority"
                ):
                    freeze_participant_levels(profile, {7: altered})
        for ids in ([], [7, 7]):
            with self.assertRaisesRegex(ValueError, "unique owned participants"):
                freeze_participant_levels(dict(profile, player_ids=ids), {7: actor})
