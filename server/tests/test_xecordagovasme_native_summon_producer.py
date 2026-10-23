"""Original3389 own-start listener consumes native WP to produce4749 summons."""
from collections import Counter
import random
import unittest
from unittest.mock import patch


class XecordagovasmeNativeSummonProducerTests(unittest.TestCase):
    def test_native_constructor_wp_and_owned_start_produce_first_summons(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from tools.combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_actor_snapshot import native_npc_creation_values
        from wakfu_server.combat_npc_spell import owned_spells
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_summon_handler import NativeSummonHandler
        from wakfu_server.combat_triggered_spell_handler import (
            NativeTriggeredSpellHandler,
        )

        source = native_npc_creation_values(3539, 156)
        self.assertEqual(source[4]["current"], 3)
        fixture = TwoXelorFixture()
        fight, characters, monster, decks = fixture.fixture(
            level=200,
            caster_breed=8,
            second_player_breed=8,
            active_spells=(4780,),
            second_player_spells=(4780,),
            compact_arena=False,
            native_target_ref=3539,
            native_target_level=156,
        )
        actor = fight.actors[-7]
        self.assertFalse(actor.controlled)
        self.assertEqual(actor.effective_level, 156)
        self.assertEqual(actor.effect_stats[4], 3)
        self.assertIn(3389, {entry.reference for entry in actor.state_ledger.entries})
        from wakfu_server.monsters import native_abilities

        self.assertNotIn(4749, {row["spell_id"] for row in native_abilities(3539, 156)})
        self.assertFalse(
            any(getattr(a, "native_summon_source", None) for a in fight.actors.values())
        )
        current_registry(fight)

        triggers, summon_calls = [], []
        original_trigger = NativeTriggeredSpellHandler.__call__
        original_summon = NativeSummonHandler.__call__

        def capture_trigger(handler, effect, values, invocation):
            result = original_trigger(handler, effect, values, invocation)
            if invocation.reference == 151315:
                triggers.append(
                    dict(
                        caster=invocation.caster_id,
                        parameters=tuple(effect["parameters"]),
                        applied=result,
                    )
                )
            return result

        def capture_summon(handler, effect, values, invocation):
            result = original_summon(handler, effect, values, invocation)
            if invocation.caster_id == -7:
                summon_calls.append(
                    dict(
                        effect=invocation.reference,
                        parameters=tuple(effect["parameters"]),
                        applied=result,
                    )
                )
            return result

        common = dict(
            player_characters=characters, deck_blobs=decks, rng=random.Random(7)
        )
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], fixture.native_monsters, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], fixture.native_monsters, p, decks[7], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                fixture.native_monsters,
                decks[7],
                action_id=action_id,
                critical=False,
                **common
            )[0],
        )
        with patch.object(
            NativeTriggeredSpellHandler, "__call__", capture_trigger
        ), patch.object(NativeSummonHandler, "__call__", capture_summon):
            for _ in range(8):
                if runtime.fight.current.id == -7:
                    break
                advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, -7)
        self.assertNotIn(4749, owned_spells(runtime.fight, fixture.native_monsters))
        self.assertEqual(
            triggers, [dict(caster=-7, parameters=(4749.0, 0.0), applied=True)]
        )
        # Native349 roots request one cell for3537 and two for3538.
        self.assertEqual(
            Counter(call["effect"] for call in summon_calls),
            Counter({151352: 1, 151354: 2}),
        )
        self.assertTrue(all(call["applied"] for call in summon_calls))
        self.assertEqual(runtime.fight.actors[-7].effect_stats[4], 2)
        summons = [
            a
            for a in runtime.fight.actors.values()
            if getattr(a, "native_summon_source", {}).get("caster_id") == -7
        ]
        self.assertEqual({a.native_summon_source["ref"] for a in summons}, {3537, 3538})
        self.assertEqual(
            Counter(a.native_summon_source["ref"] for a in summons),
            Counter({3537: 1, 3538: 2}),
        )
        self.assertEqual(len(summons), 3)
        for summoned in summons:
            self.assertEqual(summoned.team, runtime.fight.actors[-7].team)
            self.assertGreater(summoned.hp, 0)
            self.assertIn(summoned.id, runtime.fight.order)
            self.assertIn(summoned.id, runtime.fight.native_summon_registrations)
            self.assertIn(summoned.position, runtime.fight.walkable)
        current_registry(runtime.fight)


if __name__ == "__main__":
    unittest.main()
