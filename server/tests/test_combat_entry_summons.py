"""Admitted native summon casts cross each entry route with real effects."""
import os
from random import Random
import unittest
from unittest.mock import patch
from wakfu_server.combat_entry_executor import entry_route
from wakfu_server.combat_geometry_snapshot import source_snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativeSummonEntryContractTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"},
    )
    def test_controlled_wauwau_casts_owned_stabilization_through_player_entry(self):
        import test_class_summon_action_consequences_osa_ugi as fixture

        (
            native,
            characters,
            decks,
            fight,
            child,
        ) = fixture.WauwauActionConsequencesTests().controlled_summon()
        actor = fight.actors[child]
        self.assertEqual(entry_route(actor, "player"), "summon.player")
        before = source_snapshot(fight)
        ap, wp = (actor.ap, actor.effect_stats[4])
        results = {}
        results["current"] = native.cast(
            characters, decks, fight, child, 6294, actor.position, 60
        )
        new = results["current"]
        self.assertEqual([op for op, _ in new.packets[:2]], [12588, 12678])
        self.assertNotIn(13494, [op for op, _ in new.packets])
        self.assertTrue(new.outcomes)
        self.assertEqual(source_snapshot(fight), before)
        after = new.fight.actors[child]
        self.assertEqual(after.direction, actor.direction)  # Native self-cell cast.
        self.assertIn(3434, {state.reference for state in after.state_ledger.entries})
        self.assertNotIn(
            3434, {state.reference for state in actor.state_ledger.entries}
        )
        self.assertEqual((after.ap, after.effect_stats[4]), (ap - 2, wp - 1))

    def test_registered_npc_root_summon_casts_owned_damage_through_npc_entry(self):
        from validate_monster_spell_activation import fixture
        from wakfu_server.combat_server_spell import (
            server_runtime,
            prepare_server_turn_end,
        )
        from wakfu_server.combat_summon import (
            SummonSpecification,
            fresh_summon_insertion,
        )
        from wakfu_server.combat_summon_creation import NativeSummonBuilder
        from wakfu_server.combat_summon_initialization import summon_initializer
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
        from wakfu_server.combat_effective_control import effective_server_controlled
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fight, character, monsters, deck = fixture(
            6, 4, (-10, -7, -1), native_lifecycle=True
        )
        owner = fight.current
        self.assertIn(owner.id, monsters)
        factory, _ = server_runtime(
            character, monsters, deck, action_id=1, critical=False, rng=Random(0)
        )
        enemy = fight.actors[7]
        occupied = {actor.position for actor in fight.actors.values() if actor.hp > 0}
        cell = next(
            (
                cell
                for cell in sorted(
                    fight.walkable,
                    key=lambda cell: (
                        abs(cell[0] - enemy.position[0])
                        + abs(cell[1] - enemy.position[1]),
                        cell,
                    ),
                )
                if cell not in occupied and cell[2] == enemy.position[2]
            )
        )
        child = max([0, *fight.actors]) + 1
        spec = SummonSpecification(
            3748, 200, False, owner.direction, owner.team, "caster", 1
        )
        actor, registration = NativeSummonBuilder(
            factory.summon_authority, initialize_states=summon_initializer(factory, [])
        )(fight, spec, owner.id, child, cell)
        order, current = fresh_summon_insertion(
            fight, spec, caster_id=owner.id, actor_id=child
        )
        factory.summon_authority.register(
            fight, actor, registration, new_order=order, new_turn_index=current
        )
        registered_summon_stats(actor, fight, character["map_id"])
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        producer = dispatcher.effects["377764"]
        self.assertEqual(producer["effect_class"], 304)
        self.assertEqual(producer["parameters"][0], 8187)
        self.assertEqual(producer["criteria"], 'IsOwnSummon(3748, "target")')
        with fight.effect_resolution():
            dispatcher.execute(
                EffectInvocation(
                    377764,
                    200,
                    owner.id,
                    child,
                    cell,
                    native_explicit_target=True,
                    native_preselected_target=True,
                )
            )
        self.assertIn(8187, {state.reference for state in actor.state_ledger.entries})
        for step in range(len(fight.actors) * 2 + 1):
            if fight.current is not None and fight.current.id == child:
                break
            current = fight.current
            preview, _ = prepare_server_turn_end(
                character,
                monsters,
                fight,
                deck,
                actor_id=current.id,
                action_id=10 + step,
                rng=Random(0),
            )
            current = preview.actors[current.id]
            if effective_server_controlled(preview, current):
                preview.end_server_turn(current.id, preview.turn_id)
            else:
                preview.end_turn(current.owner_id, current.id, current.turn_count)
            RuntimeMessages(preview).turn_started()
            fight = preview
        self.assertEqual(fight.current.id, child)
        self.assertTrue(effective_server_controlled(fight, fight.current))
        self.assertEqual(entry_route(fight.current, "npc"), "summon.npc")
        spells = owned_spells(fight, monsters, character=character)
        self.assertIn(5023, spells)
        actor, enemy = (fight.current, fight.actors[7])
        before = source_snapshot(fight)
        ap = actor.ap
        results = {}
        results["current"] = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=5023,
                level=spells[5023],
                targetId=7,
                target=list(enemy.position),
            ),
            character,
            monsters,
            deck,
            action_id=30,
            rng=Random(0),
        )
        new = results["current"]
        self.assertEqual(
            [op for op, _ in new.packets[:4]], [13494, 13420, 12588, 12678]
        )
        self.assertTrue(new.outcomes)
        self.assertEqual(source_snapshot(fight), before)
        self.assertLess(new.fight.actors[7].hp, enemy.hp)
        self.assertEqual(new.fight.actors[child].ap, ap - new.plan["costs"]["ap"])
