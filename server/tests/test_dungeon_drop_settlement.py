"""Transactional dungeon selection, real terminal combat and native drops."""
from test_dungeon_difficulty import DungeonDifficultyPostgresTests


class DungeonDropSettlementTests(DungeonDifficultyPostgresTests):
    def test_selected_dungeon_terminal_combat_persists_native_drops_and_replays(self):
        from wakfu_server.combat.combat_state import Actor, Fight
        from wakfu_server.combat.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_rewards import award
        from wakfu_server.maps import dungeon_progression
        from wakfu_server.storage import (
            combat_reward_context,
            reward_policy,
            combat_drops,
        )
        from wakfu_server.monsters import owned_instance

        self.select(stasis_level=5, competitive=True)
        member = self.members[0]
        character = member["character"]
        cid = character["id"]
        fight_id = self.make_fight(member)
        monster = owned_instance(1, 8, -200, map_id=527, x=1, y=0, z=0, team=1)
        player = Actor(
            cid,
            0,
            (0, 0, 0),
            character["hp"],
            6,
            3,
            100,
            character["level"],
            owner_id=member["account"],
            controlled=True,
            max_hp=character["max_hp"],
        )
        npc = Actor(
            -200,
            1,
            (1, 0, 0),
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            8,
        )
        fight = Fight(
            fight_id,
            [player, npc],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        initialize_fight_snapshots(
            fight,
            characters={cid: character},
            monsters={-200: monster},
            wp_resources={cid: (0, 0), -200: (0, 0)},
            running_effects={cid: (), -200: ()},
            initial_effect_uid=100,
        )
        with self.store.connection() as db:
            dungeon_progression.bind_encounter(
                db, self.instance_id, self.party_id, cid, fight_id, player_team=0
            )
        fight.ready(member["account"])
        with fight.effect_resolution():
            fight.apply_effect_damage(cid, -200, npc.hp)
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            origin = combat_reward_context.authoritative_encounter_kind(
                db, fight_id, None
            )
            xp_context, drop_context = combat_reward_context.settlement_contexts(
                db, fight, character, [monster], encounter_kind=origin
            )
            self.assertEqual(drop_context["stasis_level"], 5)
            self.assertEqual(drop_context["dungeon_drop_rate_bp"], 40000)
            decision = reward_policy.resolve(
                self.store,
                db,
                account_id=member["account"],
                generation=member["generation"],
                character_id=cid,
                fight_id=fight_id,
                context=xp_context,
                kamas_roll_index=0,
            )
            award(
                self.store,
                member["account"],
                member["generation"],
                cid,
                fight,
                decision.policy,
                db=db,
            )
            batch = combat_drops.resolve(
                self.store,
                db,
                account_id=member["account"],
                generation=member["generation"],
                character_id=cid,
                fight_id=fight_id,
                monsters=[{"actor_id": -200, "reference": 1}],
                prospecting_bonus=combat_drops.native_prospection_bonus(player),
                can_loot=True,
                fight_context=drop_context,
                rng=lambda upper: 0,
            )
            self.assertTrue(batch.decisions)
            dungeon_progression.settle_encounter(db, fight)
        with self.store.connection() as db:
            replay = combat_drops.resolve(
                self.store,
                db,
                account_id=member["account"],
                generation=member["generation"],
                character_id=cid,
                fight_id=fight_id,
                monsters=[],
                prospecting_bonus=0,
                can_loot=False,
                fight_context={},
                rng=lambda upper: (_ for _ in ()).throw(AssertionError("replay RNG")),
            )
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.decisions, batch.decisions)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_attempt_receipts WHERE fight_id=%s AND character_id=%s",
                    (fight_id, cid),
                ).fetchone()["n"],
                len(batch.decisions),
            )
