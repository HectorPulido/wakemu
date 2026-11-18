"""Actual native constructors and reactions; offline table, not captured formation."""

from random import Random
import unittest


class GhostReefNativeRuntimeTests(unittest.TestCase):
    def test_constructor_original_add_death_and_boss_regeneration_summon(self):
        from native_recorded_instance_fixture import original_bootstrap_publication
        from jondo_native_support_probe import build_fixture
        from wakfu_server.combat_server_spell import (
            server_runtime,
            prepare_server_turn_end,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        with original_bootstrap_publication():
            case = build_fixture(
                3788,
                15,
                allies=((3786, 15, (-5, -7, -1)), (3787, 15, (-5, -6, -1))),
            )
        fight = case.fight
        self.assertEqual(fight.actors[-7].max_hp, 1000)
        self.assertEqual(fight.actors[-8].max_hp, 56)
        self.assertEqual(fight.actors[-9].max_hp, 47)
        for identity, expected in (
            (-7, [3731, 1, 0, 3797, 1, 0]),
            (-8, [3726, 1, 0, 2666, 1, 0]),
            (-9, [3726, 1, 0, 2666, 1, 0]),
        ):
            receipt = fight.native_npc_initialization_receipts[identity]
            self.assertTrue(receipt["initialized"])
            self.assertEqual(receipt["raw_triples"], expected)
        factory, _ = server_runtime(
            case.characters[7],
            case.monsters,
            case.decks[7],
            action_id=9,
            critical=False,
            rng=Random(17),
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        # A bounded native Qe.g(PV) damage fixture, not a player spell claim.
        # The real handler produces the lethal source and actual1010 delivery.
        with fight.effect_resolution():
            dispatcher.execute_pt(
                EffectInvocation(
                    162424,
                    15,
                    7,
                    -8,
                    fight.actors[-8].position,
                    native_preselected_target=True,
                )
            )
        self.assertEqual(fight.actors[-8].hp, 0)
        self.assertEqual(fight.actors[-9].hp, 47)
        self.assertEqual(fight.actors[-7].hp, 750)
        self.assertEqual(
            [
                row["amount"]
                for row in fight.events
                if row.get("kind") == "damage"
                and row.get("source_id") == row.get("target_id") == -7
            ],
            [250],
        )
        before = set(fight.actors)
        for step in range(5):
            current = fight.current
            fight, _ = prepare_server_turn_end(
                case.characters[7],
                case.monsters,
                fight,
                case.decks[7],
                actor_id=current.id,
                action_id=10 + step,
                rng=Random(17),
            )
            if set(fight.actors) - before:
                break
            if current.controlled:
                fight.end_turn(current.owner_id, current.id, current.turn_count)
            else:
                fight.end_server_turn(current.id, fight.turn_id)
        created = set(fight.actors) - before
        self.assertEqual(len(created), 1)
        summon = fight.actors[created.pop()]
        self.assertEqual(summon.team, fight.actors[-7].team)
        self.assertEqual(summon.max_hp, 56)
        self.assertEqual(
            {row.reference for row in summon.state_ledger.entries}, {3726, 2666}
        )
        self.assertEqual(summon.native_summon_source["ref"], 3786)
