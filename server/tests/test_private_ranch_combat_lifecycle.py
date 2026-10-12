"""Private combat keeps its live capability and its durable exterior separate."""
import struct
import ast
from pathlib import Path
import unittest

from postgres_case import PostgresCase
from test_combat_rewards import setup_reward_state
from wakfu_server.combat_lifecycle import prepare_finish, return_to_world
from wakfu_server.combat_rewards import Policy
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_store import create
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import POSITION, RanchSession, destination


class PrivateRanchCombatLifecycleTests(PostgresCase):
    def test_durable_reward_and_health_return_preserve_private_scope_by_projection(
        self,
    ):
        store, account, outside, generation, fight = setup_reward_state(self.store)
        exterior = {key: outside[key] for key in POSITION}
        bag = HavenBagSession(outside)
        ranch = RanchSession(
            bag, bag.inside, destination(35), lease=generation, now_ms=1000000
        )
        live = ranch.move(ranch.inside, dict(x=10, y=11, z=0))
        scope = {key: live[key] for key in POSITION}
        # Actual persistence admits the owned lease without replacing the SQL
        # exterior by the connection's transient private scene.
        fight.id = create(store, account, generation, outside["id"])
        actor = fight.actors[outside["id"]]
        actor.max_hp = outside["max_hp"]
        actor.hp = outside["hp"] - 3
        runtime = RuntimeMessages(fight)
        metadata = {
            live["id"]: dict(
                kind="player",
                account_id=account,
                name=live["name"],
                breed=live["breed"],
                is_male=True,
            ),
            -200: dict(kind="monster", ref=5525),
        }
        done = prepare_finish(
            store,
            account,
            generation,
            live,
            runtime,
            metadata,
            duration_ms=1000,
            fight_instance_id=fight.id,
            policy=Policy(xp=10, kamas=13),
        )
        self.assertEqual({key: done["character"][key] for key in POSITION}, exterior)
        live = ranch.refresh(live, done["character"])
        self.assertEqual({key: live[key] for key in POSITION}, scope)
        self.assertEqual((live["xp"], live["kamas"]), (10, 13))
        result = return_to_world(
            store,
            account,
            generation,
            live,
            runtime,
            struct.pack(">iB", fight.id, 0),
            wp=6,
        )
        live = ranch.refresh(live, result["character"])
        self.assertTrue(ranch.owns(live))
        self.assertEqual({key: live[key] for key in POSITION}, scope)
        self.assertEqual(live["hp"], actor.hp)
        saved = store.character(account, outside["id"])
        self.assertEqual({key: saved[key] for key in POSITION}, exterior)
        self.assertEqual((saved["xp"], saved["kamas"]), (10, 13))
        from wakfu_server.position_buffer import Positions

        positions = Positions(store, lease_active=lambda *args: True)
        with self.assertRaisesRegex(ValueError, "baseline does not match"):
            positions.attach(account, generation, live)
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        attach = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "attach_combat_return_position"
        )
        namespace = dict(
            active_private_session=lambda: ranch,
            ranch_session=ranch,
            character=live,
            generation=generation,
            account_id=account,
            STORE=store,
            POSITIONS=positions,
        )
        exec(
            compile(ast.Module(body=[attach], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        namespace["attach_combat_return_position"]()
        entry = positions.entries[(account, generation, outside["id"])]
        self.assertEqual({key: entry["current"][key] for key in POSITION}, exterior)
        self.assertEqual({key: namespace["character"][key] for key in POSITION}, scope)
        continuation = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If) and "opcode == 12925" in ast.unparse(node.test)
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "attach_combat_return_position"
                for node in ast.walk(continuation)
            )
        )
        bootstrap = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "combat_return_bootstrap"
        )
        from types import SimpleNamespace
        from unittest.mock import patch

        namespace.update(
            fixture=lambda opcode: b"native-template",
            time=SimpleNamespace(time=lambda: 1000),
            owned_native_bootstrap=lambda actor: [(13974, b"public")],
        )
        exec(
            compile(ast.Module(body=[bootstrap], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        with patch(
            "wakfu_server.haven_bag.map_transition", return_value=b"private-map"
        ), patch(
            "wakfu_server.haven_ranch_furniture.snapshot",
            return_value={"packet": (13864, b"hydrated-ranch")},
        ) as snapshot:
            packets = namespace["combat_return_bootstrap"]()
        self.assertEqual(
            [opcode for opcode, body in packets], [13256, 13864, 13974, 12318]
        )
        self.assertEqual(packets[1], (13864, b"hydrated-ranch"))
        self.assertEqual(snapshot.call_args.kwargs["session"], ranch)
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "combat_return_bootstrap"
                for node in ast.walk(continuation)
            )
        )
        # A replacement connection has no transferable private capability;
        # terminal recovery must use the durable exterior without re-awarding.
        from wakfu_server.combat_lifecycle import recover_settled_world

        next_generation = store.begin_session(account)
        replacement = store.select_character(account, next_generation, outside["id"])
        recovered = recover_settled_world(
            store,
            account,
            next_generation,
            replacement,
            fight,
            previous_generation=generation,
            wp=6,
        )
        self.assertEqual(
            {key: recovered["character"][key] for key in POSITION}, exterior
        )
        self.assertEqual(recovered["character"]["kamas"], 13)
        with self.assertRaises(ValueError):
            ranch.validate_lease(next_generation)
        # Leaving the ranch returns to its host bag; leaving the parent then
        # restores the unchanged exterior instead of saving private coords.
        in_bag = ranch.leave(live)
        self.assertTrue(bag.owns(in_bag))
        restored = bag.leave(in_bag)
        self.assertEqual({key: restored[key] for key in POSITION}, exterior)

    def test_abandon_keeps_private_return_and_never_saves_ranch_coordinates(self):
        from test_combat_abandon import setup_abandon_state
        from wakfu_server import combat_abandon

        store, account, generation, outside, fight, runtime = setup_abandon_state(
            self.store
        )
        exterior = {key: outside[key] for key in POSITION}
        bag = HavenBagSession(outside)
        ranch = RanchSession(
            bag, bag.inside, destination(35), lease=generation, now_ms=1000000
        )
        live = ranch.move(ranch.inside, dict(x=12, y=7, z=0))
        scope = {key: live[key] for key in POSITION}
        done = combat_abandon.prepare(store, account, generation, live, runtime, b"")
        live = ranch.refresh(live, done["character"])
        returned = combat_abandon.return_to_world(
            store,
            account,
            generation,
            live,
            runtime,
            struct.pack(">iB", fight.id, 0),
            wp=6,
        )
        live = ranch.refresh(live, returned["character"])
        self.assertTrue(ranch.owns(live))
        self.assertEqual({key: live[key] for key in POSITION}, scope)
        saved = store.character(account, outside["id"])
        self.assertEqual({key: saved[key] for key in POSITION}, exterior)
        self.assertEqual(
            (saved["xp"], saved["kamas"]), (outside["xp"], outside["kamas"])
        )


class PrivateCombatDispatchTests(unittest.TestCase):
    def test_actual_dispatch_merge_validates_capability_and_retains_host_scope(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        helper = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "refresh_owned_character"
        )
        outside = dict(id=10, account_id=2, map_id=527, instance_id=0, x=1, y=2, z=0)
        bag = HavenBagSession(outside)
        ranch = RanchSession(bag, bag.inside, destination(35), lease="lease", now_ms=1)
        live = ranch.move(ranch.inside, dict(x=12, y=7, z=0))
        namespace = dict(
            active_private_session=lambda: ranch,
            ranch_session=ranch,
            character=live,
            generation="lease",
        )
        exec(
            compile(ast.Module(body=[helper], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        merged = namespace["refresh_owned_character"]({**outside, "hp": 17})
        self.assertEqual(
            {key: merged[key] for key in POSITION}, {key: live[key] for key in POSITION}
        )
        self.assertEqual(merged["hp"], 17)
        namespace["generation"] = "stale"
        with self.assertRaises(ValueError):
            namespace["refresh_owned_character"](outside)
        namespace["generation"] = "lease"
        namespace["character"] = {**live, "instance_id": 999}
        with self.assertRaises(ValueError):
            namespace["refresh_owned_character"](outside)
        namespace["active_private_session"] = lambda: None
        self.assertIs(namespace["refresh_owned_character"](outside), outside)
        # Check actual combat SQL merge call sites rather than a copied helper.
        projected = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "character"
            and node.func.attr == "update"
            and node.args
            and isinstance(node.args[0], ast.Call)
            and isinstance(node.args[0].func, ast.Name)
            and node.args[0].func.id == "refresh_owned_character"
        ]
        self.assertGreaterEqual(len(projected), 8)
