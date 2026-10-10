"""Zobal owned spells through native map, NPC, and event runtime paths."""
import os
import random
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ZobalRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_combat_aptitude_healing_runtime import (
            AptitudeHealingRuntimeTests,
        )

        AptitudeHealingRuntimeTests.setUpClass()
        cls.fixture_factory = AptitudeHealingRuntimeTests

    def fixture(self, *, passive_spells=()):
        harness = self.fixture_factory()
        fight, characters, monster, decks = harness.fixture(
            active_spells=(7086,),
            passive_spells=passive_spells,
            caster_breed=14,
            injury=0,
            enemy_position=(-6, -7, -1),
            third_player_position=(-8, -6, -1),
            compact_arena=False,
        )
        # The shared fixture's Wonejo actor is authoritative; this extra field
        # is required only by the NPC spell-ownership lookup helper.
        monster["level"] = 1
        return fight, characters, monster, decks

    def kill_ally_with_native_wonejo_attack(
        self, fight, characters, monster, decks, *, action_id=100
    ):
        from tests.test_combat_resurrection_runtime import ResurrectionRuntimeTests

        harness = ResurrectionRuntimeTests()
        rng = random.Random(0)
        for offset in range(200):
            if fight.actors[8].hp == 0:
                break
            fight, _ = harness.damage(
                fight,
                characters,
                monster,
                decks,
                rng,
                action_id + offset,
            )
        self.assertEqual(fight.actors[8].hp, 0)
        from wakfu_server.combat_global_pv_collections import global_fighter_guards

        self.assertEqual(
            global_fighter_guards(fight, 8),
            dict(baF=False, baG=True, baK=False),
        )
        death_index = next(
            index
            for index, event in enumerate(fight.events)
            if event.get("kind") == "death" and event.get("actor_id") == 8
        )
        self.assertEqual(fight.events[death_index - 1]["kind"], "damage")
        return fight, rng

    def test_danza_macabra_resurrects_a_real_registered_ally_corpse(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, characters, monster, decks = self.fixture()
        fight, rng = self.kill_ally_with_native_wonejo_attack(
            fight, characters, monster, decks
        )
        before = snapshot(fight)
        corpse = fight.actors[8]

        def los(source, target, preview):
            return authoritative_visible(
                1134,
                source,
                target,
                preview,
                blocking_footprints={
                    identity: {actor.position[:2]}
                    for identity, actor in preview.actors.items()
                    if actor.hp > 0
                },
            )

        traced_references = {314359, 314360, 314361, 307720, 307721, 307722, 307723}
        dispatch_trace = []
        original_execute = EffectDispatcher.execute

        def traced_execute(dispatcher, invocation, **kwargs):
            reference = invocation.reference
            if reference not in traced_references:
                return original_execute(dispatcher, invocation, **kwargs)
            row = {
                "reference": reference,
                "caster_id": invocation.caster_id,
                "target_id": invocation.target_id,
                "trigger_context": invocation.native_trigger_context,
            }
            try:
                result = original_execute(dispatcher, invocation, **kwargs)
            except Exception as error:
                row["status"] = "raised"
                row["error"] = f"{type(error).__name__}: {error}"
                dispatch_trace.append(row)
                raise
            row["status"] = getattr(result, "execution_status", result)
            dispatch_trace.append(row)
            return result

        with patch.object(EffectDispatcher, "execute", traced_execute):
            result = prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | 7086, *corpse.position),
                characters[7],
                {-7: monster},
                fight,
                3,
                decks[7],
                action_id=400,
                line_of_sight=los,
                critical=False,
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
            )

        self.assertEqual(snapshot(fight), before)
        self.assertEqual(result.plan["spell_id"], 7086)
        revived = result.fight.actors[8]
        marker_records = {
            uid: row
            for uid, row in result.fight.native_owned_group_effects.items()
            if row.get("invocation", {}).get("reference") == 314358
        }
        diagnostic = (
            f"outcomes={result.outcomes!r}; dispatcher_trace={dispatch_trace!r}; "
            f"marker_records={marker_records!r}; actor_effect_stats={revived.effect_stats!r}"
        )
        self.assertGreater(revived.hp, 0, diagnostic)
        self.assertEqual(
            global_fighter_guards(result.fight, 8),
            dict(baF=True, baG=False, baK=False),
        )
        self.assertIn(8, result.fight.order)
        self.assertIn(
            1144,
            {state.reference for state in revived.state_ledger.entries},
        )


if __name__ == "__main__":
    unittest.main()
