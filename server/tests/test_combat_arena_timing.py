"""Arena phase telemetry preserves the selected native result."""
import unittest
from unittest.mock import patch
from wakfu_server import combat_terrain as terrain


class ArenaTimingTests(unittest.TestCase):
    def test_phase_callback_and_profiler_preserve_native_result(self):
        cells = {(0, 0, 0), (1, 0, 0)}
        selected = dict(
            cells=cells, edges=set(), placement={0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        callbacks = []
        with patch.object(
            terrain, "published_geometry", return_value=object()
        ), patch.object(terrain, "bounded_arena", return_value=selected), patch.object(
            terrain, "generate", return_value=selected["placement"]
        ), patch.object(
            terrain, "native_qi_surfaces", return_value=object()
        ), patch.object(
            terrain, "native_surface_indices", return_value={(0, 0): 0}
        ), patch.object(
            terrain, "arena", return_value={"native": "unchanged"}
        ), patch.object(
            terrain, "native_qi_surface_provenance", return_value={}
        ), patch.object(
            terrain.PROFILER, "observe"
        ) as observe:
            result = terrain.local_arena(
                1,
                0,
                (0, 0, 0),
                (1, 0, 0),
                compact=False,
                stage_callback=lambda *args: callbacks.append(args),
            )
        expected = [
            "geometry",
            "selection",
            "placement",
            "surface_catalog",
            "surface_indices",
            "wire",
        ]
        self.assertEqual([row[0] for row in callbacks], expected)
        self.assertEqual(
            [call.args[0] for call in observe.call_args_list],
            ["combat.arena." + name for name in expected],
        )
        self.assertTrue(all(wall >= 0 and cpu >= 0 for _, wall, cpu in callbacks))
        self.assertEqual(result["native"], "unchanged")
        self.assertEqual(result["validated_cells"], cells)
        self.assertEqual(result["placement_cells"], selected["placement"])

    def test_diagnostic_failures_do_not_abort_native_arena(self):
        cells = {(0, 0, 0), (1, 0, 0)}
        placement = {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        selected = dict(cells=cells, edges=set(), placement=placement)
        for fail_profiler, fail_callback in (
            (True, False),
            (False, True),
            (True, True),
        ):
            with self.subTest(
                profiler=fail_profiler, callback=fail_callback
            ), patch.object(
                terrain, "published_geometry", return_value=object()
            ), patch.object(
                terrain, "bounded_arena", return_value=selected
            ), patch.object(
                terrain, "generate", return_value=placement
            ), patch.object(
                terrain, "native_qi_surfaces", return_value=object()
            ), patch.object(
                terrain, "native_surface_indices", return_value={(0, 0): 0}
            ), patch.object(
                terrain, "arena", return_value={"native": "unchanged"}
            ), patch.object(
                terrain, "native_qi_surface_provenance", return_value={}
            ), patch.object(
                terrain.PROFILER,
                "observe",
                side_effect=RuntimeError("profiler unavailable")
                if fail_profiler
                else None,
            ) as observe:
                from unittest.mock import Mock

                callback = Mock(
                    side_effect=RuntimeError("logger unavailable")
                    if fail_callback
                    else None
                )
                result = terrain.local_arena(
                    1, 0, (0, 0, 0), (1, 0, 0), compact=False, stage_callback=callback
                )
                self.assertEqual(result["native"], "unchanged")
                self.assertEqual(result["validated_cells"], cells)
                self.assertEqual(result["placement_cells"], placement)
                self.assertEqual(observe.call_count, 6)
                self.assertEqual(callback.call_count, 6)
