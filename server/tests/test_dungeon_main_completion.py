"""Focused public-namespace completion projection tests; no live database."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch, Mock
from contextlib import contextmanager
from wakfu_server.combat_sn_path import NativeSnColumns
import struct, sys, unittest
from types import ModuleType
import wakfu_server
from wakfu_server import (
    dungeon_main_completion as completion,
    dungeon_physical_doors as physical,
    dungeon_native_flow as flow,
)


class MainCompletionTests(unittest.TestCase):
    def setUp(self):
        self.rule = dict(
            map_id=10,
            main_room_order=2,
            gates=[dict(source_id=99, position=[2, 0, 0])],
            traversal_cells=[[2, 0, 0], [3, 0, 0]],
            presentation=dict(scenario_id=20, event_id=30, parameters=[-1]),
        )
        self.top = dict(
            policy=physical.POLICY,
            asset_map_id=10,
            rooms=[
                dict(order=1, cells=[[0, 0, 0]], anchor=[0, 0, 0]),
                dict(order=2, cells=[[1, 0, 0]], anchor=[1, 0, 0]),
            ],
            physical_doors=[
                dict(
                    source_id=99,
                    source_room=2,
                    destination_room=2,
                    position=[2, 0, 0],
                    requires_completion=True,
                )
            ],
            exploration_geometry=dict(
                cells=[[i, 0, 0] for i in range(4)],
                edges=[[[i, 0, 0], [i + 1, 0, 0]] for i in range(3)],
            ),
            main_completion=dict(
                policy=completion.POLICY, rule_key="fixture", rule_sha256="b" * 64
            ),
            physical_exit_objects=[],
        )

    @contextmanager
    def native(self, *, multiple=False):
        rows = [[0, 0, 0, 0, 0, False]] + (
            [[10, -1, 0, 0, 0, True]] if multiple else []
        )
        data = dict(
            schema="native-Sn-Vy-columns-v1",
            map_id=10,
            source_sha256="c" * 64,
            chunks=[
                dict(
                    x=0,
                    y=0,
                    width=18,
                    height=18,
                    columns=[[i, 0, rows] for i in range(4)],
                )
            ],
        )
        columns = NativeSnColumns(data, map_id=10, source_sha256="c" * 64)
        with patch.multiple(
            "wakfu_server.native_catalog", release=lambda: "release"
        ), patch.object(NativeSnColumns, "from_published", return_value=columns):
            yield

    def requirement(self):
        return patch.object(completion, "_native_rule", return_value=self.rule)

    def test_absent_contract_is_exact_noop_and_no_catalog_reads(self):
        t = deepcopy(self.top)
        t.pop("main_completion")
        t["physical_doors"][0].pop("requires_completion")
        with patch.object(
            completion,
            "_native_rule",
            side_effect=AssertionError("Unexpected native I/O"),
        ):
            self.assertEqual(completion.blocked_cells(t, completed=False), frozenset())
            self.assertEqual(completion.packets(t, completed=True), ())

    def test_flag_without_contract_and_malformed_flag_fail_closed(self):
        t = deepcopy(self.top)
        t.pop("main_completion")
        with self.assertRaisesRegex(ValueError, "source-bound"):
            completion.blocked_cells(t, completed=False)
        t["physical_doors"][0]["requires_completion"] = 1
        with self.assertRaisesRegex(ValueError, "Malformed"):
            completion.blocked_cells(t, completed=False)
        with self.assertRaisesRegex(ValueError, "Malformed"):
            physical.packets(t, map_id=10, instance_id=1, unlocked_room=2)

    def test_terminal_frontier_alone_does_not_open_completion_terrain(self):
        with self.native(), self.requirement():
            self.assertEqual(
                physical.blocked_cells(self.top, 2), frozenset({(2, 0, 0), (3, 0, 0)})
            )
            self.assertEqual(
                physical.blocked_cells(self.top, 2, completed=True), frozenset()
            )
            p = dict(
                start_position=dict(x=1, y=0, z=0),
                end_position=dict(x=3, y=0, z=0),
                steps=[dict(dx=1, dy=0, dz=0)] * 2,
            )
            with self.assertRaises(ValueError):
                physical.validate_movement(self.top, p, unlocked_room=2)
            self.assertEqual(
                physical.validate_movement(
                    self.top, p, unlocked_room=2, completed=True
                ),
                (3, 0, 0),
            )

    def test_completed_status_with_nonterminal_frontier_fails_closed(self):
        with self.native(), self.requirement(), self.assertRaisesRegex(
            ValueError, "terminal room frontier"
        ):
            physical.blocked_cells(self.top, 1, completed=True)

    def test_single_native_column_projects_closed_door_without_changing_object(self):
        t = deepcopy(self.top)
        t.pop("main_completion")
        t["physical_doors"][0].pop("requires_completion")
        t["physical_doors"][0]["position"] = [2, 0, 7]
        before = deepcopy(t)
        with self.native():
            self.assertEqual(physical.blocked_cells(t, 1), frozenset({(2, 0, 0)}))
        self.assertEqual(t, before)

    def test_rotation_pending_blocks_even_first_stage_gate_before_native_projection(
        self,
    ):
        t = deepcopy(self.top)
        t.pop("main_completion")
        door = t["physical_doors"][0]
        door.pop("requires_completion")
        door.update(destination_room=1, position=[2, 0, 7])
        t["_rotation_pending"] = True
        existing = {50}
        with self.native():
            self.assertEqual(
                physical.blocked_cells(t, 1, blocked_source_ids=existing),
                frozenset({(2, 0, 0)}),
            )
        self.assertEqual(existing, {50})
        t["_rotation_pending"] = False
        with self.native():
            self.assertEqual(physical.blocked_cells(t, 1), frozenset())

    def test_multiple_physical_rows_keep_literal_xyz_even_for_nonfloor_through_row(
        self,
    ):
        t = deepcopy(self.top)
        t.pop("main_completion")
        t["physical_doors"][0].pop("requires_completion")
        t["physical_doors"][0]["position"] = [2, 0, 7]
        with self.native(multiple=True):
            self.assertEqual(physical.blocked_cells(t, 1), frozenset({(2, 0, 7)}))

    def test_postboss_entry_view_never_substitutes_for_main_completion(self):
        t = deepcopy(self.top)
        t.update(_entry_main_completed=True, entry_path_policy={"fixture": True})
        with self.native(), self.requirement():
            self.assertEqual(
                physical.blocked_cells(t, 2, completed=False),
                frozenset({(2, 0, 0), (3, 0, 0)}),
            )

    def test_rotation_packet_recipient_is_forwarded_through_public_wrapper(self):
        t = deepcopy(self.top)
        t.pop("main_completion")
        t["physical_doors"][0].pop("requires_completion")
        t["rotation_choice"] = {"fixture": True}
        module = ModuleType("wakfu_server.dungeon_excavation_runtime")
        module.flow_packets = Mock(return_value=((777, b"rotation"),))
        with patch.object(
            wakfu_server, "dungeon_excavation_runtime", module, create=True
        ):
            result = flow.packets(
                t, map_id=10, instance_id=1, unlocked_room=1, recipient_character_id=77
            )
        self.assertEqual(result, ((777, b"rotation"),))
        module.flow_packets.assert_called_once_with(
            t,
            map_id=10,
            instance_id=1,
            unlocked_room=1,
            completed=False,
            recipient_character_id=77,
        )

    def test_postboss_entry_paths_preserve_existing_136_opening_contract(self):
        t = deepcopy(self.top)
        t.pop("main_completion")
        t["physical_doors"][0].pop("requires_completion")
        t["physical_doors"][0].update(source_room=2, destination_room=3)
        t.update(entry_path_policy={"fixture": True}, _entry_main_completed=True)
        module = ModuleType("wakfu_server.dungeon_entry_paths")
        module.accessible_postboss_orders = Mock(return_value={3})
        with patch.dict(sys.modules, {"wakfu_server.dungeon_entry_paths": module}):
            self.assertFalse(
                physical._opened(t, t["physical_doors"][0], 2, completed=False)
            )
            self.assertTrue(
                physical._opened(t, t["physical_doors"][0], 2, completed=True)
            )
            with self.native():
                self.assertEqual(physical.blocked_cells(t, 2), frozenset())

    def test_presentation_is_idempotent_and_does_not_mutate_progress(self):
        before = deepcopy(self.top)
        with self.native(), self.requirement():
            self.assertEqual(completion.packets(self.top, completed=False), ())
            packet = completion.packets(self.top, completed=True)
            self.assertEqual(packet, completion.packets(self.top, completed=True))
        self.assertEqual(self.top, before)
        self.assertEqual(packet[0][0], 13411)
        self.assertEqual(struct.unpack(">BiiBq", packet[0][1]), (0, 30, 20, 1, -1))

    def test_extra_terrain_cannot_become_a_spawn_arena(self):
        self.top["rooms"][1]["cells"].append([2, 0, 0])
        with self.native(), self.requirement(), self.assertRaisesRegex(
            ValueError, "noncombat"
        ):
            completion.require_rule(self.top)

    def test_scope_gate_and_owner_mutations_reject(self):
        for mutate in (
            lambda t: t.update(asset_map_id=11),
            lambda t: t["physical_doors"][0].update(position=[3, 0, 0]),
            lambda t: t["physical_doors"][0].update(destination_room=1),
        ):
            t = deepcopy(self.top)
            mutate(t)
            with self.native(), self.requirement(), self.assertRaises(ValueError):
                completion.require_rule(t)

    def test_presentation_parameters_are_native_signed_longs(self):
        for values in ([True], [1 << 63], [-(1 << 63) - 1], ["-1"], [0] * 128):
            with self.assertRaises(ValueError):
                completion.presentation_packet(
                    dict(scenario_id=20, event_id=30, parameters=values)
                )


if __name__ == "__main__":
    unittest.main()
