import unittest
from types import SimpleNamespace

from wakfu_server.combat_state import Actor
from wakfu_server.combat_actor_snapshot import build_player_snapshot
from wakfu_server.combat_reward_context import build_context, build_drop_context
from wakfu_server.equipment_stats import effective_character
from wakfu_server.health import maximum
from wakfu_server.monsters import owned_instance
from wakfu_server.storage.combat_drops import native_prospection_bonus
from wakfu_server.wire import proto_field


class CombatRewardContextTests(unittest.TestCase):
    def setup_fight(self, *, winner=0, phase="finished", wisdom=17):
        account_id, character_id = 41, 501
        player = Actor(character_id, 0, (0, 0, 0), 80, 6, 3, 10, 1, account_id, True)
        player.effect_stats = {36: wisdom}
        monster = owned_instance(5525, 1, -200, map_id=1134, x=1, y=0, z=0, team=1)
        npc = Actor(
            monster["id"],
            1,
            (1, 0, 0),
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            monster["level"],
        )
        return (
            SimpleNamespace(
                phase=phase, winner=winner, actors={player.id: player, npc.id: npc}
            ),
            dict(id=character_id, account_id=account_id, level=1),
            [monster],
            player,
            npc,
        )

    def test_context_accepts_real_spawn_and_native_player_snapshot(self):
        # Mirrors the production boundary: TEST_MONSTERS contains the owned
        # instance returned by owned_instance(), and the player receives the
        # same native snapshot installed by initialize_fight_snapshots().
        character = effective_character(
            dict(
                id=501,
                account_id=41,
                breed=8,
                level=6,
                hp=maximum(8, 6),
                max_hp=maximum(8, 6),
                builds={},
                inventory_items=[],
                territory_stat_bonuses={36: 30, 33: 30},
            )
        )
        player = Actor(
            501,
            0,
            (0, 0, 0),
            character["hp"],
            6,
            3,
            0,
            6,
            owner_id=41,
            controlled=True,
            max_hp=character["max_hp"],
        )
        snapshot = build_player_snapshot(
            character, player, wp_current=6, wp_maximum=6, running_effects=()
        )
        snapshot.install(player)

        # The combat test encounter is built from this exact trusted spawn
        # descriptor shape: id/ref/level plus native owned-instance fields.
        spawned = owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)
        monster = Actor(
            spawned["id"],
            1,
            (spawned["x"], spawned["y"], spawned["z"]),
            spawned["hp"],
            spawned["ap"],
            spawned["mp"],
            spawned["initiative"],
            spawned["level"],
        )
        fight = SimpleNamespace(
            id=99,
            phase="finished",
            winner=0,
            actors={player.id: player, monster.id: monster},
        )

        self.assertEqual((snapshot.stats[36], snapshot.stats[33]), (30, 30))
        context = build_context(fight, character, [spawned])
        self.assertEqual(context["winners"][0]["wisdom"], snapshot.stats[36])
        self.assertEqual(native_prospection_bonus(player), snapshot.stats[33])
        self.assertEqual(context["winners"][0]["level"], 6)
        self.assertEqual(context["losers"], [{"level": 1, "monster_reference": 5525}])

    def test_context_uses_finished_owned_roster_native_wisdom_and_trusted_spawn(self):
        fight, character, monsters, player, _ = self.setup_fight(wisdom=28)
        result = build_context(
            fight, character, monsters, challenge_percent=100, star_percent=50
        )
        self.assertEqual(
            result,
            {
                "winner_team": 0,
                "winners": [
                    {
                        "level": 1,
                        "player": True,
                        "eligible": True,
                        "character_id": player.id,
                        "wisdom": 28,
                    }
                ],
                "losers": [{"level": 1, "monster_reference": 5525}],
                "challenge_percent": 100,
                "star_percent": 50,
            },
        )

    def test_drop_context_proves_downscaling_from_winning_actor_and_owned_sheet(self):
        fight, character, monsters, player, _ = self.setup_fight()
        character.update(
            level=20,
            active_build_index=1,
            builds={1: {"sheet": (proto_field(8, 1) + proto_field(24, 10)).hex()}},
        )
        player.effective_level = 10
        self.assertEqual(
            build_drop_context(fight, character, monsters), {"downscaled": True}
        )

    def test_drop_context_reports_not_downscaled_and_requires_owned_finished_win(self):
        fight, character, monsters, _, _ = self.setup_fight()
        self.assertEqual(
            build_drop_context(fight, character, monsters), {"downscaled": False}
        )
        fight.phase = "active"
        with self.assertRaisesRegex(ValueError, "completed fight"):
            build_drop_context(fight, character, monsters)
        fight.phase, fight.winner = "finished", 1
        with self.assertRaisesRegex(ValueError, "owned winning player"):
            build_drop_context(fight, character, monsters)

    def test_drop_context_only_sets_world_negative_conditions_from_explicit_origin(
        self,
    ):
        fight, character, monsters, _, _ = self.setup_fight()
        # Map 1134 and combat terrain IDs are deliberately not used as signals.
        self.assertEqual(
            build_drop_context(fight, character, monsters),
            {"downscaled": False},
        )
        self.assertEqual(
            build_drop_context(
                fight, character, monsters, encounter_kind="ordinary_world"
            ),
            {
                "downscaled": False,
                "in_dungeon": False,
                "in_infinite_waves": False,
            },
        )
        for unsupported in ("dungeon", "infinite_waves", "unknown"):
            with self.subTest(encounter_kind=unsupported):
                with self.assertRaisesRegex(ValueError, "Unsupported authoritative"):
                    build_drop_context(
                        fight, character, monsters, encounter_kind=unsupported
                    )

    def test_registered_summons_count_as_actors_but_never_as_players_or_monsters(self):
        fight, character, monsters, _, _ = self.setup_fight()
        winning_summon = Actor(-201, 0, (2, 0, 0), 10, 0, 0, 0, 5, 41, True)
        winning_summon.native_summon_source = {
            "ref": 123,
            "level": 5,
            "caster_id": character["id"],
        }
        losing_summon = Actor(-202, 1, (3, 0, 0), 10, 0, 0, 0, 4)
        losing_summon.native_summon_source = {
            "ref": 124,
            "level": 4,
            "caster_id": character["id"],
        }
        fight.actors.update({-201: winning_summon, -202: losing_summon})

        result = build_context(fight, character, monsters)
        winners = {row["character_id"]: row for row in result["winners"]}
        summon = winners[None]
        self.assertEqual(
            summon,
            {
                "level": 5,
                "player": False,
                "eligible": False,
                "character_id": None,
                "wisdom": 0,
            },
        )
        self.assertIn({"level": 4, "monster_reference": None}, result["losers"])
        self.assertIn({"level": 1, "monster_reference": 5525}, result["losers"])

    def test_native_negative_wisdom_is_preserved_inside_catalog_bounds(self):
        fight, character, monsters, _, _ = self.setup_fight(wisdom=-500)
        self.assertEqual(
            build_context(fight, character, monsters)["winners"][0]["wisdom"],
            -500,
        )
        fight.actors[character["id"]].effect_stats[36] = -501
        with self.assertRaisesRegex(ValueError, "Wisdom"):
            build_context(fight, character, monsters)

    def test_context_fails_closed_for_abort_defeat_missing_wisdom_and_unknown_npc(self):
        fight, character, monsters, player, _ = self.setup_fight()
        fight.phase, fight.winner = "finished", None
        with self.assertRaisesRegex(ValueError, "winning team"):
            build_context(fight, character, monsters)
        fight.phase, fight.winner = "placement", 0
        with self.assertRaisesRegex(ValueError, "completed fight"):
            build_context(fight, character, monsters)
        fight.phase, fight.winner = "finished", 1
        with self.assertRaisesRegex(ValueError, "winning player"):
            build_context(fight, character, monsters)
        fight.winner = 0
        player.effect_stats = None
        with self.assertRaisesRegex(ValueError, "Wisdom snapshot"):
            build_context(fight, character, monsters)
        player.effect_stats = {36: 17}
        unknown = Actor(-999, 1, (2, 0, 0), 10, 0, 0, 0, 1)
        fight.actors[unknown.id] = unknown
        with self.assertRaisesRegex(ValueError, "Unregistered NPC"):
            build_context(fight, character, monsters)

    def test_context_rejects_trusted_monster_mismatch_duplicate_and_foreign_player(
        self,
    ):
        fight, character, monsters, player, _ = self.setup_fight()
        fight.actors[-200].effective_level = 2
        with self.assertRaisesRegex(ValueError, "differs from trusted spawn"):
            build_context(fight, character, monsters)
        fight.actors[-200].effective_level = 1
        with self.assertRaisesRegex(ValueError, "Duplicate trusted spawned"):
            build_context(fight, character, [monsters[0], monsters[0]])
        player.owner_id += 1
        with self.assertRaisesRegex(ValueError, "owned winning player"):
            build_context(fight, character, monsters)


if __name__ == "__main__":
    unittest.main()
