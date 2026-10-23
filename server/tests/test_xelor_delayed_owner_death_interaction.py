"""Paid Devotion versus actual native NPC damage and caster death, with control."""
import random
import struct
import unittest
from unittest.mock import patch

import xelor_multiowner_fixture as fixtures
from tools.combat_audit_turns import advance_actual_turn
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_npc_spell import prepare_npc_spell
from wakfu_server.combat_ordinary_death import registered_ordinary_death
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_spell,
    prepare_server_turn_start,
    prepare_server_turn_end,
    server_runtime,
)
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.health import maximum


class XelorDelayedOwnerDeathInteractionTests(unittest.TestCase):
    def test_paid_devotion_delivers_to_living_owner_but_not_dead_owner_or_foreign_player(
        self,
    ):
        outcomes = {}
        for lethal in (False, True):
            with self.subTest(lethal=lethal):
                # Constructor-owned injuries are legitimate initial character
                # data. No runtime HP, state, timer or AP value is injected.
                fight, characters, monster, decks = fixtures.TwoXelorFixture().fixture(
                    level=200,
                    injury=maximum(5, 200) - 1 if lethal else 0,
                    active_spells=(2839,),
                    native_target_ref=5525,
                    native_target_level=1,
                    compact_arena=False,
                    enemy_position=(-7, -7, -1),
                    second_player_position=(-8, -5, -1),
                    third_player_position=(-9, -7, -1),
                )
                self.assertEqual(fight.current.id, 7)
                self.assertEqual(monster["ref"], 5525)
                self.assertGreater(fight.actors[-7].hp, 0)
                rng = random.Random(0)
                common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
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
                trace = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    if invocation.reference in (340275, 340276, 340277):
                        trace.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                bool(result),
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    before = snapshot(runtime.fight)
                    devotion = prepare_server_spell(
                        struct.pack(
                            ">qqiih",
                            7,
                            (7 << 32) | 2839,
                            *runtime.fight.actors[7].position
                        ),
                        characters[7],
                        {-7: monster},
                        runtime.fight,
                        3,
                        decks[7],
                        action_id=20,
                        critical=False,
                        line_of_sight=lambda source, target, preview: authoritative_visible(
                            1134, source, target, preview
                        ),
                        **common
                    )
                    self.assertEqual(snapshot(runtime.fight), before)
                    self.assertEqual(devotion.plan["costs"]["wp"], 4)
                    runtime.fight = devotion.fight
                    self.assertTrue(
                        any(
                            entry.reference == 7545
                            for entry in runtime.fight.actors[7].state_ledger.entries
                        )
                    )
                    self.assertFalse(
                        any(ref == 340276 and ok for ref, _, _, ok in trace)
                    )
                    foreign_maxima = {
                        identity: runtime.fight.actors[identity].max_ap
                        for identity in (8, 9)
                    }
                    for _ in range(8):
                        if runtime.fight.current.id == -7:
                            break
                        advance_actual_turn(runtime)
                    self.assertEqual(runtime.fight.current.id, -7)
                    hp_before = runtime.fight.actors[7].hp
                    source = snapshot(runtime.fight)
                    strike = prepare_npc_spell(
                        runtime.fight,
                        dict(
                            type="cast",
                            spellId=7962,
                            level=1,
                            targetId=7,
                            target=list(runtime.fight.actors[7].position),
                        ),
                        characters[7],
                        {-7: monster},
                        decks[7],
                        action_id=40,
                        **common
                    )
                    self.assertEqual(snapshot(runtime.fight), source)
                    runtime.fight = strike.fight
                    owner = runtime.fight.actors[7]
                    self.assertLess(owner.hp, hp_before)
                    self.assertEqual(owner.hp == 0, lethal)
                    if lethal:
                        self.assertTrue(registered_ordinary_death(runtime.fight, owner))
                    # The actual timeline must pass over the dead owner, or
                    # start the living owner's turn and deliver its real timer.
                    for _ in range(8):
                        advance_actual_turn(runtime)
                        if runtime.fight.current.id == (8 if lethal else 7):
                            break
                    self.assertEqual(runtime.fight.current.id, 8 if lethal else 7)
                    delivered = [
                        (caster, target)
                        for ref, caster, target, ok in trace
                        if ref == 340276 and ok
                    ]
                    self.assertEqual(delivered, [] if lethal else [(7, 7)])
                    self.assertEqual(
                        runtime.fight.actors[7].max_ap,
                        6 if lethal else 9,
                    )
                    for identity in (8, 9):
                        self.assertEqual(
                            runtime.fight.actors[identity].max_ap,
                            foreign_maxima[identity],
                        )
                    self.assertEqual(runtime.fight.phase, "active")
                    outcomes[lethal] = delivered
        self.assertEqual(outcomes, {False: [(7, 7)], True: []})


if __name__ == "__main__":
    unittest.main()
