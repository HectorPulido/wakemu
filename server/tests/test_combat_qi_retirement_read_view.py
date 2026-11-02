"""Standalone QI reads share one retirement validation, retaining all history."""
from unittest.mock import patch
import unittest

from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_ordinary_qi_retirement import complete_ordinary_qi_death
from wakfu_server.combat_qi_fight import (
    current_registry,
    install_fresh_actor_slots,
    prepare_fresh_actor_slots,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_trove_long_map import NativeTroveLongMap
from wakfu_server.combat_geometry_snapshot import source_snapshot


class StandaloneRetirementReadViewTests(unittest.TestCase):
    def test_actual_current_registry_cost_is_constant_in_retired_actor_count(self):
        counts = []
        for quantity in (2, 8):
            pc = Actor(7, 0, (0, 0, 0), 100, 6, 6, 10, 10, owner_id=1, controlled=True)
            npcs = [
                Actor(-100 - index, 1, (index + 1, 0, 0), 30, 0, 0, 1, 10)
                for index in range(quantity)
            ]
            cells = {(x, 0, 0) for x in range(quantity + 2)}
            fight = Fight(
                99,
                [pc, *npcs],
                cells,
                {0: {pc.position}, 1: {npc.position for npc in npcs}},
            )
            for actor in fight.actors.values():
                actor.physical_radius = 0
                actor.native_fight_property_counts = {}
            fight.native_qi_snapshot = dict(
                x=0, y=0, width=quantity + 2, height=1, cell_masks=[0] * (quantity + 2)
            )
            initialize_global_pv_collections(fight, tuple(fight.actors))
            install_fresh_actor_slots(
                fight,
                prepare_fresh_actor_slots(
                    fight,
                    physical_radii={actor.id: 0 for actor in fight.actors.values()},
                ),
            )
            fight.ready(1)
            for npc in npcs:
                fight.apply_effect_damage(pc.id, npc.id, npc.hp)
                self.assertTrue(complete_ordinary_qi_death(fight, npc))
            before = source_snapshot(fight)
            constructor = NativeTroveLongMap.__init__
            calls = []

            def counted(instance, *args, **kwargs):
                calls.append(1)
                constructor(instance, *args, **kwargs)

            with patch.object(NativeTroveLongMap, "__init__", counted):
                current_registry(fight)
            counts.append(len(calls))
            self.assertEqual(source_snapshot(fight), before)
            self.assertEqual(len(fight.actors), quantity + 1)
        self.assertEqual(counts, [2, 2])  # One retirement view plus one live PV.
