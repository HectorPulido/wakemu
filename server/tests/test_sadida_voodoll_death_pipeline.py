"""Actual NPC lethal damage, Voodoll retirement and native QI cell release."""
import os
import unittest

import test_sadida_grant_pipeline as grants
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaVoodollDeathPipelineTests(unittest.TestCase):
    fixture = grants.SadidaGrantPipelineTests.fixture
    cast = grants.SadidaGrantPipelineTests.cast

    def test_actual_npc_kill_releases_vudul_slot_without_owner_death(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_los import authoritative_visible

        data = self.fixture()
        character, monster, fight, deck, rng, _ = data
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=10, critical=False, rng=rng
        )

        def los(origin, target, current):
            return authoritative_visible(
                character["map_id"],
                origin,
                target,
                current,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in current.actors.values() if a.hp > 0
                },
            )

        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
            granted_spells(fight, 7)[926]["uid"],
            adapter=adapter,
            line_of_sight=los,
            limit=128,
            maximum_eligible=16,
        )
        enemy = fight.actors[-7]
        # Native926 targets a character; its constructor chooses a free
        # neighboring caster cell. A free destination is not a legal cast target.
        targets = [
            r["target"]
            for r in candidates["eligible"]
            if tuple(r["target"]) == tuple(enemy.position)
        ]
        self.assertTrue(targets, candidates)
        fight = self.cast(data, 926, target=targets[0]).fight
        summon = next(
            a
            for a in fight.actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        )
        set_hp_raw_current(summon, 1)
        helper = turns.AniripsaGrantSummonPipelineTests()
        for _ in range(20):
            if fight.current.id == -7:
                break
            helper.end_current_turn(fight, data[:5])
        self.assertEqual(fight.current.id, -7)
        if (
            abs(summon.position[0] - fight.current.position[0])
            + abs(summon.position[1] - fight.current.position[1])
            != 1
        ):
            # Actual certified NPC movement, not QI teleportation, brings the
            # original attacker beside the naturally placed Voodoll.
            from wakfu_server.combat_tactical_ai import NativeProvider

            provider = NativeProvider(
                character,
                {-7: monster},
                deck,
                player_characters={7: character},
                deck_blobs={7: deck},
            )
            source = snapshot(fight)
            moved = provider.preview(
                fight, dict(type="move", path=[(-7, -7, -1)]), 19, forecast=False
            )
            self.assertEqual(snapshot(fight), source)
            fight = moved.fight
            summon = fight.actors[summon.id]
        self.assertEqual(
            abs(summon.position[0] - fight.current.position[0])
            + abs(summon.position[1] - fight.current.position[1]),
            1,
        )
        source = snapshot(fight)
        tx = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=7962,
                level=1,
                targetId=summon.id,
                target=list(summon.position),
            ),
            character,
            {-7: monster},
            deck,
            action_id=20,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), source)
        self.assertTrue(any(tx.outcomes))
        dead = tx.fight.actors[summon.id]
        self.assertEqual(dead.hp, 0)
        self.assertEqual(dead.native_obstacle_id, -1)
        self.assertGreater(tx.fight.actors[7].hp, 0)
        current_registry(tx.fight)
