"""Original4414 turn listener reaches1155 only with actual nearby enemy PVs."""
import random
import unittest
from unittest.mock import patch


class RoyalTofuNativeEnemyCountTests(unittest.TestCase):
    def test_royal_and_arch_turn_callback_requires_two_genuine_nearby_enemies(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_triggered_spell_handler import (
            NativeTriggeredSpellHandler,
        )
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_qi_fight import current_registry

        original = NativeTriggeredSpellHandler.__call__
        for reference in (1259, 4101):
            for nearby in (1, 2):
                with self.subTest(reference=reference, nearby=nearby):
                    second = (-7, -7, -1) if nearby == 2 else (-9, -7, -1)
                    fight, characters, monster, decks = TwoXelorFixture().fixture(
                        caster_breed=8,
                        second_player_breed=8,
                        level=23,
                        active_spells=(4780,),
                        second_player_spells=(4780,),
                        second_player_position=second,
                        third_player_position=(-8, -6, -1),
                        enemy_position=(-5, -7, -1),
                        compact_arena=False,
                        native_target_ref=reference,
                        native_target_level=23,
                    )
                    enemy = fight.actors[-7]
                    self.assertEqual(enemy.team, 1)
                    self.assertFalse(enemy.controlled)
                    self.assertEqual(enemy.effective_level, 23)
                    self.assertIn(
                        4414, {state.reference for state in enemy.state_ledger.entries}
                    )
                    enemy_count = 0
                    for identity in (7, 8, 9):
                        actor = fight.actors[identity]
                        self.assertEqual(actor.team, 0)
                        self.assertTrue(actor.controlled)
                        self.assertEqual(
                            actor.owner_id, characters[identity]["account_id"]
                        )
                        self.assertEqual(actor.effective_level, 23)
                        self.assertEqual(actor.physical_radius, 0)
                        self.assertIn(actor.position, fight.walkable)
                        if (
                            sum(
                                abs(actor.position[i] - enemy.position[i])
                                for i in (0, 1)
                            )
                            <= 3
                        ):
                            enemy_count += 1
                    self.assertEqual(enemy_count, nearby)
                    self.assertEqual(
                        len({characters[i]["account_id"] for i in (7, 8, 9)}), 3
                    )
                    current_registry(fight)  # Real snapshot and QK ownership guards.
                    before_hp = {
                        identity: fight.actors[identity].hp for identity in (7, 8, 9)
                    }
                    before_positions = {
                        identity: fight.actors[identity].position
                        for identity in (7, 8, 9)
                    }
                    calls = []

                    def capture(handler, effect, values, invocation):
                        result = original(handler, effect, values, invocation)
                        if invocation.reference == 409302:
                            calls.append(
                                dict(
                                    caster=invocation.caster_id,
                                    reference=invocation.reference,
                                    parameters=tuple(effect["parameters"]),
                                    applied=result,
                                )
                            )
                        return result

                    rng = random.Random(7)
                    common = dict(
                        player_characters=characters, deck_blobs=decks, rng=rng
                    )
                    runtime = RuntimeMessages(
                        fight,
                        turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                            characters[7], {-7: monster}, p, decks[7], **common, **kw
                        ),
                        turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                            characters[7], {-7: monster}, p, decks[7], **common, **kw
                        ),
                        expiration_runtime_factory=lambda *, action_id: server_runtime(
                            characters[7],
                            {-7: monster},
                            decks[7],
                            action_id=action_id,
                            critical=False,
                            **common
                        )[0],
                    )
                    with patch.object(NativeTriggeredSpellHandler, "__call__", capture):
                        for _ in range(8):
                            if runtime.fight.current.id == -7:
                                break
                            advance_actual_turn(runtime)
                    self.assertEqual(runtime.fight.current.id, -7)
                    current_registry(runtime.fight)
                    self.assertIn(
                        4414,
                        {
                            state.reference
                            for state in runtime.fight.actors[-7].state_ledger.entries
                        },
                    )
                    if nearby == 2:
                        self.assertEqual(
                            calls,
                            [
                                dict(
                                    caster=-7,
                                    reference=409302,
                                    parameters=(1155.0, 0.0),
                                    applied=True,
                                )
                            ],
                        )
                        for identity in (7, 8):
                            self.assertLess(
                                runtime.fight.actors[identity].hp, before_hp[identity]
                            )
                        self.assertTrue(
                            any(
                                runtime.fight.actors[i].position != before_positions[i]
                                for i in (7, 8)
                            )
                        )
                        self.assertEqual(runtime.fight.actors[9].hp, before_hp[9])
                        self.assertEqual(
                            runtime.fight.actors[9].position, before_positions[9]
                        )
                    else:
                        self.assertEqual(calls, [])
                        self.assertEqual(
                            {i: runtime.fight.actors[i].hp for i in (7, 8, 9)},
                            before_hp,
                        )
                        self.assertEqual(
                            {i: runtime.fight.actors[i].position for i in (7, 8, 9)},
                            before_positions,
                        )


if __name__ == "__main__":
    unittest.main()
