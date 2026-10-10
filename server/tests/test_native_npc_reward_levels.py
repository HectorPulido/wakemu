"""NPC reward levels extend native shorts without changing player progression."""
import unittest
from postgres_case import PostgresCase
from wakfu_server.reward_policy import _normalize_context


def context(npc_level, player_level=200):
    return dict(
        winner_team=0,
        challenge_percent=0,
        star_percent=0,
        winners=[
            dict(
                level=player_level, player=True, eligible=True, character_id=7, wisdom=0
            )
        ],
        losers=[dict(level=npc_level, monster_reference=5301)],
    )


class NativeNpcRewardLevelTests(unittest.TestCase):
    def test_real_high_level_npc_and_native_signed_short_limit_are_preserved(self):
        for level in (201, 218, 220, 224, 233, 32767):
            self.assertEqual(
                _normalize_context(context(level), 7)["losers"][0]["level"], level
            )

    def test_npc_range_and_player_cap_are_independent(self):
        for level in (0, -1, 32768, True):
            with self.subTest(level=level), self.assertRaises(ValueError):
                _normalize_context(context(level), 7)
        with self.assertRaises(ValueError):
            _normalize_context(context(233, player_level=201), 7)


class NativeNpcRewardLevelPostgresTests(PostgresCase):
    def test_nearest_lower_dev_defaults_and_reference_override_remain_explicit(self):
        with self.store.connection() as db:
            baseline = db.execute(
                "SELECT base_xp,min_kamas,max_kamas,source FROM combat_reward_level_defaults WHERE monster_level=200"
            ).fetchone()
            self.assertNotIn("explicit-dev-nearest-lower", baseline["source"])
            for level in (201, 233, 32767):
                row = db.execute(
                    "SELECT base_xp,min_kamas,max_kamas,source FROM combat_reward_level_defaults WHERE monster_level=%s",
                    (level,),
                ).fetchone()
                self.assertEqual(
                    tuple(row[k] for k in ("base_xp", "min_kamas", "max_kamas")),
                    tuple(baseline[k] for k in ("base_xp", "min_kamas", "max_kamas")),
                )
                self.assertIn("source_level:200", row["source"])
                self.assertIn("nonofficial-wakfu-balance", row["source"])
            db.execute(
                "INSERT INTO combat_reward_monster_levels(monster_reference,monster_level,base_xp,min_kamas,max_kamas,source) VALUES(5301,233,900,10,20,'explicit test override')"
            )
            self.assertEqual(
                db.execute(
                    "SELECT base_xp FROM combat_reward_monster_levels WHERE monster_reference=5301 AND monster_level=233"
                ).fetchone()["base_xp"],
                900,
            )
