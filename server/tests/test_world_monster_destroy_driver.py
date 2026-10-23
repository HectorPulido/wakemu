"""Execute the actual World cnT closure without importing its network loop."""
import ast
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import Mock, patch

from psycopg import DatabaseError
from psycopg_pool import PoolTimeout
from wakfu_server import combat_terrain, ecology_feedback
from wakfu_server.objectives import environmental_monster_destroy as destroy
from wakfu_server.objectives import environmental_destroy_publication as publication
from wakfu_server.objectives import environmental_gameplay as gameplay
from wakfu_server.objectives import environmental_archmonster_runtime as archmonsters
from wakfu_server.planting_location import owned_character
from wakfu_server.world import World


class WorldMonsterDestroyDriverTests(unittest.TestCase):
    def test_actual_owned_route_commits_before_publication_replays_without_credit_and_keeps_npc_fallback(
        self,
    ):
        path = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(path.read_text())
        recovery = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "publish_native_monster_destructions"
        )
        polling = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "poll_environmental_events"
        )
        helper = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "try_native_monster_destroy"
        )
        routes = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and isinstance(n.test, ast.BoolOp)
            and any(
                isinstance(c, ast.Call)
                and isinstance(c.func, ast.Name)
                and c.func.id == helper.name
                for c in ast.walk(n.test)
            )
        ]
        self.assertEqual(len(routes), 1)
        owned_route = routes[0]
        self.assertEqual(len(owned_route.orelse), 1)
        fallback = owned_route.orelse[0]
        self.assertIsInstance(fallback, ast.If)
        # Execute both exact production routing predicates. Replacing their
        # network-loop bodies with labels observes routing without inventing a
        # dialogue acceptance, reward, service, or client packet producer.
        route = ast.parse('def route(opcode, body, loaded):\n    return "other"').body[
            0
        ]
        route.body = [
            ast.If(
                test=deepcopy(owned_route.test),
                body=[ast.Return(ast.Constant("owned"))],
                orelse=[
                    ast.If(
                        test=deepcopy(fallback.test),
                        body=[ast.Return(ast.Constant("legacy"))],
                        orelse=[ast.Return(ast.Constant("other"))],
                    )
                ],
            )
        ]
        stored = dict(
            id=7, account_id=8, map_id=327, instance_id=0, x=0, y=0, z=0, direction=0
        )
        live = dict(stored, x=9)
        buffered = dict(stored, x=10, direction=2)
        world = World(lambda _: b"", lambda _: b"", lambda *_: True)
        world.join("owned-generation", object(), live)
        positions = SimpleNamespace(merge=Mock(return_value=buffered))
        registry = SimpleNamespace(lock=RLock())
        state = dict(
            transaction=False,
            owned=True,
            replay=False,
            failure=False,
            blocked=False,
            publish_failure=None,
        )
        events = []

        def execute(sql, parameters):
            self.assertTrue(registry.lock._is_owned())
            self.assertTrue(state["transaction"])
            self.assertIn("environmental_owned_group_members", sql)
            self.assertEqual(parameters, (327, 0, -9001))
            events.append("lookup")
            return SimpleNamespace(
                fetchone=lambda: dict(owned=True) if state["owned"] else None
            )

        db = SimpleNamespace(execute=execute)

        @contextmanager
        def connection():
            self.assertTrue(registry.lock._is_owned())
            self.assertFalse(state["transaction"])
            state["transaction"] = True
            events.append("begin")
            try:
                yield db
            except Exception:
                events.append("rollback")
                raise
            else:
                events.append("commit")
            finally:
                state["transaction"] = False

        store = SimpleNamespace(
            connection=connection,
            now=lambda: datetime(2026, 10, 22, tzinfo=timezone.utc),
        )

        def commit(
            backend, transaction, account_id, generation, character, body, **kwargs
        ):
            self.assertIs(backend, store)
            self.assertIs(transaction, db)
            self.assertTrue(registry.lock._is_owned())
            self.assertTrue(state["transaction"])
            self.assertEqual(
                (account_id, generation, character["x"]), (8, "owned-generation", 10)
            )
            self.assertEqual(struct.unpack(">qq", body), (-9001, 265))
            self.assertIs(kwargs["groups"], registry)
            self.assertTrue(kwargs["loaded"])
            self.assertIs(kwargs["blocked"], state["blocked"])
            self.assertEqual(kwargs["location_context"](stored)["x"], 10)
            self.assertTrue(kwargs["reachable"](character, dict(x=11, y=0, z=0)))
            self.assertFalse(kwargs["reachable"](character, dict(x=100, y=0, z=0)))
            events.append("native-action")
            if state["failure"] or state["blocked"]:
                raise ValueError("native action refused")
            return dict(
                replayed=state["replay"],
                map_id=327,
                instance_id=0,
                character_id=7,
                monster_id=-9001,
                action_id=265,
            )

        def contribute(transaction, receipt):
            self.assertIs(transaction, db)
            self.assertTrue(registry.lock._is_owned())
            self.assertTrue(state["transaction"])
            self.assertFalse(receipt["replayed"])
            events.append("contribute")

        def publish(*args, **kwargs):
            self.assertFalse(registry.lock._is_owned())
            self.assertFalse(state["transaction"])
            self.assertEqual(args, (store, world, registry))
            self.assertEqual((kwargs["map_id"], kwargs["instance_id"]), (327, 0))
            events.append("publish")
            if state["publish_failure"] == "oserror":
                raise OSError("socket disappeared after commit")
            return 0 if state["publish_failure"] == "false" else 1

        sent = []
        namespace = dict(
            struct=struct,
            character=stored,
            WORLD=world,
            POSITIONS=positions,
            STORE=store,
            COMBAT_GROUPS=registry,
            account_id=8,
            generation="owned-generation",
            loaded=True,
            fight=None,
            combat_session=None,
            spectator_session=None,
            hero_switch_pending=None,
            bag_session=None,
            ranch_session=None,
            owned_planting_character=owned_character,
            poll_environmental_events=lambda: events.append("poll"),
            record=Mock(),
            send=lambda *args: sent.append(args[-2:]),
            connection=object(),
            service=object(),
            DatabaseError=DatabaseError,
            PoolTimeout=PoolTimeout,
        )
        poll_wrapper = ast.parse(
            """
def make_poll(character):
    environmental_poll_at = 0
    environmental_publication_error = None
"""
        ).body[0]
        poll_wrapper.body.append(deepcopy(polling))
        poll_wrapper.body.append(
            ast.Return(ast.Name(id="poll_environmental_events", ctx=ast.Load()))
        )
        monotonic = [1.0]
        namespace.update(
            time=SimpleNamespace(monotonic=lambda: monotonic[0]),
            environmental_events=SimpleNamespace(
                refresh=lambda *args, **kwargs: events.append("refresh"),
                claimed_character=None,
            ),
            flush_positions=Mock(),
        )
        module = ast.fix_missing_locations(
            ast.Module(
                body=[deepcopy(recovery), deepcopy(helper), route, poll_wrapper],
                type_ignores=[],
            )
        )
        exec(compile(module, str(path), "exec"), namespace)
        body = struct.pack(">qq", -9001, 265)
        with patch.object(
            combat_terrain,
            "map_geometry",
            return_value=dict(edges=[((10, 0, 0), (11, 0, 0))]),
        ), patch.object(
            destroy, "commit", side_effect=commit
        ) as committed, patch.object(
            gameplay, "committed_monster_destroy", side_effect=contribute
        ) as credited, patch.object(
            publication, "publish", side_effect=publish
        ) as published, patch.object(
            ecology_feedback, "information", return_value=(674, b"refused")
        ), patch.object(
            archmonsters, "poll", return_value=()
        ):
            self.assertEqual(namespace["route"](13222, body, True), "owned")
            self.assertEqual(
                events,
                [
                    "begin",
                    "lookup",
                    "native-action",
                    "contribute",
                    "commit",
                    "publish",
                    "poll",
                ],
            )
            events.clear()
            state["replay"] = True
            self.assertEqual(namespace["route"](13222, body, True), "owned")
            self.assertEqual(
                events,
                ["begin", "lookup", "native-action", "commit", "publish", "poll"],
            )
            self.assertEqual(credited.call_count, 1)
            self.assertEqual(published.call_count, 2)
            # A rejected owned action remains handled; it cannot fall through
            # to a legacy NPC choice after a rollback.
            events.clear()
            state["failure"] = True
            self.assertEqual(namespace["route"](13222, body, True), "owned")
            self.assertEqual(events, ["begin", "lookup", "native-action", "rollback"])
            self.assertEqual(sent, [(674, b"refused")])
            self.assertEqual(published.call_count, 2)
            state.update(failure=False, owned=False)
            events.clear()
            self.assertEqual(namespace["route"](13222, body, True), "legacy")
            self.assertEqual(events, ["begin", "lookup", "commit"])
            self.assertEqual(committed.call_count, 3)
            self.assertEqual(
                namespace["route"](12058, b"legacy choice", True), "legacy"
            )
            self.assertEqual(namespace["route"](13222, b"short", True), "legacy")
            self.assertEqual(namespace["route"](13222, body, False), "other")
            self.assertEqual(namespace["route"](999, body, True), "other")
            self.assertEqual(committed.call_count, 3)
            self.assertEqual(sent, [(674, b"refused")])
            state.update(owned=True, blocked=True)
            for scene in (
                "fight",
                "combat_session",
                "spectator_session",
                "hero_switch_pending",
                "bag_session",
                "ranch_session",
            ):
                with self.subTest(blocked_scene=scene):
                    namespace[scene] = object()
                    events.clear()
                    self.assertEqual(namespace["route"](13222, body, True), "owned")
                    self.assertEqual(
                        events, ["begin", "lookup", "native-action", "rollback"]
                    )
                    namespace[scene] = None
            self.assertEqual(credited.call_count, 1)
            self.assertEqual(published.call_count, 2)
            # The source recovery poll reuses the committed outbox after a
            # failed require-all send or an actual socket OSError. It performs
            # no new action/credit/SQL transaction before retry publication.
            state.update(blocked=False, replay=True)
            actual_poll = namespace["make_poll"](stored)
            for failure in ("false", "oserror"):
                with self.subTest(post_commit_publication=failure):
                    events.clear()
                    state["publish_failure"] = failure
                    before_credit = credited.call_count
                    before_send = len(sent)
                    self.assertEqual(namespace["route"](13222, body, True), "owned")
                    self.assertEqual(
                        events,
                        [
                            "begin",
                            "lookup",
                            "native-action",
                            "commit",
                            "publish",
                            "poll",
                        ],
                    )
                    self.assertEqual(credited.call_count, before_credit)
                    self.assertEqual(len(sent), before_send)
                    state["publish_failure"] = None
                    events.clear()
                    before_actions = committed.call_count
                    monotonic[0] += 2
                    actual_poll()
                    self.assertEqual(events, ["publish", "refresh"])
                    self.assertEqual(committed.call_count, before_actions)
                    self.assertEqual(credited.call_count, before_credit)
                    events.clear()
                    actual_poll()
                    self.assertEqual(events, [])
            namespace["record"].assert_any_call(
                event="environmental_monster_destroy_publication_pending",
                map_id=327,
                instance_id=0,
                reason="OSError",
            )
