"""A new owner client must receive claimed NPC appearances before cvb."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from protocol_codec import Reader
from wakfu_server.combat.combat_reconnect_world_actors import ordinary_npc_appearances
from wakfu_server.combat.combat_session_adapter import CombatSessionAdapter
from wakfu_server.monsters import owned_instance


class ReconnectWorldActorTests(unittest.TestCase):
    def setUp(self):
        self.monster = owned_instance(4, 8, -200, map_id=1134, x=-10, y=-2, z=-1)
        self.actor = SimpleNamespace(
            id=-200, controlled=False, team=1, position=(-9, -3, -1)
        )
        self.player = SimpleNamespace(
            id=13, controlled=True, team=0, position=(-8, -3, -1)
        )
        self.fight = SimpleNamespace(
            actors={13: self.player, -200: self.actor},
            native_summon_registrations={},
            phase="placement",
        )
        self.shared = SimpleNamespace(
            map_id=1134,
            instance_id=0,
            join_context={
                "monsters": {-200: self.monster},
                "group_key": (1134, 0, 555),
            },
        )

    def test_claimed_npc_spawn_uses_current_position_and_original_profile(self):
        before = deepcopy(vars(self.fight)), deepcopy(vars(self.shared))
        packets = ordinary_npc_appearances(self.fight, self.shared)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][0], 12608)
        outer = Reader(packets[0][1])
        self.assertEqual(
            tuple(outer.number(t) for t in ("B", "B", "B", "q")), (0, 1, 1, -200)
        )
        actor = Reader(outer.take(outer.number("H")))
        outer.finish()
        self.assertEqual(
            tuple(actor.number(t) for t in ("B", "q", "B", "q")), (11, -200, 1, -1)
        )
        actor.text("H")
        self.assertEqual(actor.number("h"), 4)
        self.assertEqual(
            tuple(actor.number(t) for t in ("i", "i", "h", "q")), (-9, -3, -1, 1134)
        )
        self.assertEqual((vars(self.fight), vars(self.shared)), before)

    def test_owned_reconnect_orders_appearance_before_placement_and_active_bootstrap(
        self,
    ):
        adapter = CombatSessionAdapter(SimpleNamespace())
        for phase in ("placement", "active"):
            with self.subTest(phase=phase):
                self.fight.phase = phase
                with patch(
                    "wakfu_server.combat.combat_reconnect_snapshot.owned_snapshot",
                    return_value=((12847, b"combat"),),
                ):
                    packets = adapter.owned_reconnect_bootstrap(
                        self.fight, self.shared, None
                    )
                self.assertEqual([op for op, _ in packets], [12608, 12847])

    def test_friendly_duel_does_not_fabricate_npcs(self):
        self.shared.join_context = {}
        self.assertEqual(ordinary_npc_appearances(self.fight, self.shared), ())

    def test_rift_keeps_its_separate_wave_snapshot(self):
        self.fight.rift_wave_state = {"wave": 2}
        self.assertEqual(ordinary_npc_appearances(self.fight, self.shared), ())

    def test_registered_summons_are_not_recreated_as_world_monsters(self):
        summon = SimpleNamespace(id=88, controlled=False, team=0, position=(-8, -2, -1))
        self.fight.actors[88] = summon
        self.fight.native_summon_registrations[88] = {"owner": 13}
        packets = ordinary_npc_appearances(self.fight, self.shared)
        outer = Reader(packets[0][1])
        self.assertEqual(
            tuple(outer.number(t) for t in ("B", "B", "B", "q")), (0, 1, 1, -200)
        )

    def test_incomplete_or_foreign_group_authority_is_rejected_without_mutation(self):
        cases = [
            {"monsters": {}, "group_key": (1134, 0, 555)},
            {"monsters": {-200: self.monster}, "group_key": (527, 0, 555)},
            {
                "monsters": {-200: dict(self.monster, id=-201)},
                "group_key": (1134, 0, 555),
            },
        ]
        for context in cases:
            with self.subTest(context=context):
                self.shared.join_context = context
                before = deepcopy(vars(self.fight)), deepcopy(vars(self.shared))
                with self.assertRaises(ValueError):
                    ordinary_npc_appearances(self.fight, self.shared)
                self.assertEqual((vars(self.fight), vars(self.shared)), before)
