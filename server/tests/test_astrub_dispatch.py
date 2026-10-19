"""Exercise the actual console dispatcher with real SQL ownership transitions."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from postgres_case import PostgresCase
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession, destination


class AstrubDispatcherTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("astrub-dispatch", "password")["id"]
        self.saved = self.store.create_character(self.account, "Astrub dispatch")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.saved["id"])

    def dispatcher(self, scene=None, fight=None, combat_session=None):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        function = deepcopy(
            next(
                node
                for node in ast.walk(ast.parse(source.read_text()))
                if isinstance(node, ast.FunctionDef)
                and node.name == "execute_test_command"
            )
        )
        # Production nonlocals are explicit mutable globals in this isolated harness.
        for index, node in enumerate(function.body):
            if isinstance(node, ast.Nonlocal):
                function.body[index] = ast.Global(names=node.names)
        function.decorator_list = []
        bag = HavenBagSession(self.saved) if scene else None
        ranch = (
            RanchSession(
                bag, bag.inside, destination(35), lease=self.generation, now_ms=1
            )
            if scene == "ranch"
            else None
        )
        actor = ranch.inside if ranch else bag.inside if bag else self.saved
        sent = []
        world = Mock()
        exteriors = Mock()
        exteriors.discard.return_value = None
        positions = Mock()
        namespace = dict(
            character=actor,
            position={},
            movement_state=None,
            fight=fight,
            fight_messages=None,
            combat_session=combat_session,
            bag_session=bag,
            ranch_session=ranch,
            account_id=self.account,
            generation=self.generation,
            STORE=self.store,
            COMBAT_TEST=False,
            COMBAT_GROUPS=None,
            WORLD=world,
            POSITIONS=positions,
            HAVEN_BAG_EXTERIORS=exteriors,
            PLANTINGS=Mock(),
            HARVESTS=Mock(),
            connection=object(),
            service="world",
            cancel_flora=Mock(),
            cancel_crafting=Mock(),
            flush_positions=Mock(),
            validate_ranch_lease=Mock(
                side_effect=lambda: ranch.validate_lease(self.generation)
            ),
            Movement=lambda value: dict(value),
            owned_native_bootstrap=Mock(return_value=[(13974, b"public")]),
            owned_haven_leave=Mock(
                return_value=[
                    (13959, b""),
                    (13019, b""),
                    (13256, b""),
                    (13974, b"outside"),
                ]
            ),
            fixture=lambda opcode: b"template",
            join_world=Mock(),
            mark_static_sync_pending=Mock(),
            record=Mock(),
            send=lambda connection, service, opcode, body: sent.append((opcode, body)),
            wire=SimpleNamespace(chat=lambda actor, answer: answer),
        )
        tree = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        exec(compile(tree, str(source), "exec"), namespace)
        return namespace, sent, actor

    def assert_arrival(self, namespace, actor):
        result = namespace["execute_test_command"]("!astrub")
        self.assertIn("message", result)
        expected = dict(map_id=527, instance_id=0, x=0, y=32, z=0)
        stored = self.store.character(self.account, self.saved["id"])
        self.assertEqual({key: stored[key] for key in expected}, expected)
        self.assertEqual(
            {key: namespace["character"][key] for key in expected}, expected
        )
        self.assertIsNone(namespace["bag_session"])
        self.assertIsNone(namespace["ranch_session"])
        namespace["POSITIONS"].attach.assert_called_once_with(
            self.account, self.generation, namespace["character"]
        )
        namespace["POSITIONS"].account_barrier.assert_not_called()
        namespace["join_world"].assert_called_once()

    def test_public_arrival(self):
        namespace, sent, actor = self.dispatcher()
        self.assert_arrival(namespace, actor)
        namespace["owned_native_bootstrap"].assert_called_once()
        namespace["owned_haven_leave"].assert_not_called()
        self.assertNotIn(13019, [opcode for opcode, _ in sent])

    def test_bag_exit_clears_native_bag_controller(self):
        namespace, sent, actor = self.dispatcher("bag")
        self.assertEqual(actor["map_id"], 9)
        self.assert_arrival(namespace, actor)
        self.assertEqual([opcode for opcode, _ in sent].count(13019), 1)
        namespace["HAVEN_BAG_EXTERIORS"].discard.assert_called_once_with(
            self.generation, self.saved["id"]
        )
        namespace["PLANTINGS"].cancel.assert_called_once()
        namespace["HARVESTS"].cancel.assert_called_once()

    def test_ranch_exit_preserves_sql_exterior_baseline_and_avoids_duplicate_leave(
        self,
    ):
        namespace, sent, actor = self.dispatcher("ranch")
        self.assertEqual(actor["map_id"], 1440)
        ranch = namespace["ranch_session"]
        # Real transition_map compares durable SQL location; a live1440 baseline fails.
        self.assert_arrival(namespace, actor)
        self.assertTrue(ranch.closed)
        namespace["validate_ranch_lease"].assert_called_once()
        self.assertNotIn(13019, [opcode for opcode, _ in sent])
        self.assertIn(13256, [opcode for opcode, _ in sent])
        namespace["owned_native_bootstrap"].assert_not_called()

    def test_fight_and_shared_combat_cannot_escape(self):
        for fight, shared in ((object(), None), (None, object())):
            with self.subTest(shared=shared is not None):
                namespace, sent, actor = self.dispatcher("ranch", fight, shared)
                with self.assertRaisesRegex(ValueError, "Termina el combate"):
                    namespace["execute_test_command"]("!astrub")
                self.assertIs(namespace["character"], actor)
                self.assertIsNotNone(namespace["ranch_session"])
                self.assertFalse(namespace["ranch_session"].closed)
                namespace["HAVEN_BAG_EXTERIORS"].discard.assert_not_called()
                namespace["POSITIONS"].attach.assert_not_called()
                self.assertEqual(
                    self.store.character(self.account, self.saved["id"])["map_id"],
                    self.saved["map_id"],
                )
