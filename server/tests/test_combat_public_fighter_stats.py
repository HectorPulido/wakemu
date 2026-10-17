"""Public external membership excludes XP with exact native group preservation."""
import unittest
from test_combat_actor import CombatActorTests
from wakfu_server.combat_actor import actor_stats
from wakfu_server.combat_public_fighter_stats import public_player_fighter_stats


class PublicFighterStatsTests(unittest.TestCase):
    def test_public_projection_preserves_owned_groups_and_identity_without_xp(self):
        stats = actor_stats(CombatActorTests().character(), 123, team=1, wp=6)
        public = public_player_fighter_stats(stats, actor_id=7, fight_id=123)
        self.assertEqual(public, b"\x02" + stats[9:])
        self.assertEqual(len(public), len(stats) - 8)
        self.assertEqual(public[-20:], stats[-20:])

    def test_foreign_identity_wrong_kind_and_incomplete_sources_fail_closed(self):
        stats = actor_stats(CombatActorTests().character(), 123, wp=6)
        invalid = [stats[:i] for i in range(len(stats))]
        invalid += [b"\x02" + stats[9:], stats + b"trailer", bytearray(stats)]
        for source in invalid:
            with self.subTest(length=len(source)):
                with self.assertRaises(ValueError):
                    public_player_fighter_stats(source, actor_id=7, fight_id=123)
        for actor_id, fight_id in [(8, 123), (7, 124), (True, 123), (7, True)]:
            with self.assertRaises(ValueError):
                public_player_fighter_stats(stats, actor_id=actor_id, fight_id=fight_id)
