"""Exercise the real World BenKO adapter at its domain boundary."""

import ast
from contextlib import contextmanager
from pathlib import Path
import struct
import unittest
from unittest.mock import MagicMock, Mock, patch


def extracted_adapter(bindings):
    source = Path(__file__).resolve().parents[1] / "local_game_server.py"
    tree = ast.parse(source.read_text())
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "resurrect_world_character"
    )

    class Scope(ast.NodeTransformer):
        def visit_Nonlocal(self, item):
            return ast.copy_location(ast.Global(names=item.names), item)

    module = ast.fix_missing_locations(
        ast.Module(body=[Scope().visit(node)], type_ignores=[])
    )
    exec(compile(module, str(source), "exec"), bindings)
    return bindings["resurrect_world_character"]


class ObservedLock:
    def __init__(self):
        self.depth = 0

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, *_):
        self.depth -= 1


class WorldResurrectionAdapterTests(unittest.TestCase):
    def bindings(self, *, target_id=41, target_account=2, target_leader_id=40):
        character = dict(
            id=40,
            account_id=2,
            map_id=546,
            instance_id=9,
            x=12,
            y=13,
            z=0,
            direction=3,
            hp=400,
        )
        target_leader = dict(
            id=target_leader_id,
            account_id=target_account,
            map_id=546,
            instance_id=9,
            x=12,
            y=13,
            z=0,
        )
        world_lock = ObservedLock()
        world = Mock()
        world.lock = world_lock
        world.players = {40: ("source-lease", object(), character)}
        if target_leader_id != 40:
            world.players[target_leader_id] = ("target-lease", object(), target_leader)
        store = Mock()
        store.connection.return_value = MagicMock()
        connection = store.connection.return_value
        db = connection.__enter__.return_value
        db.execute.return_value.fetchone.return_value = {
            "account_id": target_account,
            "leader_id": target_leader_id,
        }
        store.now.return_value = 1
        position_barriers = []

        @contextmanager
        def barrier(owner, *, blocking):
            position_barriers.append((owner, blocking))
            yield

        positions = Mock()
        positions.account_barrier.side_effect = barrier
        send = Mock()
        result = dict(
            donor={"id": 40, "hp": 400},
            donor_packets=[(12470, b"debit")],
            target={
                "id": target_id,
                "account_id": target_account,
                "map_id": 546,
                "instance_id": 9,
                "x": 12,
                "y": 13,
                "z": 0,
                "hp": 1,
            },
            target_packets=[(12436, b"hp-one")],
            world_packets=[(12088, b"alive")],
        )
        domain = Mock(return_value=result)
        bindings = dict(
            character=character,
            account_id=2,
            generation="source-lease",
            position={"x": 14, "y": 13, "z": -1},
            fight=None,
            combat_session=None,
            STORE=store,
            POSITIONS=positions,
            WORLD=world,
            connection=object(),
            service=3,
            send=send,
            refresh_owned_character=lambda value: dict(value),
            record=Mock(),
            struct=struct,
        )
        return bindings, domain, position_barriers, world_lock, result

    def install_domain(self, domain):
        return patch("wakfu_server.world_resurrection.resurrect", domain)

    def test_active_hero_target_uses_selected_main_and_source_private_position(self):
        b, domain, barriers, lock, result = self.bindings(target_id=41)
        with self.install_domain(domain):
            extracted_adapter(b)(struct.pack(">q", 41))
        self.assertEqual(1, domain.call_count)
        live = domain.call_args.kwargs["live_locations"]
        self.assertEqual(
            {"x": 14, "y": 13, "z": -1}, {key: live[40][key] for key in ("x", "y", "z")}
        )
        self.assertEqual(
            (546, 9, "source-lease"),
            (live[40]["map_id"], live[40]["instance_id"], live[40]["generation"]),
        )
        # The hero id maps to its selected main's live location, under the
        # main connection generation; the domain still targets hero 41.
        self.assertEqual((40, "source-lease"), (live[41]["id"], live[41]["generation"]))
        self.assertEqual([(2, False)], barriers)
        self.assertEqual(
            0, lock.depth, "database domain call must run outside WORLD.lock"
        )
        self.assertEqual([12470], [call.args[2] for call in b["send"].call_args_list])
        b["WORLD"].send_to.assert_called_once_with(40, "source-lease", 12436, b"hp-one")
        b["WORLD"].broadcast.assert_called_once_with(
            "source-lease", 40, 12088, b"alive"
        )

    def test_self_resurrection_updates_the_selected_world_character_to_one_hp(self):
        b, domain, barriers, lock, _result = self.bindings(target_id=40)
        with self.install_domain(domain):
            extracted_adapter(b)(struct.pack(">q", 40))
        self.assertEqual(1, b["character"]["hp"])
        self.assertEqual([(2, False)], barriers)
        self.assertEqual(0, lock.depth)
        b["send"].assert_called_once_with(b["connection"], 3, 12470, b"debit")
        b["WORLD"].send_to.assert_called_once_with(40, "source-lease", 12436, b"hp-one")
        b["WORLD"].update.assert_called_once_with(
            "source-lease", b["character"], 12088, b"alive"
        )

    def test_cross_account_barriers_are_sorted_and_target_disconnect_skips_delivery(
        self,
    ):
        b, domain, barriers, lock, result = self.bindings(
            target_id=51, target_account=8, target_leader_id=50
        )

        # Simulate the target disconnecting after the committed SQL operation.
        def commit_then_disconnect(*_args, **_kwargs):
            b["WORLD"].players.pop(50)
            return result

        domain.side_effect = commit_then_disconnect
        with self.install_domain(domain):
            extracted_adapter(b)(struct.pack(">q", 51))
        self.assertEqual(
            1, domain.call_count, "the source is debited in one committed call"
        )
        self.assertEqual([(2, False), (8, False)], barriers)
        self.assertEqual(0, lock.depth)
        self.assertEqual([12470], [call.args[2] for call in b["send"].call_args_list])
        b["WORLD"].send_to.assert_not_called()
        b["WORLD"].broadcast.assert_not_called()
        b["WORLD"].update.assert_not_called()

    def test_stale_world_target_is_rejected_before_domain_or_debit(self):
        b, domain, barriers, _lock, _ = self.bindings(
            target_id=51, target_account=8, target_leader_id=50
        )
        b["WORLD"].players.pop(50)
        with self.install_domain(domain):
            with self.assertRaisesRegex(ValueError, "left the world"):
                extracted_adapter(b)(struct.pack(">q", 51))
        domain.assert_not_called()
        self.assertEqual([(2, False), (8, False)], barriers)
        b["send"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
