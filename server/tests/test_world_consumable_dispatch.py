"""Exercise the actual opcode12659 branch with bounded World dependencies."""
import ast
import json
from copy import deepcopy
from itertools import count
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class WorldConsumableDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse(
            (Path(__file__).parents[1] / "local_game_server.py").read_text()
        )
        branches = [
            node
            for node in ast.walk(source)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "opcode == 12659 and loaded"
        ]
        if len(branches) != 1:
            raise AssertionError("Expected one world 12659 item-use branch")
        dispatch = deepcopy(branches[0])
        dispatch.orelse = []
        module = ast.Module(
            body=[
                ast.For(
                    target=ast.Name(id="iteration", ctx=ast.Store()),
                    iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                    body=[dispatch],
                    orelse=[],
                )
            ],
            type_ignores=[],
        )
        cls.driver = compile(
            ast.fix_missing_locations(module), "<actual-world-12659>", "exec"
        )
        ticks = [
            node
            for node in ast.walk(source)
            if isinstance(node, ast.If)
            and "last_consumable_tick" in ast.unparse(node.test)
            and ">= 5" in ast.unparse(node.test)
        ]
        if len(ticks) != 1:
            raise AssertionError("Expected one bounded World consumable checkpoint")
        tick = deepcopy(ticks[0])
        tick.orelse = []
        tick_module = ast.Module(
            body=[
                ast.For(
                    target=ast.Name(id="iteration", ctx=ast.Store()),
                    iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                    body=[tick],
                    orelse=[],
                )
            ],
            type_ignores=[],
        )
        cls.tick_driver = compile(
            ast.fix_missing_locations(tick_module),
            "<actual-world-consumable-tick>",
            "exec",
        )

    def setup_route(self, *, result=None):
        actor = dict(id=7, hp=80, map_id=12, instance_id=4, direction=3)
        saved = dict(
            id=7,
            hp=80,
            map_id=1,
            instance_id=0,
            direction=0,
            x=1,
            y=2,
            z=0,
            consumable_states=[],
        )
        result = result or dict(
            character=saved,
            previous_character=dict(id=7, consumable_states=[]),
            packets=[(12470, b"consumed")],
            emotes=[],
            native_consumable=True,
        )
        use = Mock(return_value=result)
        send = Mock()
        record = Mock()
        publish = Mock()
        world = SimpleNamespace(broadcast=Mock(), update=Mock())
        bindings = dict(
            opcode=12659,
            loaded=True,
            body=b"request",
            fight=None,
            STORE=object(),
            account_id=3,
            generation="session-a",
            character=actor,
            position={"x": 8, "y": 9, "z": 2},
            connection=object(),
            service="world",
            send=send,
            record=record,
            refresh_owned_character=lambda value: dict(value),
            publish_consumable_character=publish,
            WORLD=world,
            LOCAL_WORLD_ACTIONS=count(1),
            COMBAT_TEST_WP=9,
            PLAYER_TEMPLATE=object(),
            OWNED_HERO_TEMPLATE=object(),
            wire=SimpleNamespace(
                refresh_player=lambda *_: (13912, b"world-refresh"),
                chat=lambda *_: b"error",
            ),
            apply_readiness=Mock(),
            checkpoint_fight=Mock(),
        )
        return bindings, use, send, record, world

    def test_main_use_publishes_with_live_position_and_committed_character(self):
        result = dict(
            character=dict(
                id=7,
                hp=79,
                map_id=1,
                instance_id=0,
                direction=0,
                x=1,
                y=2,
                z=0,
                consumable_states=[{"uid": 1}],
            ),
            previous_character=dict(id=7, consumable_states=[]),
            packets=[(12470, b"consumed")],
            emotes=[],
            native_consumable=True,
        )
        bindings, use, send, record, world = self.setup_route(result=result)
        delta = Mock(return_value=((12613, b"state"), (13420, b"flush")))
        with (
            patch("wakfu_server.inventory_consumable_effects.use", use),
            patch("wakfu_server.consumable_buff_wire.delta", delta),
            patch(
                "wakfu_server.inventory_items.equipment_inventory",
                return_value=(12470, b"inventory"),
            ),
        ):
            exec(self.driver, bindings)

        use.assert_called_once_with(
            bindings["STORE"],
            3,
            "session-a",
            7,
            b"request",
            expected_hp=80,
            in_fight=False,
            native_map_id=12,
        )
        published = delta.call_args.args[1]
        self.assertEqual(
            tuple(
                published[key]
                for key in ("map_id", "instance_id", "direction", "x", "y", "z")
            ),
            (12, 4, 3, 8, 9, 2),
        )
        bindings["publish_consumable_character"].assert_called_once_with(
            bindings["character"]
        )
        world.broadcast.assert_any_call("session-a", 7, 12613, b"state")
        world.broadcast.assert_any_call("session-a", 7, 13420, b"flush")
        self.assertEqual(bindings["character"]["hp"], 79)
        self.assertEqual(record.call_args.kwargs["event"], "inventory_food_used")

    def test_publication_value_error_is_after_commit_and_never_reloads_as_rejection(
        self,
    ):
        bindings, use, _send, record, _world = self.setup_route()
        reload_inventory = Mock(
            side_effect=AssertionError("committed item reloaded as rejected")
        )
        # Inject module dependencies imported locally by the branch.
        with (
            patch("wakfu_server.inventory_consumable_effects.use", use),
            patch("wakfu_server.inventory_move.reload_inventory", reload_inventory),
            patch(
                "wakfu_server.consumable_buff_wire.delta",
                side_effect=ValueError("publication failure"),
            ),
            patch("wakfu_server.combat_lifecycle.outside_progression", return_value=()),
            patch(
                "wakfu_server.inventory_items.equipment_inventory",
                return_value=(12470, b"inventory"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "publication failure"):
                exec(self.driver, bindings)
        reload_inventory.assert_not_called()
        record.assert_not_called()

    def test_periodic_checkpoint_publishes_expiry_and_suppresses_it_during_combat(self):
        before = dict(
            id=7, map_id=12, instance_id=4, hp=80, consumable_states=[{"uid": 1}]
        )
        after = dict(before, consumable_states=[])
        world = SimpleNamespace(broadcast=Mock(), update=Mock())
        send = Mock()
        publish = Mock()
        bindings = dict(
            loaded=True,
            character=before,
            last_consumable_tick=0,
            account_id=3,
            generation="session-a",
            STORE=object(),
            fight=None,
            combat_session=None,
            last_consumable_tick_value=None,
            time=SimpleNamespace(monotonic=lambda: 10.0),
            service="world",
            WORLD=world,
            send=send,
            connection=object(),
            publish_consumable_character=publish,
            LOCAL_WORLD_ACTIONS=count(1),
            COMBAT_TEST_WP=9,
            PLAYER_TEMPLATE=object(),
            wire=SimpleNamespace(refresh_player=lambda *_: (13912, b"world-refresh")),
        )
        synchronize = Mock(return_value=after)
        delta = Mock(return_value=((13560, b"expired"), (13420, b"flush")))
        with (
            patch("wakfu_server.consumable_world_lifecycle.synchronize", synchronize),
            patch("wakfu_server.consumable_buff_wire.delta", delta),
        ):
            exec(self.tick_driver, bindings)
        synchronize.assert_called_once_with(
            bindings["STORE"],
            3,
            "session-a",
            before,
            in_combat=False,
            company_updates=[],
        )
        self.assertEqual(delta.call_args.args[:2], (before, after))
        world.broadcast.assert_any_call("session-a", 7, 13560, b"expired")
        publish.assert_called_once_with(after)

        world.broadcast.reset_mock()
        delta.reset_mock()
        publish.reset_mock()
        world.update.reset_mock()
        bindings.update(character=before, fight=object(), last_consumable_tick=0)
        with (
            patch(
                "wakfu_server.consumable_world_lifecycle.synchronize",
                return_value=after,
            ),
            patch("wakfu_server.consumable_buff_wire.delta", delta),
        ):
            exec(self.tick_driver, bindings)
        delta.assert_not_called()
        publish.assert_not_called()
        world.update.assert_not_called()

    def test_food_publication_keeps_owner_build_and_targets_world_refresh_only(self):
        from tests.test_equipment_stats import EquipmentStatsTests
        from test_aptitude_catalog_coverage import aptitude_sheet
        from wakfu_server.builds import selection_message
        from wakfu_server.consumable_buff_wire import snapshot as state_snapshot
        from wakfu_server.consumable_world_publication import publish
        from wakfu_server.territory_bonuses import world_packet
        from wakfu_server.world import World
        from wakfu_server.wire import proto_field, proto_fields

        class Peer:
            def __init__(self, name):
                self.name = name

            def shutdown(self, _how):
                self.fail("Unexpected socket shutdown")

        sent = []
        owner = EquipmentStatsTests().character()
        catalog_path = (
            Path(__file__).parents[1] / "protocol" / "native-consumable-actions.json"
        )
        catalog = json.loads(catalog_path.read_text())
        food_plan = next(
            row["plan"] for row in catalog["items"] if row["item_ref"] == 3663
        )
        food_state = dict(food_plan["states"][0], uid=9_001, remaining_ms=600_000)
        owner.update(
            account_id=21,
            active_build_index=0,
            map_id=1134,
            instance_id=7,
            x=3,
            y=4,
            z=0,
            direction=3,
            consumable_states=[food_state],
        )
        owner["builds"][0].update(
            sheet=b"".join(
                proto_field(tag, value)
                for tag, value in (
                    (8, 0),
                    (18, b"Saved equipment"),
                    (24, 6),
                    (56, 0),
                )
            ).hex(),
            deck="",
            aptitudes=aptitude_sheet([(36, 1)]).hex(),
        )
        observer = dict(id=2, account_id=22, map_id=1134, instance_id=7, x=4, y=4, z=0)
        foreign_instance = dict(
            id=3, account_id=23, map_id=1134, instance_id=8, x=4, y=4, z=0
        )

        def deliver(peer, opcode, body):
            sent.append((peer.name, opcode, body))

        world = World(
            lambda character: ("spawn", character["id"]),
            lambda character_id: ("remove", character_id),
            deliver,
            state_packets=lambda _character: (),
            refresh_state_packets=lambda _character: self.fail(
                "format-39 refresh must not replay food state"
            ),
        )
        owner_peer = Peer("owner")
        world.join("owner-generation", owner_peer, owner)
        world.join("observer-generation", Peer("observer"), observer)
        world.join("other-generation", Peer("other-instance"), foreign_instance)
        sent.clear()

        expected_snapshot = world_packet(owner)
        expected_selection = selection_message(owner)
        publish(
            world,
            "owner-generation",
            owner,
            send=lambda opcode, body: world.send_to(
                owner["id"], "owner-generation", opcode, body
            ),
        )

        owner_packets = [
            (opcode, body) for peer, opcode, body in sent if peer == "owner"
        ]
        observer_packets = [
            (opcode, body) for peer, opcode, body in sent if peer == "observer"
        ]
        other_packets = [
            (opcode, body) for peer, opcode, body in sent if peer == "other-instance"
        ]
        self.assertEqual(
            owner_packets,
            [expected_snapshot, expected_selection, expected_snapshot],
        )
        self.assertEqual(observer_packets, [expected_snapshot])
        self.assertEqual(other_packets, [])
        self.assertEqual(
            [opcode for opcode, _ in owner_packets],
            [expected_snapshot[0], expected_selection[0], expected_snapshot[0]],
        )
        self.assertEqual(world.players[owner["id"]][2]["builds"], owner["builds"])
        self.assertEqual(
            world.players[owner["id"]][2]["consumable_states"],
            owner["consumable_states"],
        )
        self.assertEqual(world.players[owner["id"]][2]["active_build_index"], 0)
        food_packets = state_snapshot(owner)
        self.assertEqual([opcode for opcode, _ in food_packets], [12613, 12613, 13420])
        child = food_packets[1][1]
        fight, _action, _parent, execute, effect_class, size = struct.unpack_from(
            ">iiiBih", child
        )
        self.assertEqual((fight, execute, effect_class), (-1, 0, 122))
        child_fields = dict(proto_fields(child[19 : 19 + size]))
        self.assertEqual(child_fields[4 << 3], 0)
        additional = dict(proto_fields(child_fields[8 << 3 | 2]))
        self.assertEqual(additional[12 << 3], 21)
        self.assertEqual(additional[25 << 3], 0)


if __name__ == "__main__":
    unittest.main()
