"""Publish live PA callbacks onto the retained Fight reference atomically."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_area_boundary import adopt_fight
from wakfu_server.combat_characteristic_link import ObservableCharacteristicStats


class CharacteristicAdoptionTests(unittest.TestCase):
    def fight(self):
        fight = SimpleNamespace(
            actors={},
            native_characteristic_links={
                7: dict(source_id=1, destination_id=2, source_stat=10)
            },
        )
        for identity in (1, 2):
            fight.actors[identity] = SimpleNamespace(
                effect_stats=ObservableCharacteristicStats({10: 4}, fight, identity)
            )
        return fight

    def test_adoption_preserves_actor_identity_and_live_callback_destination(self):
        fight = self.fight()
        actor = fight.actors[1]
        candidate = deepcopy(fight)
        adopt_fight(fight, candidate)
        self.assertIs(fight.actors[1], actor)
        self.assertIs(actor.effect_stats._fight, fight)
        with patch("wakfu_server.combat_characteristic_link._refresh") as refresh:
            actor.effect_stats[10] = 9
        refresh.assert_called_once()
        self.assertIs(refresh.call_args.args[0], fight)
        self.assertIs(refresh.call_args.args[1], fight.native_characteristic_links[7])

    def test_invalid_listener_rejects_before_publishing_any_actor(self):
        fight = self.fight()
        before_actor, before_stats = fight.actors[1], fight.actors[1].effect_stats
        candidate = deepcopy(fight)
        candidate.actors[2].effect_stats._identity = 1
        with self.assertRaisesRegex(ValueError, "Stale native PA"):
            adopt_fight(fight, candidate)
        self.assertIs(fight.actors[1], before_actor)
        self.assertIs(fight.actors[1].effect_stats, before_stats)
        self.assertIs(before_stats._fight, fight)

    def test_last_removed_link_still_rebinds_observable_stats_for_future_links(self):
        fight = self.fight()
        fight.native_characteristic_links.clear()
        candidate = deepcopy(fight)
        adopt_fight(fight, candidate)
        self.assertIs(fight.actors[1].effect_stats._fight, fight)
        self.assertIs(fight.actors[2].effect_stats._fight, fight)
