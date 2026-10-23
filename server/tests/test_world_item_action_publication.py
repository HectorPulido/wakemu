"""Exercise the actual World adapters after committed inventory operations."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import time
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch


def adapter(name, bindings):
    source = Path(__file__).resolve().parents[1] / "local_game_server.py"
    tree = ast.parse(source.read_text())
    node = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name
    )

    class Scope(ast.NodeTransformer):
        def visit_Nonlocal(self, item):
            return ast.copy_location(ast.Global(names=item.names), item)

    module = ast.fix_missing_locations(
        ast.Module(body=[Scope().visit(node)], type_ignores=[])
    )
    exec(compile(module, str(source), "exec"), bindings)
    return bindings[name]


class WorldItemActionPublicationTests(unittest.TestCase):
    def bindings(self):
        character = dict(
            id=40,
            account_id=2,
            map_id=546,
            instance_id=0,
            x=12,
            y=13,
            z=0,
            direction=3,
            hp=471,
        )
        return dict(
            character=character,
            account_id=2,
            generation="lease",
            fight=None,
            combat_session=None,
            connection=object(),
            service=3,
            selected=True,
            loaded=True,
            movement_state=object(),
            hero_switch_pending=None,
            chest_opening=None,
            guild_chest_session=None,
            bag_session=None,
            ranch_session=None,
            STORE=Mock(),
            WORLD=Mock(),
            POSITIONS=Mock(),
            HARVESTS=Mock(pending={}),
            PLANTINGS=Mock(pending={}),
            COMBAT_SESSIONS=Mock(),
            send=Mock(),
            record=Mock(),
            refresh_owned_character=lambda value: dict(value),
            active_private_session=lambda: None,
            flush_positions=Mock(),
            struct=struct,
            time=time,
        )

    def test_visual_script_commits_before_one_scene_broadcast_without_actor_reset(self):
        b = self.bindings()
        events = []
        b["STORE"].connection.return_value.__enter__ = Mock()
        b["STORE"].connection.return_value.__exit__ = Mock(return_value=False)
        db = b["STORE"].connection.return_value.__enter__.return_value
        db.execute.return_value.fetchone.return_value = {"character_id": 40}
        b["WORLD"].ecology_snapshot.return_value = [b["character"]]
        b["COMBAT_SESSIONS"].lookup_character.return_value = None
        b["COMBAT_GROUPS"] = Mock()
        b["COMBAT_GROUPS"].available.return_value = []
        result = dict(
            character=dict(b["character"], x=-99),
            packets=[(12470, b"debit")],
            script_packet=(13270, b"visual"),
            script_id=7593,
            consumed=1,
        )

        def commit(*args, **kwargs):
            self.assertEqual(kwargs["location"]["x"], 12)
            self.assertTrue(kwargs["target_present"])
            events.append("commit")
            return result

        b["send"].side_effect = lambda *_: events.append("debit")
        b["WORLD"].emit_location.side_effect = lambda *_: events.append("visual")
        with patch(
            "wakfu_server.script_item_actions.action_class", return_value="bIa"
        ), patch("wakfu_server.script_item_actions.use", side_effect=commit):
            self.assertTrue(
                adapter("play_inventory_script", b)(struct.pack(">iqB", 7593, 7, 0))
            )
        self.assertEqual(events, ["commit", "debit", "visual"])
        self.assertEqual(b["character"]["x"], 12)
        b["WORLD"].emit_location.assert_called_once_with(546, 0, 13270, b"visual")
        b["WORLD"].update.assert_not_called()

    def test_visual_script_target_excludes_other_scene_and_fighting_monsters(self):
        b = self.bindings()
        b["STORE"].connection.return_value.__enter__ = Mock()
        b["STORE"].connection.return_value.__exit__ = Mock(return_value=False)
        db = b["STORE"].connection.return_value.__enter__.return_value
        db.execute.return_value.fetchone.return_value = {"character_id": 40}
        b["WORLD"].ecology_snapshot.return_value = [dict(b["character"], instance_id=9)]
        b["COMBAT_GROUPS"] = Mock()
        b["COMBAT_GROUPS"].available.return_value = []
        body = struct.pack(">iqBiih", 7593, 7, 1, 12, 13, 0)
        with patch(
            "wakfu_server.script_item_actions.action_class", return_value="bIa"
        ), patch(
            "wakfu_server.script_item_actions.use", side_effect=ValueError("No target")
        ) as use:
            with self.assertRaisesRegex(ValueError, "No target"):
                adapter("play_inventory_script", b)(body)
        self.assertFalse(use.call_args.kwargs["target_present"])
        self.assertEqual(use.call_args.kwargs["location"]["id"], 40)
        b["send"].assert_not_called()
        b["WORLD"].emit_location.assert_not_called()

    def test_feeding_publishes_partial_pet_and_characteristics_without_actor_reset(
        self,
    ):
        b = self.bindings()
        b.update(
            opcode=12767,
            body=b"feed",
            send_batch=Mock(),
            mount_snapshot=lambda _: [],
            publish_consumable_character=Mock(),
        )
        result = dict(
            character=dict(b["character"], x=-99, y=-99),
            packets=[],
            applied=True,
            replayed=False,
            xp_delta=100,
            health_delta=0,
        )
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "opcode == 12767 and loaded"
        )
        module = ast.fix_missing_locations(ast.Module(body=node.body, type_ignores=[]))
        with patch(
            "wakfu_server.mount_feeding_dispatch.prepare", return_value=result
        ), patch(
            "wakfu_server.mount_publication.pet_packet", return_value=(13046, b"pet29")
        ), patch(
            "wakfu_server.wire.refresh_player",
            side_effect=AssertionError("actor reset"),
        ):
            exec(compile(module, str(source), "exec"), b)
        self.assertEqual((b["character"]["x"], b["character"]["y"]), (12, 13))
        b["WORLD"].update.assert_called_once_with(
            "lease", b["character"], 13046, b"pet29"
        )
        b["publish_consumable_character"].assert_called_once_with(b["character"])

    def test_mission_xp_delta_precedes_absolute_progression_and_refreshes_selected_actor_in_place(
        self,
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        nodes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "simple_item_result is not None"
        ]
        self.assertEqual(len(nodes), 1)
        branch = deepcopy(nodes[0])
        branch.orelse = []
        module = ast.fix_missing_locations(
            ast.Module(
                body=[
                    ast.For(
                        target=ast.Name(id="iteration", ctx=ast.Store()),
                        iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                        body=[branch],
                        orelse=[],
                    )
                ],
                type_ignores=[],
            )
        )

        b = self.bindings()
        live = dict(b["character"])
        persisted = dict(
            live,
            x=-100,
            y=-200,
            z=7,
            map_id=999,
            instance_id=55,
            direction=0,
            xp=200_000_000,
        )
        b.update(
            simple_item_result={
                "character": persisted,
                "packets": [(13879, b"mission-objective")],
                "consumed": 15,
                "xp_changed": True,
            },
            simple_class="bIn",
            PLAYER_TEMPLATE=object(),
            COMBAT_TEST_WP=6,
            wire=Mock(),
            refresh_owned_character=lambda row: dict(row),
            position={"x": 12, "y": 13, "z": 0},
            send=Mock(),
            publish_consumable_character=Mock(),
            record=Mock(),
        )
        b["wire"].refresh_player.return_value = (13046, b"current-character-state")
        b["WORLD"].update = Mock()
        progression_character = {}
        from wakfu_server import combat_lifecycle

        with patch(
            "wakfu_server.combat_lifecycle.outside_progression",
            side_effect=lambda character, wp: (
                progression_character.update(character)
                or (13912, b"absolute-progression")
            ),
        ) as outside:
            exec(compile(module, str(source), "exec"), b)

        outside.assert_called_once()
        self.assertEqual(outside.call_args.args[0]["id"], live["id"])
        self.assertEqual(
            (
                progression_character["x"],
                progression_character["y"],
                progression_character["z"],
                progression_character["map_id"],
                progression_character["instance_id"],
                progression_character["direction"],
            ),
            (12, 13, 0, 546, 0, 3),
        )
        self.assertEqual(
            [call.args[2:] for call in b["send"].call_args_list],
            [(13879, b"mission-objective"), (13912, b"absolute-progression")],
        )
        b["WORLD"].update.assert_called_once_with(
            "lease", b["character"], 13046, b"current-character-state"
        )
        b["publish_consumable_character"].assert_called_once_with(b["character"])
        self.assertEqual(
            (
                b["character"]["x"],
                b["character"]["y"],
                b["character"]["map_id"],
                b["character"]["instance_id"],
            ),
            (12, 13, 546, 0),
        )

    def test_due_pet_wake_publishes_partial_state_preserving_buffered_location(self):
        b = self.bindings()
        b.update(pet_hibernation_due=0.0, publish_consumable_character=Mock())
        b["STORE"].connection.return_value.__enter__ = Mock()
        b["STORE"].connection.return_value.__exit__ = Mock(return_value=False)
        db = b["STORE"].connection.return_value.__enter__.return_value
        db.execute.return_value.fetchall.return_value = []
        result = dict(
            changed=True,
            character=dict(b["character"], x=-99, hp=434),
            packets=[(12470, b"replace"), (13494, b"inventory")],
            next_deadline_ms=None,
        )
        with patch("wakfu_server.pet_hibernation.refresh", return_value=result), patch(
            "wakfu_server.mount_publication.pet_packet", return_value=(13046, b"awake")
        ), patch(
            "wakfu_server.wire.refresh_player",
            side_effect=AssertionError("actor reset"),
        ):
            adapter("refresh_pet_hibernation", b)()
        self.assertEqual((b["character"]["x"], b["character"]["hp"]), (12, 434))
        b["WORLD"].update.assert_called_once_with(
            "lease", b["character"], 13046, b"awake"
        )
        b["publish_consumable_character"].assert_called_once_with(b["character"])
        self.assertGreater(b["pet_hibernation_due"], time.monotonic())

    def test_phoenix_binding_persists_without_actor_reset_or_stale_world_replacement(
        self,
    ):
        import threading

        b = self.bindings()
        b.update(
            position={
                "map_id": 546,
                "instance_id": 0,
                "x": 12,
                "y": 13,
                "z": 0,
                "direction": 3,
            },
            spectator_session=None,
        )
        b["WORLD"].lock = threading.RLock()
        stale = ("older-generation", object(), dict(b["character"], hp=1))
        b["WORLD"].players = {40: stale}
        persisted = dict(
            b["character"],
            saved_phoenix_id=31682,
            x=-50,
            y=-50,
            map_id=99,
            instance_id=42,
            direction=7,
        )
        result = dict(
            character=persisted, saved_phoenix_id=31682, applied=True, packets=[]
        )
        with patch(
            "wakfu_server.phoenix_points.activate", return_value=result
        ) as activate, patch(
            "wakfu_server.wire.refresh_player",
            side_effect=AssertionError("actor reset"),
        ):
            adapter("activate_world_phoenix", b)(struct.pack(">qHH", 31682, 0, 0))
        self.assertEqual(
            (12, 13, 0, 546, 0, 3),
            tuple(
                b["character"][key]
                for key in ("x", "y", "z", "map_id", "instance_id", "direction")
            ),
        )
        activate.assert_called_once()
        self.assertEqual(
            b["position"],
            {key: activate.call_args.kwargs["location"][key] for key in b["position"]},
        )
        self.assertIs(stale, b["WORLD"].players[40])
        b["WORLD"].update.assert_not_called()
        b["send"].assert_not_called()
        b["record"].assert_called_once_with(
            event="phoenix_bound", actor_id=40, phoenix_id=31682, changed=True
        )

    def test_world_snapshot_replays_regional_icon_alongside_food_without_mutating_actor(
        self,
    ):
        from wakfu_server import territory_bonus_wire

        character = dict(
            id=40,
            territory_state_id=1915,
            consumable_states=[{"uid": 91, "state_id": 981}],
        )
        bindings = dict(
            STORE=object(),
            mount_snapshot=lambda *_: (),
            consumable_state_packets=lambda _: food,
        )
        function = adapter("world_state_packets", bindings)
        food = ((12613, b"food-state"),)
        with patch("wakfu_server.mount_publication.snapshot", return_value=()), patch(
            "wakfu_server.personal_ecology.snapshot", return_value=()
        ), patch("wakfu_server.characters.emotes.retained", return_value=()), patch(
            "wakfu_server.consumable_buff_wire.snapshot", return_value=food
        ), patch(
            "wakfu_server.world_resurrection.snapshot", return_value=()
        ), patch(
            "wakfu_server.territory_bonus_wire.snapshot",
            wraps=territory_bonus_wire.snapshot,
        ) as regional:
            packets = function(character)
        regional.assert_called_once_with(40, 1915)
        self.assertEqual(food[0], packets[0])
        self.assertTrue(any(opcode == 12613 for opcode, _ in packets[1:]))
        self.assertEqual([{"uid": 91, "state_id": 981}], character["consumable_states"])

    def test_account_item_spell_grant_publishes_once_without_actor_refresh(self):
        b = self.bindings()
        b["connection"] = SimpleNamespace(
            write_lock=threading.RLock(), item_spell_uids=set()
        )
        uid = (40 << 32) | 5623
        packet = (12503, struct.pack(">qiqh", 40, 5623, uid, 130))
        remember = adapter("publish_item_spell_updates", dict(struct=struct))
        b["send"].side_effect = lambda connection, service, opcode, payload: remember(
            connection, "world", opcode, payload
        )
        with patch(
            "wakfu_server.item_spell_publication.account_inventory_packets",
            return_value=[packet],
        ):
            publish = adapter("publish_account_item_spells", b)
            publish()
            publish()
        b["send"].assert_called_once_with(b["connection"], 3, *packet)
        self.assertIn(uid, b["connection"].item_spell_uids)
        b["WORLD"].update.assert_not_called()
        b["send"].reset_mock()
        with patch(
            "wakfu_server.item_spell_publication.account_inventory_packets",
            return_value=[packet],
        ):
            publish(seed=True)
            publish()
        b["send"].assert_not_called()

    def test_nation_publication_replays_selected_main_state_without_scene_or_sql_reset(
        self,
    ):
        b = self.bindings()
        b.update(
            position={"x": 12, "y": 13, "z": 0},
            wire=Mock(),
            fixture=Mock(return_value=b"captured-main"),
            consumable_state_packets=Mock(return_value=[(13494, b"quest-state")]),
            guild_company_packet=Mock(return_value=(22601, b"company")),
        )
        persisted = dict(
            b["character"],
            x=-90,
            y=-91,
            z=4,
            map_id=999,
            instance_id=888,
            direction=7,
            nation_id=0,
            guild_native={"guildId": 0, "blazon": 0, "level": 0, "name": ""},
        )
        remote = (22599, b"remote-main")
        publish = adapter("publish_nation_character", b)
        with patch(
            "wakfu_server.characters.nation_state.nation_id", return_value=0
        ), patch(
            "wakfu_server.characters.nation_state.synchro", return_value=bytes(27)
        ), patch(
            "wakfu_server.characters.guild_wire.remote_actor_update",
            return_value=remote,
        ):
            first = publish(persisted)
            second = publish(persisted)
        self.assertEqual(
            (12, 13, 0, 546, 0, 3),
            (
                first["x"],
                first["y"],
                first["z"],
                first["map_id"],
                first["instance_id"],
                first["direction"],
            ),
        )
        self.assertIs(second, b["character"])
        self.assertEqual(6, b["send"].call_count)
        self.assertEqual(
            [15548, 13494, 22601, 15548, 13494, 22601],
            [call.args[2] for call in b["send"].call_args_list],
        )
        b["wire"].adapt.assert_has_calls(
            [
                unittest.mock.call(15548, b"captured-main", 2, second),
                unittest.mock.call(15548, b"captured-main", 2, second),
            ]
        )
        b["guild_company_packet"].assert_has_calls(
            [
                unittest.mock.call(second, second["guild_native"]),
                unittest.mock.call(second, second["guild_native"]),
            ]
        )
        b["WORLD"].update.assert_has_calls(
            [
                unittest.mock.call("lease", second, *remote, include_sender=False),
                unittest.mock.call("lease", second, *remote, include_sender=False),
            ]
        )
        b["STORE"].connection.assert_not_called()
        b["WORLD"].broadcast.assert_not_called()

    def test_nation_publication_refreshes_hero_and_broadcasts_to_company_observers(
        self,
    ):
        b = self.bindings()
        b.update(
            position={"x": 12, "y": 13, "z": 0}, OWNED_HERO_TEMPLATE=b"hero-template"
        )
        main_identity = b["character"]
        hero = dict(
            id=41,
            account_id=2,
            map_id=999,
            instance_id=888,
            x=-90,
            y=-91,
            z=4,
            direction=7,
            hp=333,
            nation_id=30,
            guild_native={"guildId": 7, "blazon": 8, "level": 9, "name": "Guild"},
        )
        remote = (22599, b"remote-hero")
        publish = adapter("publish_nation_character", b)
        with patch(
            "wakfu_server.characters.nation_state.nation_id", return_value=30
        ), patch(
            "wakfu_server.characters.nation_state.synchro", return_value=b"n" * 27
        ), patch(
            "wakfu_server.characters.guild_wire.remote_actor_update",
            return_value=remote,
        ), patch(
            "wakfu_server.characters.hero_wire.refresh",
            return_value=(15548, b"hero-refresh"),
        ) as refresh:
            result = publish(hero)
        self.assertEqual(
            (12, 13, 0, 546, 0, 3),
            (
                result["x"],
                result["y"],
                result["z"],
                result["map_id"],
                result["instance_id"],
                result["direction"],
            ),
        )
        self.assertIs(b["character"], main_identity)
        refresh.assert_called_once_with(b"hero-template", result)
        b["send"].assert_called_once_with(b["connection"], 3, 15548, b"hero-refresh")
        b["WORLD"].broadcast.assert_called_once_with(
            "lease", 40, *remote, include_sender=False
        )
        b["WORLD"].update.assert_not_called()
        b["STORE"].connection.assert_not_called()

    def test_test_actor_uses_live_location_and_same_scene_occupancy_then_replay_is_silent(
        self,
    ):
        b = self.bindings()
        from wakfu_server import item_test_spawns

        b.update(
            position={"x": 14, "y": 15, "z": 1}, bag_session=None, ranch_session=None
        )
        lock = threading.RLock()
        b["COMBAT_GROUPS"] = SimpleNamespace(lock=lock)
        b["WORLD"].ecology_snapshot.return_value = [
            dict(id=40, map_id=546, instance_id=0, x=12, y=13, z=0),
            dict(id=51, map_id=546, instance_id=0, x=16, y=17, z=1),
            dict(id=52, map_id=999, instance_id=0, x=90, y=91, z=0),
        ]
        body = struct.pack(">iq", item_test_spawns.ACTION_ID, 88)
        key = (546, 0, 7001)
        applied = dict(applied=True, key=key, world_packets=[(12608, b"spawn-native")])
        replay = dict(applied=False, key=key, world_packets=[])
        events = []

        def use(*args, **kwargs):
            self.assertTrue(lock._is_owned())
            events.append("commit")
            self.assertEqual(b["character"]["x"], 12)
            self.assertEqual(
                (14, 15, 1), tuple(kwargs["location"][key] for key in ("x", "y", "z"))
            )
            self.assertEqual([(12, 13, 0), (16, 17, 1)], kwargs["occupied_cells"])
            return applied if events.count("commit") == 1 else replay

        def emit(*args):
            self.assertTrue(lock._is_owned())
            events.append(("emit", args))

        b["WORLD"].emit_location.side_effect = emit
        before = dict(b["character"])
        with patch.object(item_test_spawns, "use", side_effect=use):
            invoke = adapter("spawn_inventory_test_actor", b)
            self.assertTrue(invoke(body))
            self.assertTrue(invoke(body))
        self.assertEqual(
            ["commit", ("emit", (546, 0, 12608, b"spawn-native")), "commit"], events
        )
        self.assertEqual(before, b["character"])
        b["WORLD"].ecology_snapshot.assert_has_calls(
            [unittest.mock.call(), unittest.mock.call()]
        )
        self.assertEqual(2, b["WORLD"].ecology_snapshot.call_count)
        b["STORE"].connection.assert_not_called()

    def test_test_actor_rejects_private_bag_and_ranch_before_domain_use(self):
        b = self.bindings()
        from wakfu_server import item_test_spawns

        body = struct.pack(">iq", item_test_spawns.ACTION_ID, 88)
        for field in ("bag_session", "ranch_session"):
            with self.subTest(field=field):
                local = self.bindings()
                local.update(bag_session=None, ranch_session=None)
                local[field] = object()
                groups = Mock()
                groups.lock = MagicMock()
                local["COMBAT_GROUPS"] = groups
                with patch.object(item_test_spawns, "use") as use:
                    with self.assertRaisesRegex(ValueError, "ordinary public ground"):
                        adapter("spawn_inventory_test_actor", local)(body)
                use.assert_not_called()
                groups.lock.__enter__.assert_not_called()
                local["WORLD"].ecology_snapshot.assert_not_called()

    def test_item_emote_retains_indefinite_occupation_and_live_position(self):
        b = self.bindings()
        b["COMBAT_SESSIONS"].lookup_character.return_value = None
        persisted = dict(b["character"], x=-99, y=-99)
        result = dict(
            character=persisted,
            packets=[(12470, b"debit")],
            packet=(12088, b"occupation"),
            duration_ms=-1,
        )
        with patch(
            "wakfu_server.emote_item_actions.action_class", return_value="bHY"
        ), patch("wakfu_server.emote_item_actions.play", return_value=result):
            self.assertTrue(adapter("play_inventory_emote", b)(b"request"))
        self.assertEqual((b["character"]["x"], b["character"]["y"]), (12, 13))
        self.assertEqual(b["character"]["_emote_until"], float("inf"))
        self.assertEqual(b["character"]["_emote_packet"], result["packet"])
        b["WORLD"].update.assert_called_once_with(
            "lease", b["character"], *result["packet"]
        )
        b["send"].assert_called_once_with(b["connection"], 3, 12470, b"debit")

    def test_recustomization_clears_selection_after_committed_entitlement(self):
        b = self.bindings()
        events = []
        b["STORE"].clear_character.side_effect = lambda *_: events.append("clear")
        result = dict(
            character=b["character"], packets=[(12470, b"debit")], pending={"mode": 13}
        )

        def commit(*_):
            events.append("commit")
            return result

        with patch(
            "wakfu_server.simple_item_actions._action_classes",
            return_value={5556: {"bIb"}},
        ), patch(
            "wakfu_server.character_recustomization.request", side_effect=commit
        ), patch(
            "wakfu_server.character_recustomization.transition_packets",
            return_value=[(12707, b"mode"), (22797, b"open")],
        ):
            self.assertTrue(
                adapter("open_item_recustomization", b)(struct.pack(">iq", 5556, 7))
            )
        self.assertEqual(events, ["commit", "clear"])
        self.assertFalse(b["selected"])
        self.assertFalse(b["loaded"])
        self.assertIsNone(b["character"])
        self.assertEqual(
            [call.args[2] for call in b["send"].call_args_list], [12470, 12707, 22797]
        )

    def test_item_travel_acknowledges_only_after_native_bootstrap_and_join(self):
        b = self.bindings()
        events = []
        arrived = dict(b["character"], map_id=527, x=0, y=32)
        result = dict(
            character=arrived,
            packets=[(12470, b"debit")],
            transition={"token": "travel"},
            native_class="bIr",
            consumed=1,
        )
        b.update(
            position={"x": 12, "y": 13, "z": 0},
            Movement=lambda value: dict(value),
            owned_native_bootstrap=lambda _: [(13974, b"map")],
            join_world=lambda *_: events.append("join"),
            mark_static_sync_pending=Mock(),
        )
        b[
            "send"
        ].side_effect = lambda _connection, _service, opcode, _body: events.append(
            opcode
        )
        with patch(
            "wakfu_server.item_teleports.action_class", return_value="bIr"
        ), patch("wakfu_server.item_teleports.use", return_value=result), patch(
            "wakfu_server.item_teleports.acknowledge",
            side_effect=lambda *_: events.append("ack"),
        ):
            self.assertTrue(adapter("use_inventory_teleport", b)(b"request"))
        self.assertEqual(events, [12470, 13974, "join", "ack"])
        self.assertEqual(b["position"], {"x": 0, "y": 32, "z": 0})
        self.assertEqual(b["character"]["map_id"], 527)
