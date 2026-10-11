"""Steamer damage reduction under an actual native owned enemy cast."""
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_passive_semantics_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerIncomingDamageRuntimeTests(unittest.TestCase):
    fixture = helpers.SteamerPassiveSemanticsRuntimeTests.fixture

    def test_robust_casing_reduces_actual_direct_enemy_damage(self):
        from test_aniripsa_cunejo_area_pipeline import AreaEnabledFixture
        from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        samples = {}
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                data = self.fixture((6943,) if enabled else (), target_distance=1)
                character, monster, fight, deck, rng = data
                AreaEnabledFixture().end_current_turn(fight, data)
                self.assertEqual(fight.current.id, -7)
                spells = owned_spells(fight, {-7: monster})
                trace, errors = [], []
                groups = [
                    {
                        key: row.get(key)
                        for key in (
                            "uid",
                            "target_id",
                            "invocation",
                            "native_subscription_masks",
                            "native_effect_flags",
                            "children",
                        )
                    }
                    for row in getattr(fight, "native_owned_group_effects", {}).values()
                    if row.get("invocation", {}).get("reference") == 344028
                ]
                events = []
                from wakfu_server.combat_ordinary_events import OrdinaryDamageEvents

                phase = OrdinaryDamageEvents.phase

                def observe_phase(runtime, effect, invocation, **kwargs):
                    events.append(
                        (
                            invocation.reference,
                            invocation.caster_id,
                            invocation.target_id,
                            kwargs.get("channel"),
                            effect.get("native_effect_flags"),
                            runtime.definition(effect, invocation),
                        )
                    )
                    return phase(runtime, effect, invocation, **kwargs)

                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    trace.append((invocation.reference, result))
                    return result

                selected = None
                for spell, level in sorted(spells.items()):
                    try:
                        with patch.object(
                            EffectDispatcher, "execute", observe
                        ), patch.object(OrdinaryDamageEvents, "phase", observe_phase):
                            tx = prepare_npc_spell(
                                fight,
                                dict(
                                    type="cast",
                                    spellId=spell,
                                    level=level,
                                    targetId=7,
                                    target=fight.actors[7].position,
                                ),
                                character,
                                {-7: monster},
                                deck,
                                action_id=4,
                                rng=rng,
                            )
                    except ValueError as error:
                        errors.append((spell, str(error)))
                        continue
                    damage = fight.actors[7].hp - tx.fight.actors[7].hp
                    if damage > 0:
                        selected = (spell, damage, list(trace))
                        break
                self.assertIsNotNone(selected, errors)
                samples[enabled] = selected
                if enabled:
                    self.assertIn(
                        (344029, True),
                        selected[2],
                        dict(selected=selected, groups=groups, phases=events),
                    )
                else:
                    self.assertFalse(any(ref == 344029 for ref, _ in selected[2]))
        self.assertEqual(samples[False][0], samples[True][0], samples)
        self.assertLess(samples[True][1], samples[False][1], samples)
