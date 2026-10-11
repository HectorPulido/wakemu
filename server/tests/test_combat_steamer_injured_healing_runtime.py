"""Specialization healing restores genuinely lost HP through native gameplay."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_special_passives_runtime as qualified
import test_combat_steamer_passive_semantics_runtime as fixtures
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerInjuredHealingRuntimeTests(unittest.TestCase):
    def test_specialization_restores_actual_enemy_damage(self):
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_healing_handler import NativeHealingHandler

        instance = qualified.SteamerSpecialPassivesRuntimeTests()
        applied = []
        heal = NativeHealingHandler.__call__

        def observe(handler, effect, values, invocation):
            actor = handler.fight.actors.get(invocation.target_id)
            before = actor.hp if actor is not None else None
            result = heal(handler, effect, values, invocation)
            if invocation.reference == 346194:
                applied.append(
                    (
                        invocation.target_id,
                        before,
                        actor.hp if actor is not None else None,
                        result,
                    )
                )
            return result

        def injured_fixture(passives=(), *, actives=()):
            data = fixtures.SteamerPassiveSemanticsRuntimeTests().fixture(
                passives, actives=actives, target_distance=1
            )
            character, monster, fight, deck, rng = data
            lifecycle = turns.AniripsaGrantSummonPipelineTests()
            for _ in range(20):
                if fight.current.id == -7:
                    break
                lifecycle.end_current_turn(fight, data)
            self.assertEqual(fight.current.id, -7)
            before = fight.actors[7].hp
            tx = prepare_npc_spell(
                fight,
                dict(
                    type="cast",
                    spellId=7962,
                    level=1,
                    targetId=7,
                    target=list(fight.actors[7].position),
                ),
                character,
                {-7: monster},
                deck,
                action_id=20,
                rng=rng,
            )
            data = instance.adopt(data, tx.fight)
            self.assertLess(data[2].actors[7].hp, before)
            data = instance.next_owned_turn(data)
            fight = data[2]
            owner, enemy = fight.actors[7].position, fight.actors[-7].position
            dx, dy = owner[0] - enemy[0], owner[1] - enemy[1]
            self.assertEqual(abs(dx) + abs(dy), 1)
            # Real two-step retreat restores the native Piratería range3.
            path = [(owner[0] + dx * i, owner[1] + dy * i, owner[2]) for i in (1, 2)]
            self.assertTrue(all(cell in fight.walkable for cell in path), path)
            fight.move(3, 7, path)
            self.assertEqual(fight.actors[7].position, path[-1])
            return data

        instance.fixture = injured_fixture
        with patch.object(NativeHealingHandler, "__call__", observe):
            instance.test_turret_earth_damage_invokes_specialization_heal_only_when_owned()
        self.assertTrue(applied, applied)
        self.assertTrue(
            any(
                before is not None and after > before for _, before, after, _ in applied
            ),
            applied,
        )
