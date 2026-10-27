"""Exercise actual World owner/peer callbacks and native regional deltas."""
import ast
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


class RegionalWorldReplayTests(unittest.TestCase):
    def test_real_world_owner_resync_transitions_and_fresh_transport(self):
        from wakfu_server.world import World
        from wakfu_server import territory_bonuses, ecology_context
        from wakfu_server import personal_ecology, world_resurrection
        from wakfu_server.characters import emotes
        from wakfu_server.combat_effect_removal import _identity_fields

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        events = []
        namespace = dict(
            World=World,
            STORE=MagicMock(),
            OPEN_PLANTING=False,
            mount_snapshot=lambda c: ((900, b"mount"),),
            consumable_state_packets=lambda c: ((901, b"food"),),
            send=lambda peer, service, opcode, body: events.append(
                (peer, opcode, body)
            ),
            send_batch=lambda peer, service, packets: events.extend(
                (peer, *p) for p in packets
            ),
            send_native_planting_bonus=lambda *a: None,
            REGIONAL_BONUSES=SimpleNamespace(mark_context_refreshed=lambda c: None),
            record=lambda **kw: None,
            PLAYER_TEMPLATE=None,
            wire=SimpleNamespace(
                spawn_player=lambda template, c: c["id"], remove_player=lambda i: i
            ),
        )
        for name in ("world_state_packets", "send_planting_context"):
            node = next(
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == name
            )
            exec(
                compile(
                    ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                    str(source),
                    "exec",
                ),
                namespace,
            )
        assignment = next(
            n
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "WORLD" for t in n.targets)
        )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=[assignment], type_ignores=[])
                ),
                str(source),
                "exec",
            ),
            namespace,
        )
        world = namespace["WORLD"]
        # The actual join/resync entry source must preserve publication markers.
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "pop"
            ):
                self.assertFalse(
                    node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "_published_territory_state_id"
                )

        character = dict(
            id=40, account_id=4, map_id=527, instance_id=0, x=1, y=2, z=0, hp=123
        )
        peer = object()
        regional = {"state": 1917, "bonuses": {33: -10, 36: -10}}

        def attached(c):
            return dict(
                c,
                territory_state_id=regional["state"],
                territory_stat_bonuses=dict(regional["bonuses"]),
            )

        def publish(c=character, p=peer):
            namespace["send_planting_context"](p, c, include_weather=False)

        def native_rows(p):
            rows = []
            for recipient, opcode, body in events:
                if recipient is not p or opcode not in (12613, 13560):
                    continue
                offset = 13 if opcode == 12613 else 12
                generic, length = struct.unpack_from(">ih", body, offset)
                payload = body[offset + 6 : offset + 6 + length]
                fields = _identity_fields(payload)
                self.assertEqual(struct.unpack_from(">i", body)[0], -1)
                rows.append((opcode, generic, fields[1], fields.get(7)))
            return rows

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(personal_ecology, "snapshot", return_value=())
            )
            stack.enter_context(patch.object(emotes, "retained", return_value=()))
            stack.enter_context(
                patch.object(world_resurrection, "snapshot", return_value=())
            )
            stack.enter_context(
                patch.object(
                    ecology_context, "packet", return_value=(12789, b"ecology")
                )
            )
            stack.enter_context(
                patch.object(
                    territory_bonuses,
                    "attach_character",
                    side_effect=lambda db, c: attached(c),
                )
            )
            stack.enter_context(
                patch.object(
                    territory_bonuses,
                    "reconcile_owned",
                    side_effect=lambda store, account, gen, c: attached(c),
                )
            )
            stack.enter_context(
                patch.object(
                    territory_bonuses,
                    "world_packets",
                    return_value=((13046, b"stats"),),
                )
            )
            publish()
            world.join("g", peer, character)
            self.assertEqual([r[0] for r in native_rows(peer)], [12613] * 5)
            initial_uids = {r[2] for r in native_rows(peer)}
            self.assertEqual(len(initial_uids), 5)
            self.assertEqual(sum(r[1] == 310 for r in native_rows(peer)), 1)
            events.clear()
            for _ in range(3):
                world.resynchronize("g", peer, character)
                publish()
            self.assertEqual(native_rows(peer), [])
            self.assertEqual(character["hp"], 123)
            self.assertEqual(character["territory_stat_bonuses"], regional["bonuses"])

            other_peer = object()
            other = dict(character, id=41, account_id=5)
            events.clear()
            world.join("other", other_peer, other)
            self.assertEqual(
                len(native_rows(other_peer)), 5
            )  # Original actor replay to observer.
            self.assertTrue(all(r[3] == 40 for r in native_rows(other_peer)))
            events.clear()
            world.leave(41, "other")
            for state, expected in (
                (1915, [13560] * 5 + [12613] * 5),
                (1917, [13560] * 5 + [12613] * 5),
                (None, [13560] * 5),
            ):
                events.clear()
                regional.update(
                    state=state, bonuses={} if state is None else {33: 30, 36: 30}
                )
                publish()
                self.assertEqual([r[0] for r in native_rows(peer)], expected)
                events.clear()
                publish()
                world.resynchronize("g", peer, character)
                self.assertEqual(native_rows(peer), [])

            regional.update(state=1917, bonuses={33: -10, 36: -10})
            fresh = deepcopy(character)
            fresh.pop("_published_territory_state_id")
            fresh.pop("_published_territory_stat_bonuses")
            new_peer = object()
            events.clear()
            publish(fresh, new_peer)
            world.join("new-generation", new_peer, fresh)
            self.assertEqual([r[0] for r in native_rows(new_peer)], [12613] * 5)
            self.assertEqual({r[2] for r in native_rows(new_peer)}, initial_uids)
            self.assertEqual(fresh["hp"], 123)
