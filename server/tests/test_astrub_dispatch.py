"""Exercise the actual console dispatcher with real SQL ownership transitions."""
import ast
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import time

from postgres_case import PostgresCase
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession, destination
from wakfu_server.ecology_admin_jobs import COMMANDS as ASYNC_ECOLOGY_COMMANDS
from wakfu_server.combat_shared import Registry
import test_combat_admin_recovery as recovery_fixture


class AstrubDispatcherTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("astrub-dispatch", "password")["id"]
        self.saved = self.store.create_character(self.account, "Astrub dispatch")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.saved["id"])

    def dispatcher(
        self, scene=None, fight=None, combat_session=None, *, complete=False
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        source_tree = ast.parse(source.read_text())
        extra_helpers = (
            {"complete_test_fight", "refresh_shared_combat", "attach_command_combat"}
            if complete
            else set()
        )
        helpers = [
            deepcopy(node)
            for node in ast.walk(source_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name
            in (
                {
                    "deferred_native_combat_attachment",
                    "submit_ecology_admin_command",
                    "ecology_admin_coordination",
                    "deliver_rift_transition",
                    "emergency_exit_current_combat",
                    "recover_aborted_publication_cohort",
                }
                | extra_helpers
            )
        ]
        self.assertEqual(len(helpers), 6 + len(extra_helpers))
        function = deepcopy(
            next(
                node
                for node in ast.walk(source_tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "execute_test_command"
            )
        )
        # Production nonlocals are explicit mutable globals in this isolated harness.
        for extracted in (*helpers, function):
            extracted.decorator_list = []
            for index, node in enumerate(extracted.body):
                if isinstance(node, ast.Nonlocal):
                    extracted.body[index] = ast.Global(names=node.names)
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
            COMBAT_SESSIONS=SimpleNamespace(
                lookup_character=lambda unused: None,
                registry=Registry(lambda unused: True),
            ),
            CHECKPOINT_WRITER=SimpleNamespace(flush_fight=lambda *args, **kwargs: True),
            publication_recovery_shared=None,
            publication_recovery_attempt_token=None,
            publication_recovery_notice_token=None,
            checkpoint_id=None,
            checkpoint_revision=None,
            checkpoint_terminal=False,
            pending_terminal_world_recovery=None,
            TEST_MONSTERS=(),
            TEST_MONSTERS_BY_ID={},
            TEST_GROUP_KEY=None,
            fight_started_at=None,
            placement_deadline=Mock(),
            refresh_owned_character=lambda saved: saved,
            attach_combat_return_position=Mock(),
            EXTERNAL_FIGHT_MARKERS=SimpleNamespace(remove=lambda unused: None),
            publish_full_abandon_group=Mock(),
            loaded=True,
            contextmanager=contextmanager,
            ASYNC_ECOLOGY_COMMANDS=ASYNC_ECOLOGY_COMMANDS,
            COMBAT_GROUPS=None,
            time=time,
            COMBAT_TEST_WP=None,
            DUNGEON_ROOM_RUNTIME_AVAILABLE=False,
            custom_task_cards=Mock(),
            drain_shared_combat=Mock(),
            checkpoint_fight=Mock(),
            information=lambda answer: (674, answer),
            send_batch=lambda *args: None,
            combat_return_bootstrap=lambda: (),
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
        tree = ast.fix_missing_locations(
            ast.Module(body=[*helpers, function], type_ignores=[])
        )
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
        created = self.store.create_character(
            self.account, "After Actual Astrub", selection_generation=self.generation
        )
        selected = self.store.select_character(
            self.account, self.generation, created["id"]
        )
        self.assertEqual(selected["id"], created["id"])
        self.assertTrue(
            self.store.current_character_session(
                self.account, self.generation, created["id"]
            )
        )

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

    def test_live_rift_escape_uses_real_cancellation_and_allows_repeated_astrub(self):
        fixture = recovery_fixture.CombatAdminRecoveryTests.fixture(self)
        self.account, self.generation, identity = fixture["owners"][0]
        self.saved = self.store.character(self.account, identity)
        shared = fixture["shared"]
        shared.fight.phase = "active"
        shared.fight.winner = None
        namespace, sent, actor = self.dispatcher(
            fight=shared.fight, combat_session=fixture["sessions"][0]
        )
        namespace["fight_messages"] = shared.runtime
        namespace["COMBAT_SESSIONS"] = SimpleNamespace(
            lookup_character=fixture["registry"].lookup_character,
            registry=fixture["registry"],
        )
        namespace["POSITIONS"] = fixture["positions"]
        result = namespace["execute_test_command"]("!astrub")
        self.assertIn("message", result)
        self.assertIsNone(namespace["fight"])
        self.assertIsNone(namespace["combat_session"])
        self.assertFalse(fixture["registry"].fights)
        self.assertEqual(
            (namespace["character"]["map_id"], namespace["character"]["instance_id"]),
            (527, 0),
        )
        for member in (identity, *fixture["heroes"]):
            saved = self.store.character(self.account, member)
            self.assertEqual((saved["map_id"], saved["instance_id"]), (527, 0))
            self.assertEqual(saved["hp"], fixture["expected"][member])
        namespace["execute_test_command"]("!astrub")
        generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, generation, fixture["heroes"][0])
        created = self.store.create_character(self.account, "After Escape")
        self.assertGreater(created["id"], 0)
