"""Pure legacy-oracle equivalence; actual-size terrain, no game runtime."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_qi_registry as candidate
from wakfu_server.combat_qi_snapshot import ImmutableQIMasks
from wakfu_server import combat_trove_byte_set as trove

FIXTURES = Path(__file__).parent / "fixtures"
CONTRACT = json.loads((FIXTURES / "native_trove_byte_set_under5.json").read_text())
_SPEC = importlib.util.spec_from_file_location(
    "wakfu_server._qi_registry_under5_oracle", FIXTURES / "qi_registry_before_under5.py"
)
legacy = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(legacy)


def row(identity, position, radius=0, indexed=True):
    return dict(
        identity=["actor", identity],
        position=list(position),
        radius=radius,
        indexed=indexed,
        movement_blocking=True,
    )


def fixture(registry_type, *, rows=None, large=False):
    width, height, x, y = (127, 145, -64, -72) if large else (9, 9, -4, -4)
    arena = dict(
        x=x,
        y=y,
        width=width,
        height=height,
        cell_masks=ImmutableQIMasks([0] * (width * height)),
    )
    slots = [None] * 127
    rows = (
        [
            (0, row(1, (0, 0))),
            (3, row(2, (1, 0))),
            (19, row(3, (0, 1))),
            (126, row(4, (-1, 0))),
        ]
        if rows is None
        else rows
    )
    for slot, descriptor in rows:
        slots[slot] = deepcopy(descriptor)
    registry = registry_type(arena, slots)
    registry.capture_fresh_cell_topology([slot for slot, _ in rows])
    return registry


def state(registry):
    return deepcopy(
        dict(
            slots=registry.slots,
            touched=registry.touched_cells,
            byte_topology=registry.byte_topology,
            terrain={
                name: getattr(registry.terrain, name)
                for name in ("x", "y", "width", "height", "masks")
            },
        )
    )


def outcome(registry, operation):
    try:
        return ("ok", operation(registry))
    except Exception as error:
        return ("error", type(error).__name__, str(error))


class RegistryUnder5OracleTests(unittest.TestCase):
    def setUp(self):
        self.contract = patch.object(trove, "_contract", return_value=CONTRACT)
        self.contract.start()
        self.addCleanup(self.contract.stop)

    def pair(self, **kwargs):
        return fixture(legacy.NativeQIRegistry, **kwargs), fixture(
            candidate.NativeQIRegistry, **kwargs
        )

    def assert_operation(self, pair, operation):
        old, new = pair
        self.assertEqual(outcome(old, operation), outcome(new, operation))
        self.assertEqual(state(old), state(new))

    def test_actual_sized_four_radius_zero_population_has_identical_all_cell_queries(
        self,
    ):
        pair = self.pair(large=True)
        self.assertEqual(len(pair[0].terrain.masks), 18415)
        for cell in ((0, 0), (1, 0), (-1, 0), (0, 1), (3, 3), (-65, 0), (1000, 0)):
            self.assert_operation(
                pair, lambda registry, cell=cell: registry.ordered_U(*cell)
            )
        self.assertEqual(pair[0].snapshot().occupancy, pair[1].snapshot().occupancy)

    def test_overlapping_positive_negative_and_clipped_radii_preserve_trove_order(self):
        rows = [
            (0, row(1, (0, 0), 2)),
            (1, row(2, (1, 0), -2)),
            (7, row(3, (-4, -4), 1)),
            (126, row(4, (0, 0), 0)),
        ]
        pair = self.pair(rows=rows)
        for x in range(-5, 6):
            for y in range(-5, 6):
                self.assert_operation(
                    pair, lambda registry, x=x, y=y: registry.ordered_U(x, y)
                )

    def test_move_toggle_remove_and_reused_slot_keep_history_and_touched_empty(self):
        pair = self.pair()
        operations = [
            lambda r: r.move(3, ["actor", 2], (2, 2)),
            lambda r: r.ordered_U(1, 0),
            lambda r: r.toggle(0, ["actor", 1], False),
            lambda r: r.ordered_U(0, 0),
            lambda r: r.toggle(0, ["actor", 1], True),
            lambda r: r.remove(19, ["actor", 3]),
            lambda r: r.register(row(5, (0, 1))),
            lambda r: r.ordered_U(0, 1),
            lambda r: r.move(126, ["actor", 4], (-10, -10)),
        ]
        for operation in operations:
            self.assert_operation(pair, operation)
        self.assertIn((1, 0), pair[1].touched_cells)

    def test_live_external_slot_mutations_are_revalidated_each_query(self):
        mutations = [
            lambda r: r.slots[126].update(radius=True),
            lambda r: r.slots[126].update(radius=128),
            lambda r: r.slots[126].update(position=[True, 0]),
            lambda r: r.slots[126].update(position=[(1 << 31), 0]),
            lambda r: r.slots[126].update(position=[0]),
            lambda r: r.slots[126].update(position=[0, 0, 0]),
            lambda r: r.slots[126].update(position=[20, 20]),
            lambda r: r.slots[126].pop("position"),
            lambda r: r.slots[126].pop("indexed"),
            lambda r: r.slots.append(row(100, (0, 0))),
            lambda r: r.slots[126].update(indexed=False, position=["ignored"]),
            lambda r: r.slots[126].update(identity=["unread-by-snapshot"]),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                pair = self.pair()
                for registry in pair:
                    mutation(registry)
                self.assert_operation(pair, lambda r: r.ordered_U(0, 0))

    def test_live_terrain_mutations_and_error_order_match_legacy(self):
        mutations = [
            lambda r: setattr(r.terrain, "width", True),
            lambda r: setattr(r.terrain, "width", 0),
            lambda r: setattr(r.terrain, "height", 40000),
            lambda r: setattr(r.terrain, "masks", [0]),
            lambda r: setattr(r.terrain, "masks", [True] * 81),
            lambda r: setattr(r.terrain, "masks", [32768] * 81),
            lambda r: setattr(r.terrain, "masks", tuple([0] * 81)),
            lambda r: setattr(r.terrain, "masks", "not-masks"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                pair = self.pair()
                for registry in pair:
                    mutation(registry)
                self.assert_operation(pair, lambda r: r.ordered_U(0, 0))
        pair = self.pair()
        for registry in pair:
            registry.slots[126]["position"] = [0]
            registry.terrain.masks = [True] * 81
        self.assert_operation(pair, lambda r: r.ordered_U(0, 0))

    def test_invalid_trove_history_is_never_skipped_for_matching_live_population(self):
        mutations = [
            lambda s: s.update(size=True),
            lambda s: s.update(size=99),
            lambda s: s["states"].__setitem__(0, True),
            lambda s: s.update(keys=[0]),
            lambda s: s.update(compact_removes="invalid"),
        ]
        for mutation in mutations:
            pair = self.pair()
            for registry in pair:
                mutation(registry.byte_topology["0,0"])
            self.assert_operation(pair, lambda r: r.ordered_U(0, 0))
        pair = self.pair()
        for registry in pair:
            registry.byte_topology["0,0"] = trove.NativeTroveByteSet().state
        self.assert_operation(pair, lambda r: r.ordered_U(0, 0))

    def test_outside_queries_keep_legacy_early_return_even_with_invalid_population(
        self,
    ):
        pair = self.pair()
        for registry in pair:
            registry.slots[126]["radius"] = 128
            registry.byte_topology = None
        self.assert_operation(pair, lambda r: r.ordered_U(-100, -100))
        self.assert_operation(pair, lambda r: r.ordered_U(True, 0))

    def test_failed_late_obstacle_does_not_publish_earlier_touched_columns(self):
        pair = self.pair()
        before = [set(r.touched_cells) for r in pair]
        for registry in pair:
            registry.slots[0]["position"] = [3, 3]
            registry.slots[126]["radius"] = 128
        self.assert_operation(pair, lambda r: r.ordered_U(0, 0))
        self.assertEqual([r.touched_cells for r in pair], before)

    def test_direct_occupancy_change_is_detected_without_checkpoint_cache(self):
        pair = self.pair()
        self.assert_operation(pair, lambda r: r.ordered_U(0, 0))
        for registry in pair:
            registry.slots[0]["position"] = [3, 3]
        self.assert_operation(pair, lambda r: r.ordered_U(0, 0))
        self.assert_operation(pair, lambda r: r.ordered_U(3, 3))

    def test_custom_snapshot_and_touched_collection_preserve_legacy_dispatch(self):
        pair = self.pair()
        for registry in pair:
            registry.snapshot = lambda: SimpleNamespace(U=lambda x, y: frozenset({0}))
        self.assert_operation(pair, lambda r: r.ordered_U(0, 0))
        pair = self.pair()
        for registry in pair:
            registry.touched_cells = dict.fromkeys(registry.touched_cells)
        self.assert_operation(pair, lambda r: r.ordered_U(0, 0))
        pair = self.pair()
        for registry in pair:
            registry.terrain.aK = lambda x, y: True
        self.assert_operation(pair, lambda r: r.ordered_U(0.0, 0))

    def test_slot_copy_retains_cross_row_aliases_and_detaches_input(self):
        position = [0, 0]
        rows = [row(1, position), row(2, position)]
        rows[0]["position"] = rows[1]["position"] = position
        copied = candidate._copy_slots(rows + [None] * 125)
        self.assertIs(copied[0]["position"], copied[1]["position"])
        self.assertIsNot(copied[0]["position"], position)
        copied[0]["position"][0] = 7
        self.assertEqual(position, [0, 0])
        self.assertEqual(copied[1]["position"], [7, 0])

    def test_extra_fields_cycles_and_subclasses_use_full_deepcopy_semantics(self):
        cyclic = row(1, (0, 0))
        cyclic["custom"] = cyclic
        copied = candidate._copy_slots([cyclic] + [None] * 126)
        self.assertIs(copied[0]["custom"], copied[0])
        self.assertIsNot(copied[0], cyclic)

        class Row(dict):
            pass

        source = Row(row(2, (0, 0)))
        self.assertIs(type(candidate._copy_slots([source])[0]), Row)
        pair = self.pair(rows=[(0, cyclic)])
        self.assertEqual(pair[0].slots[0]["custom"] is pair[0].slots[0], True)
        self.assertEqual(pair[1].slots[0]["custom"] is pair[1].slots[0], True)

    def test_population_endpoint_and_rectangle_wrap_guards_match(self):
        cases = [((2147483646, 0), 1), ((-2147483648, 0), 1), ((0, 0), 127)]
        for position, radius in cases:
            pair = self.pair()
            for registry in pair:
                registry.slots[126].update(position=list(position), radius=radius)
            self.assert_operation(pair, lambda r: r.ordered_U(0, 0))
