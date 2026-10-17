"""Execute actual join and ready replay functions against one native scene."""
import ast
from contextlib import ExitStack, nullcontext
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from test_combat_external_markers import sample_shared
from wakfu_server.combat.combat_external_markers import ExternalFightMarkers


class WorldMarkerReadyReplayTests(unittest.TestCase):
    def exercise(self, *, fresh_join):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        nodes = [
            next(
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "Connection"
            )
        ]
        for name in ("join_world", "send_loaded_world_snapshot"):
            node = functions[name]
            node.decorator_list = []
            nodes.append(node)
        character = dict(id=42, account_id=9, map_id=1134, instance_id=0)
        markers = ExternalFightMarkers()
        shared = sample_shared()
        markers.update(shared, now_ms=100000, now_monotonic=100.0)
        packets = []
        profiler = SimpleNamespace(span=lambda *args: nullcontext())
        namespace = dict(
            threading=threading,
            PROFILER=profiler,
            record=lambda **kw: None,
            character=character,
            loaded=True,
            account_id=9,
            generation="lease",
            fight=None,
            combat_session=None,
            COMBAT_TEST=True,
            service="world",
            EXTERNAL_FIGHT_MARKERS=markers,
            STORE=SimpleNamespace(
                connection=lambda: nullcontext(None), current_session=lambda *args: True
            ),
            COMBAT_GROUPS=SimpleNamespace(
                lock=threading.RLock(), available=lambda *args: ()
            ),
            HAVEN_BAG_EXTERIORS=SimpleNamespace(snapshots=lambda *args: ()),
            PLANTINGS=SimpleNamespace(snapshots=lambda *args, **kw: ()),
            HARVESTS=SimpleNamespace(availability_snapshot=lambda *args: ()),
            monster_corpse_snapshot=lambda *args, **kw: (),
            send_planting_context=lambda *args: None,
            sync_static_world=lambda **kw: None,
            refresh_party=lambda *args: None,
            refresh_guild=lambda *args: None,
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        connection = namespace["Connection"](SimpleNamespace(sendall=lambda data: None))
        connection.native_instance_scope = lambda: (9, "lease", 42, 1134, 0)
        namespace["connection"] = connection

        def send(peer, service, opcode, body):
            import struct

            peer.sendall(struct.pack(">IH", len(body) + 6, opcode) + body)
            packets.append((opcode, body))

        namespace["send"] = send
        namespace["send_batch"] = lambda peer, service, rows: [
            send(peer, service, *row) for row in rows
        ]
        namespace["WORLD"] = SimpleNamespace(
            join=lambda *args: True, resynchronize=lambda *args: True
        )
        with ExitStack() as stack:
            overrides = {
                "wakfu_server.profession_store.ensure_all_learned": dict(packets=()),
                "wakfu_server.maps.npc_world.load_scene": (),
                "wakfu_server.maps.npc_placements.load_scene": (),
                "wakfu_server.characters.heroes.ensure_company_party": dict(heroes=()),
                "wakfu_server.characters.hero_wire.company": (674, b"company"),
                "wakfu_server.ecology_admin.admin_removed_packets": (),
                "wakfu_server.combat.combat_world_group_cleanup.defeated_snapshot": (),
            }
            for name, value in overrides.items():
                stack.enter_context(patch(name, return_value=value))
            namespace["join_world"]("lease", connection, character)
            self.assertEqual(sum(opcode == 13753 for opcode, _ in packets), 1)
            namespace["send_loaded_world_snapshot"]()
            namespace["send_loaded_world_snapshot"]()
            self.assertEqual(sum(opcode == 13753 for opcode, _ in packets), 1)
            self.assertEqual(
                connection.marker_publications.snapshot(
                    connection.native_instance_scope()
                ),
                {53: 1},
            )
            shared.fight.phase = "active"
            markers.update(shared, now_ms=101000, now_monotonic=101.0)
            namespace["send_loaded_world_snapshot"]()
            self.assertEqual(sum(opcode == 12233 for opcode, _ in packets), 1)
            if fresh_join:
                namespace["join_world"]("lease", connection, character)
                self.assertEqual(sum(opcode == 13753 for opcode, _ in packets), 2)
                namespace["send_loaded_world_snapshot"]()
                self.assertEqual(sum(opcode == 13753 for opcode, _ in packets), 2)
            else:
                markers.remove(53)
                namespace["send_loaded_world_snapshot"]()
                self.assertEqual(sum(opcode == 12238 for opcode, _ in packets), 1)
                self.assertEqual(
                    connection.marker_publications.snapshot(
                        connection.native_instance_scope()
                    ),
                    {},
                )

    def test_bootstrap_then_ready_replays_once_and_keeps_phase_and_end_updates(self):
        self.exercise(fresh_join=False)

    def test_explicit_fresh_scene_join_resets_cursor_but_ready_does_not(self):
        self.exercise(fresh_join=True)
