"""Actual native Xelor stat polarity, AP-loss recipients and turn consumers."""
import unittest
from unittest.mock import patch
import test_xelor_runtime_pipeline as helpers
import test_aniripsa_grant_summon_pipeline as turns
from wakfu_server.combat_effect_dispatch import EffectDispatcher


class XelorNumericConsumersCandidateTests(unittest.TestCase):
    def test_tick_tock_damage_and_willpower_polarity_with_actual_turns(self):
        h = helpers.XelorRuntimePipelineTests()
        observations = {}
        for passive in (None, 764, 5353):
            for phase in (0, 1):
                # Independent legal fights prevent an actual first attack KO
                # from invalidating the next parity's turn setup.
                data = h.fixture(passives=(passive,) if passive else ())
                if phase:
                    data = h.next_owned_turn(data)
                actor = data[2].actors[7]
                self.assertEqual(
                    h.states(actor).get(6771 if phase == 0 else 6772),
                    1 if passive else None,
                )
                self.assertNotIn(6772 if phase == 0 else 6771, h.states(actor))
                before_hp = data[2].actors[-7].hp
                stats = (actor.effect_stats.get(48, 0), actor.effect_stats.get(86, 0))
                attack = h.cast(
                    data, 754, data[2].actors[-7].position, action_id=20 + phase
                )
                damage = before_hp - attack.fight.actors[-7].hp
                self.assertGreater(damage, 0)
                self.assertEqual((actor.id, data[2].actors[-7].id), (7, -7))
                observations[passive, phase] = (stats, damage)
        # Native bindings:126/129 gain/lose final damage48;
        # 177/178 gain/lose WILLPOWER86. These are not armor families.
        for phase in (0, 1):
            base_stats, base_damage = observations[None, phase]
            expected = {
                (764, 0): (-20, 0),
                (764, 1): (20, 0),
                (5353, 0): (0, 20),
                (5353, 1): (0, -20),
            }
            for passive in (764, 5353):
                stats, damage = observations[passive, phase]
                self.assertEqual(
                    tuple(a - b for a, b in zip(stats, base_stats)),
                    expected[passive, phase],
                    observations,
                )
                if passive == 5353:
                    self.assertEqual(damage, base_damage, observations)
                elif phase == 0:
                    self.assertLess(damage, base_damage, observations)
                else:
                    self.assertGreater(damage, base_damage, observations)

    def test_marchitation_actual_target_turn_damages_and_removes_owned_state(self):
        h = helpers.XelorRuntimePipelineTests()
        observations = {}
        for enabled in (False, True):
            data = h.fixture(passives=(7195,) if enabled else ())
            paid = h.cast(data, 775, data[2].actors[-7].position, action_id=30)
            data = h.adopt(data, paid.fight)
            target = data[2].actors[-7]
            entries = [s for s in target.state_ledger.entries if s.reference == 6774]
            self.assertEqual(len(entries), int(enabled))
            if enabled:
                self.assertEqual(
                    (entries[0].caster_id, entries[0].target_id, entries[0].level),
                    (7, -7, 20),
                )
            self.assertNotIn(6774, h.states(data[2].actors[7]))
            before = target.hp
            trace = []
            original = EffectDispatcher.execute

            def observe(dispatcher, invocation, **kwargs):
                result = original(dispatcher, invocation, **kwargs)
                if invocation.reference in (
                    314323,
                    314327,
                    314356,
                    349637,
                    349638,
                    349640,
                ):
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
                turns.AniripsaGrantSummonPipelineTests().end_current_turn(data[2], data)
            self.assertEqual(data[2].current.id, -7)
            self.assertNotIn(6774, h.states(data[2].actors[-7]))
            completed = {ref for ref, caster, target_id, ok in trace if ok}
            self.assertEqual(314327 in completed, enabled, trace)
            self.assertEqual(314356 in completed, enabled, trace)
            observations[enabled] = before - data[2].actors[-7].hp
        self.assertEqual(observations[False], 0)
        self.assertGreater(observations[True], 0)

    def test_combat_mage_modifies_only_real_ap_loss_recipient_before_next_attack(self):
        h = helpers.XelorRuntimePipelineTests()
        observations = {}
        attacks = {}
        for enabled in (False, True):
            data = h.fixture(passives=(7193,) if enabled else ())
            data[2].move(3, 7, [(-7, -7, -1)])
            before = data[2].actors[-7].effect_stats.get(48, 0)
            owner_before = data[2].actors[7].effect_stats.get(48, 0)
            tx = h.cast(data, 775, data[2].actors[-7].position, action_id=40)
            target = tx.fight.actors[-7]
            entries = [s for s in target.state_ledger.entries if s.reference == 7790]
            self.assertEqual(len(entries), int(enabled))
            if enabled:
                self.assertEqual(
                    (entries[0].caster_id, entries[0].target_id, entries[0].level),
                    (7, -7, 3),
                )
            self.assertEqual(tx.fight.actors[7].effect_stats.get(48, 0), owner_before)
            observations[enabled] = target.effect_stats.get(48, 0) - before
            data = h.adopt(data, tx.fight)
            turns.AniripsaGrantSummonPipelineTests().end_current_turn(data[2], data)
            self.assertEqual(data[2].current.id, -7)
            from wakfu_server.combat_npc_spell import owned_spells, prepare_npc_spell

            enemy = data[2].actors[-7]
            owner = data[2].actors[7]
            # Real NPC MP obtains the adjacent melee context on its actual turn.
            destination = (owner.position[0] + 1, owner.position[1], owner.position[2])
            if enemy.position != destination:
                self.assertEqual(
                    sum(abs(enemy.position[i] - destination[i]) for i in (0, 1)), 1
                )
                self.assertEqual(enemy.position[2], destination[2])
                self.assertIn(destination, data[2].walkable)
                if data[2].edges is not None:
                    self.assertIn((enemy.position, destination), data[2].edges)
                before_mp = enemy.mp
                movement = data[2].server_move(-7, [destination])
                self.assertEqual(movement["path"], [destination])
                self.assertLess(enemy.mp, before_mp)
                self.assertEqual(enemy.position, destination)
            candidates = []
            attack = None
            for reference, level in sorted(
                owned_spells(data[2], {-7: data[1]}).items()
            ):
                try:
                    candidate = prepare_npc_spell(
                        data[2],
                        dict(
                            type="cast",
                            spellId=reference,
                            level=level,
                            targetId=7,
                            target=list(owner.position),
                        ),
                        data[0],
                        {-7: data[1]},
                        data[3],
                        action_id=50,
                        rng=data[4],
                    )
                except ValueError as error:
                    candidates.append((reference, str(error)))
                    continue
                if candidate.fight.actors[7].hp < owner.hp:
                    attack = candidate
                    break
            self.assertIsNotNone(attack, candidates)
            attacks[enabled] = owner.hp - attack.fight.actors[7].hp
        self.assertEqual(observations, {False: 0, True: -3})
        self.assertGreater(attacks[False], 0)
        self.assertGreater(attacks[True], 0)
        self.assertLessEqual(attacks[True], attacks[False])
