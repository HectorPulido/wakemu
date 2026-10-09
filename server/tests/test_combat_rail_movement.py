import copy
import unittest
import struct
from types import SimpleNamespace

from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_rail_movement import movement_cost, rail_path_cost
from wakfu_server.combat_microbot_network import SOURCE
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_geometry_snapshot import source_snapshot


class Authority:
    def __init__(self, properties=(), carried=False):
        self.pb = frozenset(properties)
        self.carried = carried

    def __call__(self, fight, actor):
        if fight.actors.get(actor.id) is not actor:
            raise ValueError("Not actual current actor")
        return NativeActorAuthority(
            targeting={},
            is_player=True,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=self.carried,
            breed_id=16,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
        )

    def properties(self, fight, actor):
        return self.pb


class RailMovementTests(unittest.TestCase):
    def fixture(self, properties=(), owner_team=0, carried=False):
        actor = SimpleNamespace(id=7, team=0, position=(0, 0, 0), mp=2)
        owner = SimpleNamespace(id=8, team=owner_team)
        cells = [(x, 0, 0) for x in range(11)]
        fight = SimpleNamespace(
            actors={7: actor, 8: owner},
            native_rail_movement_authority=Authority(properties, carried),
            native_microbot_networks={
                8: dict(source=SOURCE, segments=[[[0, 0, 0], [10, 0, 0]]], cells=cells)
            },
        )
        return fight, actor

    def test_native_three_cells_per_mp_and_one_cost_property(self):
        for length in range(1, 13):
            self.assertEqual(rail_path_cost(length, False), (length + 2) // 3)
            self.assertEqual(rail_path_cost(length, True), 1)
        fight, actor = self.fixture()
        self.assertEqual(
            movement_cost(fight, actor, [(x, 0, 0) for x in range(1, 7)]), (2, True)
        )
        self.assertEqual(
            movement_cost(fight, actor, [(x, 0, 0) for x in range(1, 8)]), (7, False)
        )
        fight.native_rail_movement_authority.pb = frozenset({98})
        self.assertEqual(
            movement_cost(fight, actor, [(x, 0, 0) for x in range(1, 11)]), (1, True)
        )

    def test_team_network_not_owner_and_full_altitude_membership(self):
        fight, actor = self.fixture()
        self.assertEqual(movement_cost(fight, actor, [(1, 0, 0)]), (1, True))
        self.assertEqual(movement_cost(fight, actor, [(1, 0, 1)]), (1, False))
        fight.actors[8].team = 1
        self.assertEqual(movement_cost(fight, actor, [(1, 0, 0)]), (1, False))

    def test_rails_only_and_carried_native_fallback(self):
        fight, actor = self.fixture({77})
        with self.assertRaisesRegex(ValueError, "restricted to rails"):
            movement_cost(fight, actor, [(0, 1, 0)])
        fight.native_rail_movement_authority.carried = True
        self.assertEqual(movement_cost(fight, actor, [(0, 1, 0)]), (1, False))

    def test_retirement_removes_membership_without_recovering_network(self):
        fight, actor = self.fixture({77})
        fight.native_microbot_networks[8]["segments"] = []
        fight.native_microbot_networks[8]["cells"] = []
        with self.assertRaisesRegex(ValueError, "restricted to rails"):
            movement_cost(fight, actor, [(1, 0, 0)])

    def test_checkpoint_omits_provider_and_actual_rebind_is_required(self):
        fight, actor = self.fixture()
        encoded = snapshot(fight)
        self.assertNotIn("native_rail_movement_authority", encoded)
        self.assertNotIn("native_rail_movement_authority", source_snapshot(fight))
        restored = copy.deepcopy(fight)
        del restored.native_rail_movement_authority
        with self.assertRaisesRegex(ValueError, "actor authority"):
            movement_cost(restored, restored.actors[7], [(1, 0, 0)])
        restored.native_rail_movement_authority = Authority()
        self.assertEqual(
            movement_cost(restored, restored.actors[7], [(1, 0, 0)]), (1, True)
        )

    def test_ordinary_unknown_network_is_not_guessed(self):
        actor = SimpleNamespace(mp=2)
        self.assertEqual(
            movement_cost(SimpleNamespace(), actor, [(1, 0, 0)]), (1, False)
        )
        fight, actor = self.fixture()
        fight.native_microbot_networks[8]["source"] = "unattested"
        with self.assertRaisesRegex(ValueError, "provenance"):
            movement_cost(fight, actor, [(1, 0, 0)])

    def actual_fight(self, properties=(), networks=True):
        player = Actor(7, 0, (0, 0, 0), 60, 6, 6, 20, 200, 3, True)
        enemy = Actor(-7, 1, (11, 0, 0), 4500, 6, 3, 1, 133)
        cells = {(x, 0, 0) for x in range(12)}
        edges = {(a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1}
        fight = Fight(
            2,
            [player, enemy],
            cells,
            {0: {player.position}, 1: {enemy.position}},
            edges,
        )
        fight.ready(3)
        fight.native_rail_movement_authority = Authority(properties)
        if networks:
            fight.native_microbot_networks = {
                7: dict(
                    source=SOURCE,
                    segments=[[[0, 0, 0], [10, 0, 0]]],
                    cells=[(x, 0, 0) for x in range(11)],
                )
            }
        return RuntimeMessages(fight)

    def test_real_fsm_spends_rail_cost_serializes_and_checkpoints(self):
        for length in (3, 4, 6):
            with self.subTest(length=length):
                runtime = self.actual_fight()
                path = [(x, 0, 0) for x in range(1, length + 1)]
                body = struct.pack(">q", 7) + b"".join(
                    struct.pack(">iih", *cell) for cell in path
                )
                packets, event = apply_client(
                    runtime, 3, body, lambda actor: struct.pack(">i", actor.mp)
                )
                cost = (length + 2) // 3
                self.assertEqual(event["cost"], cost)
                self.assertTrue(event["on_rails"])
                self.assertEqual(runtime.fight.actors[7].mp, 6 - cost)
                self.assertEqual(runtime.fight.actors[7].position, path[-1])
                self.assertEqual(
                    [number for number, _ in packets], [13624, 13420, 12873]
                )
                self.assertEqual(packets[-1][1][-4:], struct.pack(">i", 6 - cost))
                saved = snapshot(runtime.fight)
                self.assertEqual(saved["actors"]["7"]["mp"], 6 - cost)
                self.assertNotIn("native_rail_movement_authority", saved)

    def test_real_fsm_ordinary_and_rejected_paths_preserve_resources(self):
        runtime = self.actual_fight(networks=False)
        event = runtime.fight.move(3, 7, [(1, 0, 0), (2, 0, 0), (3, 0, 0)])
        self.assertEqual(event["cost"], 3)
        self.assertNotIn("on_rails", event)
        self.assertEqual(runtime.fight.actors[7].mp, 3)
        rail = self.actual_fight({98})
        before = snapshot(rail.fight)
        with self.assertRaisesRegex(ValueError, "Invalid combat movement path"):
            rail.fight.move(3, 7, [(3, 0, 0)])
        self.assertEqual(snapshot(rail.fight), before)

    def test_untyped_provider_never_attests_rail_carry(self):
        fight, actor = self.fixture()

        class Untyped(Authority):
            def __call__(self, *args):
                return SimpleNamespace(is_carried=False)

        fight.native_rail_movement_authority = Untyped()
        with self.assertRaisesRegex(ValueError, "snapshot"):
            movement_cost(fight, actor, [(1, 0, 0)])
