"""Focused copy semantics for persisted QI Trove byte topologies."""

from copy import deepcopy
import unittest

from wakfu_server.combat.combat_qi_registry import (
    NativeQIRegistry,
    _copy_byte_topology,
)


class QITopologyCopyTests(unittest.TestCase):
    @staticmethod
    def trove_state(keys=None, states=None):
        return {
            "keys": [0, 0, 0] if keys is None else keys,
            "states": [0, 0, 0] if states is None else states,
            "size": 0,
            "free": 3,
            "compact_removes": 10,
        }

    def test_exact_topology_matches_deepcopy_and_detaches_all_arrays(self):
        topology = {
            "2,4": self.trove_state([7, 0, 0], [1, 0, 0]),
            "3,4": self.trove_state([0, -3, 0], [0, 1, 0]),
        }
        expected = deepcopy(topology)

        copied = _copy_byte_topology(topology)

        self.assertEqual(copied, expected)
        self.assertIsNot(copied, topology)
        for cell in topology:
            self.assertIsNot(copied[cell], topology[cell])
            self.assertIsNot(copied[cell]["keys"], topology[cell]["keys"])
            self.assertIsNot(copied[cell]["states"], topology[cell]["states"])
        copied["2,4"]["keys"][0] = 99
        copied["3,4"]["states"].append(1)
        self.assertEqual(topology["2,4"]["keys"][0], 7)
        self.assertEqual(topology["3,4"]["states"], [0, 1, 0])

    def test_shared_states_and_arrays_keep_deepcopy_alias_semantics(self):
        shared_keys = [1, 0, 0]
        first = self.trove_state(shared_keys, [1, 0, 0])
        second = self.trove_state(shared_keys, [1, 0, 0])
        topology = {"1,1": first, "2,1": first, "3,1": second}

        copied = _copy_byte_topology(topology)
        expected = deepcopy(topology)

        self.assertEqual(copied, expected)
        self.assertIs(copied["1,1"], copied["2,1"])
        self.assertIs(copied["1,1"], not_first := copied["2,1"])
        self.assertIsNot(not_first, first)
        self.assertIs(copied["1,1"]["keys"], copied["3,1"]["keys"])
        self.assertIsNot(copied["1,1"]["keys"], shared_keys)

    def test_malformed_and_custom_cyclic_shapes_use_deepcopy_fallback(self):
        class TopologySubclass(dict):
            pass

        custom = TopologySubclass()
        custom["self"] = custom
        copied_custom = _copy_byte_topology(custom)
        self.assertIsNot(copied_custom, custom)
        self.assertIs(copied_custom["self"], copied_custom)
        expected_custom = deepcopy(custom)
        self.assertIs(expected_custom["self"], expected_custom)

        malformed_state = {"keys": [1], "unexpected": []}
        malformed_state["cycle"] = malformed_state
        malformed = {"0,0": malformed_state}
        copied = _copy_byte_topology(malformed)
        self.assertIsNot(copied["0,0"], malformed_state)
        self.assertIs(copied["0,0"]["cycle"], copied["0,0"])
        expected = deepcopy(malformed)
        self.assertIs(expected["0,0"]["cycle"], expected["0,0"])

    def test_registry_constructor_detaches_checkpoint_and_lifecycle_stays_equivalent(
        self,
    ):
        arena = dict(x=0, y=0, width=3, height=2, cell_masks=[0] * 6)
        source = NativeQIRegistry(arena, [None] * 127)
        source.capture_fresh_cell_topology([])
        row = dict(
            identity=("actor", 41),
            indexed=True,
            movement_blocking=True,
            position=(0, 0),
            radius=0,
        )
        self.assertEqual(source.register(row), 0)
        self.assertEqual(
            source.register(dict(row, identity=("actor", 42), position=(1, 0))), 1
        )
        persisted_slots = source.serialized_slots()
        persisted_topology = source.serialized_byte_topology()
        persisted_cells = source.serialized_cells()
        expected_topology = deepcopy(persisted_topology)

        restored = NativeQIRegistry(
            arena,
            persisted_slots,
            touched_cells=persisted_cells,
            byte_topology=persisted_topology,
        )
        self.assertEqual(restored.serialized_byte_topology(), expected_topology)
        self.assertIsNot(restored.byte_topology, persisted_topology)
        for cell, state in expected_topology.items():
            self.assertIsNot(restored.byte_topology[cell], persisted_topology[cell])
            self.assertIsNot(restored.byte_topology[cell]["keys"], state["keys"])

        # Mutating either the persisted input or the restored registry must
        # not affect the other; subsequent native QI operations still match
        # the independently deep-copied checkpoint representation.
        persisted_topology["0,0"]["keys"][0] = 99
        self.assertEqual(restored.ordered_U(0, 0), (0,))
        restored.move(0, ("actor", 41), (2, 1))
        self.assertEqual(restored.snapshot().U(2, 1), frozenset((0,)))
        self.assertEqual(restored.snapshot().U(1, 0), frozenset((1,)))
        restored.remove(1, ("actor", 42))
        serialized = restored.serialized_byte_topology()
        reloaded = NativeQIRegistry(
            arena,
            restored.serialized_slots(),
            touched_cells=restored.serialized_cells(),
            byte_topology=serialized,
        )
        self.assertEqual(reloaded.snapshot().U(2, 1), frozenset((0,)))


if __name__ == "__main__":
    unittest.main()
