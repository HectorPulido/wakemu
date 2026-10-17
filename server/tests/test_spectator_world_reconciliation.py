"""Preserve native world contexts across spectator leave and reentry."""
import ast
from pathlib import Path
import struct
import unittest
from types import SimpleNamespace

from wakfu_server.combat.combat_external_markers import (
    ExternalFightMarkers,
    MarkerPublications,
)
from wakfu_server.combat.combat_multiplayer_wire import decode_external
from test_combat_external_markers import sample_shared


def frame(opcode, body):
    return struct.pack(">IH", len(body) + 6, opcode) + body


class SpectatorWorldReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.scope = (7, "generation", 42, 1134, 0)
        self.cursor = MarkerPublications()
        self.markers = ExternalFightMarkers()
        self.shared = sample_shared()
        self.markers.update(self.shared, now_ms=100000, now_monotonic=100.0)

    def publish(self, packets):
        self.cursor.after_write(b"".join(frame(*p) for p in packets), self.scope)

    def reconcile(self):
        return self.markers.world_snapshots(
            1134,
            0,
            exclude_character_id=42,
            known_phases=self.cursor.snapshot(self.scope),
        )

    def test_native_leave_preserves_existing_actor_and_context_once(self):
        original = self.markers.world_snapshots(1134, 0)
        self.assertEqual([p[0] for p in original], [12608, 13753])
        decoded = decode_external(original[1][1])
        self.assertEqual(decoded["fight_id"], 53)
        self.assertEqual(decoded["myr"], [17, -201])
        self.publish(original)
        # bvU restores buG before sending cpg/12154; this is no fresh scene.
        self.assertEqual(self.reconcile(), ())
        self.assertEqual(self.reconcile(), ())
        self.assertEqual(self.cursor.snapshot(self.scope), {53: 1})

    def test_missed_phase_new_fight_and_ended_fight_are_reconciled(self):
        self.publish(self.markers.world_snapshots(1134, 0))
        self.shared.fight.phase = "active"
        self.markers.update(self.shared, now_ms=101000, now_monotonic=101.0)
        delta = self.reconcile()
        self.assertEqual(delta, ((12233, struct.pack(">i", 53)),))
        self.publish(delta)
        self.assertEqual(self.reconcile(), ())
        other = sample_shared()
        other.fight.id = 54
        other.group_lease = (other.group_lease[0], other.group_lease[1], 54, 1)
        self.markers.update(other, now_ms=102000, now_monotonic=102.0)
        self.markers.remove(53)
        delta = self.reconcile()
        self.assertEqual([p[0] for p in delta], [12608, 13753, 12238])
        self.assertEqual(decode_external(delta[1][1])["fight_id"], 54)
        self.assertEqual(struct.unpack(">iiiB", delta[2][1]), (53, 1, -1, 1))
        self.publish(delta)
        self.assertEqual(self.cursor.snapshot(self.scope), {54: 1})
        self.assertEqual(self.reconcile(), ())

    def test_scene_and_owner_lease_reset_and_received_removal(self):
        original = self.markers.world_snapshots(1134, 0)
        self.publish(original)
        for scope in ((7, "replacement", 42, 1134, 0), (7, "generation", 42, 1134, 8)):
            self.assertEqual(self.cursor.snapshot(scope), {})
        self.cursor.reset(self.scope)
        self.assertEqual(self.reconcile(), original)
        self.publish(original)
        self.publish((self.markers.remove(53),))
        self.assertEqual(self.reconcile(), ())
        self.assertEqual(self.cursor.snapshot(self.scope), {})

    def test_private_and_participant_filters_remain_authoritative(self):
        self.assertEqual(self.markers.world_snapshots(1134, 9, known_phases={}), ())
        self.assertEqual(
            self.markers.world_snapshots(
                1134, 0, exclude_character_id=17, known_phases={}
            ),
            (),
        )

    def test_failed_actual_connection_write_does_not_claim_publication(self):
        from wakfu_server.performance_profiler import PROFILER
        import threading

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        node = next(
            n
            for n in ast.parse(source.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == "Connection"
        )
        scope = {
            "threading": threading,
            "PROFILER": PROFILER,
            "record": lambda **kw: None,
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                str(source),
                "exec",
            ),
            scope,
        )

        def fail(_data):
            raise OSError("socket closed")

        connection = scope["Connection"](SimpleNamespace(sendall=fail))
        connection.native_instance_scope = lambda: self.scope
        with self.assertRaises(OSError):
            connection.sendall(
                b"".join(frame(*p) for p in self.markers.world_snapshots(1134, 0))
            )
        self.assertEqual(connection.marker_publications.snapshot(self.scope), {})

    def test_successful_actual_connection_batch_tracks_only_marker_lifecycle(self):
        from wakfu_server.performance_profiler import PROFILER
        import threading

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        node = next(
            n
            for n in ast.parse(source.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == "Connection"
        )
        scope = {
            "threading": threading,
            "PROFILER": PROFILER,
            "record": lambda **kw: None,
        }
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                str(source),
                "exec",
            ),
            scope,
        )
        writes = []
        connection = scope["Connection"](SimpleNamespace(sendall=writes.append))
        connection.native_instance_scope = lambda: self.scope
        original = self.markers.world_snapshots(1134, 0)
        data = frame(674, b"unrelated") + b"".join(frame(*p) for p in original)
        connection.sendall(data)
        self.assertEqual(writes, [data])
        self.assertEqual(connection.marker_publications.snapshot(self.scope), {53: 1})
        connection.sendall(frame(12053, b"spectator-timeline"))
        self.assertEqual(connection.marker_publications.snapshot(self.scope), {53: 1})
        connection.sendall(frame(12233, struct.pack(">i", 53)))
        self.assertEqual(connection.marker_publications.snapshot(self.scope), {53: 2})
        connection.sendall(frame(*self.markers.remove(53)))
        self.assertEqual(connection.marker_publications.snapshot(self.scope), {})

    def test_spectator_return_keeps_full_world_refresh_with_marker_reconciliation(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        functions = {
            n.name: n
            for n in ast.walk(ast.parse(source.read_text()))
            if isinstance(n, ast.FunctionDef)
        }
        refresh = functions["refresh_owned_world_after_spectating"]
        call = next(
            n
            for n in ast.walk(refresh)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "send_loaded_world_snapshot"
        )
        self.assertEqual(
            [(k.arg, ast.literal_eval(k.value)) for k in call.keywords],
            [("reconcile_markers", True)],
        )
        calls = {
            n.func.attr
            for n in ast.walk(functions["send_loaded_world_snapshot"])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        self.assertTrue(
            {
                "resynchronize",
                "snapshots",
                "available",
                "availability_snapshot",
                "world_snapshots",
            }
            <= calls
        )
        self.assertNotIn("prepare_delivery", calls)
