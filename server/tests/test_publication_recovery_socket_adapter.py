"""Actual socket recovery helpers preserve paused owners and restore world state."""
import ast
import struct
import threading
from copy import copy, deepcopy
import symtable
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from psycopg import DatabaseError
from psycopg_pool import PoolTimeout
import test_party_publication_staged_recovery as staged_fixtures
from test_native_recovery_instance_publication_hooks import frames
from wakfu_server.combat_instance_publication_recovery import (
    publication_recovery_waiting,
)
from wakfu_server.movement import Movement
from wakfu_server.position_buffer import Positions, PositionOwnerBusy
from wakfu_server.world import World


HELPERS = (
    "recover_aborted_publication_cohort",
    "continue_aborted_publication_recovery",
    "attempt_shared_combat_attachment",
    "abort_waiting_publication_cohort",
    "consume_command_combat_recovery",
    "command_recovery_holds_request",
    "attach_command_combat",
    "finish_aborted_native_return",
    "complete_aborted_native_return",
    "deferred_native_combat_attachment",
)


def native_return_adapter(*, connection=False):
    source = Path(__file__).parents[1] / "local_game_server.py"
    names = {"AbortedNativeReturn", "written_fight_id"}
    if connection:
        names.add("Connection")
    nodes = [
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
    ]
    namespace = dict(
        threading=threading,
        PROFILER=SimpleNamespace(span=lambda _: nullcontext()),
        record=Mock(),
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            str(source),
            "exec",
        ),
        namespace,
    )
    return namespace


def extracted_helpers(namespace, state, *, omit_entry_information=False):
    adapters = native_return_adapter()
    namespace.update(
        {name: adapters[name] for name in ("AbortedNativeReturn", "written_fight_id")}
    )
    source = Path(__file__).parents[1] / "local_game_server.py"
    text = source.read_text()
    tree = ast.parse(text)
    session_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )
    session_symbols = next(
        child
        for child in symtable.symtable(text, str(source), "exec").get_children()
        if child.get_name() == "session"
    )
    for argument in (
        *session_node.args.posonlyargs,
        *session_node.args.args,
        *session_node.args.kwonlyargs,
    ):
        namespace.setdefault(argument.arg, None)
    imports = []
    for node in session_node.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            break
        if (
            omit_entry_information
            and isinstance(node, ast.ImportFrom)
            and node.module == "wakfu_server.ecology_feedback"
            and any(alias.name == "information" for alias in node.names)
        ):
            continue
        imports.append(deepcopy(node))
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in HELPERS
    ]
    # Exercise the actual receiver's gate order, not just its terminal handler.
    # A continue means this one frame was consumed before opcode dispatch.
    receiver = next(
        node
        for node in ast.walk(session_node)
        if isinstance(node, ast.While)
        and any(
            isinstance(stmt, ast.If)
            and isinstance(stmt.test, ast.Call)
            and isinstance(stmt.test.func, ast.Name)
            and stmt.test.func.id == "command_recovery_holds_request"
            for stmt in node.body
        )
    )
    gate_index = next(
        index
        for index, stmt in enumerate(receiver.body)
        if isinstance(stmt, ast.If)
        and isinstance(stmt.test, ast.Call)
        and isinstance(stmt.test.func, ast.Name)
        and stmt.test.func.id == "command_recovery_holds_request"
    )
    gates = deepcopy(receiver.body[gate_index : gate_index + 3])

    class SingleFrame(ast.NodeTransformer):
        def visit_Continue(self, node):
            return ast.copy_location(ast.Return(ast.Constant("held")), node)

    gates = [SingleFrame().visit(node) for node in gates]
    handler = next(
        node
        for node in ast.walk(receiver)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.BoolOp)
        and any(
            isinstance(value, ast.Name) and value.id == "aborted_native_return"
            for value in ast.walk(node.test)
        )
        and any(
            isinstance(value, ast.Constant) and value.value == 12925
            for value in ast.walk(node.test)
        )
        and any(
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "finish_aborted_native_return"
            for stmt in node.body
            for value in ast.walk(stmt)
        )
    )
    handler = deepcopy(handler)
    handler.orelse = []
    handler.body.append(ast.Return(ast.Constant("dispatched")))
    pipeline = ast.FunctionDef(
        name="receiver_native_return",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg("opcode"), ast.arg("body")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=gates + [handler, ast.Return(ast.Constant("unhandled"))],
        decorator_list=[],
    )
    functions.append(pipeline)
    names = sorted(
        {
            name
            for function in functions
            for node in ast.walk(function)
            if isinstance(node, ast.Nonlocal)
            for name in node.names
        }
    )
    bindings = [
        ast.Assign(
            [ast.Name(name, ast.Store())],
            ast.Subscript(
                ast.Name("initial", ast.Load()), ast.Constant(name), ast.Load()
            ),
        )
        for name in names
    ]
    # Preserve the original session's local/cell classification. Reachable
    # dependencies are explicit fixture seams, except information: its real
    # session-entry import must initialize the actual closure cell.
    dependencies = [
        ast.Assign(
            [ast.Name(name, ast.Store())],
            ast.Subscript(
                ast.Name("_fixture_dependencies", ast.Load()),
                ast.Constant(name),
                ast.Load(),
            ),
        )
        for name in session_symbols.get_locals()
        if name in namespace and name not in names and name != "information"
    ]
    getter = ast.FunctionDef(
        name="state",
        args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=[
            ast.Return(
                ast.Dict(
                    keys=[ast.Constant(name) for name in names],
                    values=[ast.Name(name, ast.Load()) for name in names],
                )
            )
        ],
        decorator_list=[],
    )
    setter = ast.FunctionDef(
        name="set_state",
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=ast.arg("changes"),
            defaults=[],
        ),
        body=[ast.Nonlocal(names)]
        + [
            ast.Assign(
                [ast.Name(name, ast.Store())],
                ast.Call(
                    ast.Attribute(ast.Name("changes", ast.Load()), "get", ast.Load()),
                    [ast.Constant(name), ast.Name(name, ast.Load())],
                    [],
                ),
            )
            for name in names
        ],
        decorator_list=[],
    )
    factory = ast.FunctionDef(
        name="factory",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg("initial"), ast.arg("_fixture_dependencies")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=imports
        + dependencies
        + bindings
        + functions
        + [
            getter,
            setter,
            ast.Return(
                ast.Dict(
                    keys=[
                        ast.Constant(name)
                        for name in (
                            *HELPERS,
                            "receiver_native_return",
                            "state",
                            "set_state",
                        )
                    ],
                    values=[
                        ast.Name(name, ast.Load())
                        for name in (
                            *HELPERS,
                            "receiver_native_return",
                            "state",
                            "set_state",
                        )
                    ],
                )
            ),
        ],
        decorator_list=[],
    )
    # Unreachable execution, but the compiler sees every original conditional
    # import and nested binding. A missing entry import therefore reproduces
    # the real unbound free cell instead of falling back to a global fixture.
    factory.body.append(ast.If(ast.Constant(False), deepcopy(session_node.body), []))
    module = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["factory"]({name: state.get(name) for name in names}, namespace)


class TranslationStore:
    """Translate the position adapter's SQL boundary without replacing Positions."""

    def __init__(self, character):
        self.saved = dict(character)
        self.busy = False

    def character(self, account, identity, db=None):
        if self.busy:
            raise PositionOwnerBusy("Position owner is busy; retry checkpoint")
        return dict(self.saved)

    def now(self):
        return 0

    def current_character_session(self, account, generation, identity):
        return identity == self.saved["id"] and account == self.saved["account_id"]

    @contextmanager
    def connection(self, **kwargs):
        yield self

    def execute(self, statement, params=None):
        return self

    def fetchone(self):
        return {"character_id": self.saved["id"]}


class PublicationRecoverySocketAdapterTests(unittest.TestCase):
    def harness(
        self,
        fixture,
        owner,
        source,
        *,
        adopt=None,
        shared=None,
        omit_entry_information=False
    ):
        shared = shared or fixture.shared
        character = dict(
            id=owner.character_id,
            account_id=owner.account_id,
            map_id=527,
            instance_id=0,
            x=5,
            y=6,
            z=0,
            direction=2,
            hp=41,
        )
        store = TranslationStore(character)
        positions = Positions(store, lease_active=lambda *args: True)
        world = World(lambda row: b"spawn", lambda row: b"remove", lambda *args: None)
        world.join(
            owner.generation,
            "peer-" + str(owner.account_id),
            dict(character, map_id=1134),
        )
        observed = dict(sends=[], events=[], adopt=[], bootstrap=[], sync=[])
        clock = SimpleNamespace(value=100.0)
        connection = SimpleNamespace(instance_publications=source[0])
        initial = dict(
            character=dict(character, map_id=1134),
            fight=shared.fight,
            fight_messages=shared.runtime,
            combat_session=owner,
            group_lease=object(),
            checkpoint_id=99,
            checkpoint_revision=7,
            checkpoint_terminal=False,
            pending_terminal_world_recovery={"pending": True},
            publication_recovery_shared=shared,
            publication_recovery_attempt_token=None,
            publication_recovery_notice_token=None,
            publication_recovery_attempt_due=0.0,
            publication_recovery_return_due=0.0,
            aborted_native_return=None,
            position={"x": 0, "y": 0, "z": 0},
            movement_state=None,
            TEST_MONSTERS=(1,),
            TEST_MONSTERS_BY_ID={1: 1},
            TEST_GROUP_KEY=1,
            fight_started_at=1.0,
        )
        functions = None

        def adoption():
            observed["adopt"].append(clock.value)
            return adopt() if adopt is not None else False

        def deferred():
            return shared if publication_recovery_waiting(shared) else None

        def attach():
            current = functions["state"]()["character"]
            return positions.attach(owner.account_id, owner.generation, current)

        checkpoint_writer = Mock()
        checkpoint_writer.flush_for_takeover.return_value = True
        checkpoint_writer.takeover_writer.side_effect = lambda *args, persist: persist()
        namespace = dict(
            account_id=owner.account_id,
            generation=owner.generation,
            connection=connection,
            service="world",
            STORE=store,
            WORLD=world,
            COMBAT_TEST=True,
            loaded=True,
            COMBAT_SESSIONS=SimpleNamespace(
                lookup_character=lambda identity: fixture.registry.lookup_character(
                    identity
                ),
                registry=fixture.registry,
            ),
            CHECKPOINT_WRITER=checkpoint_writer,
            time=SimpleNamespace(monotonic=lambda: clock.value),
            Movement=Movement,
            DatabaseError=DatabaseError,
            PoolTimeout=PoolTimeout,
            refresh_owned_character=lambda saved: saved,
            attach_combat_return_position=attach,
            placement_deadline=SimpleNamespace(take_expired=lambda *args: None),
            combat_return_bootstrap=lambda: ((13974, b"world"),),
            send_batch=lambda *args: observed["bootstrap"].append(args),
            join_world=lambda generation, peer, row: world.join(generation, peer, row),
            mark_static_sync_pending=lambda: observed["sync"].append(True),
            execute_test_command=lambda text: observed.setdefault(
                "commands", []
            ).append(text),
            execute_dungeon_exit_command=lambda **kwargs: observed.setdefault(
                "commands", []
            ).append("!exitdungeon"),
            record=lambda **row: observed["events"].append(row),
            send=lambda *args: observed["sends"].append(args),
            adopt_shared_duel=adoption,
            refresh_shared_combat=lambda: shared,
        )
        functions = extracted_helpers(
            namespace, initial, omit_entry_information=omit_entry_information
        )
        return functions, clock, observed, store, positions, world

    def test_committed_abort_waits_for_each_real_native_return_before_world_or_command(
        self,
    ):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_shared import Session

        namespace = native_return_adapter(connection=True)
        written_fight_id = namespace["written_fight_id"]
        frame = struct.pack(">IHi", 10, 12847, 332)
        failed = namespace["Connection"](
            SimpleNamespace(sendall=Mock(side_effect=OSError("partial write")))
        )
        with self.assertRaises(OSError):
            failed.sendall(frame)
        self.assertIsNone(failed.native_fight_id)
        published = namespace["Connection"](SimpleNamespace(sendall=Mock()))
        published.sendall(frame)
        self.assertEqual(published.native_fight_id, 332)

        # A selected main can differ from the last controlled hero. The
        # existing terminal codec must include the whole real owned cohort.
        actors = [
            Actor(
                identity,
                0,
                (index, 0, 0),
                41,
                6,
                3,
                100 - index,
                30,
                1 if identity < 108 else 2,
                True,
            )
            for index, identity in enumerate((105, 106, 107, 108, 109))
        ]
        actors.append(Actor(-200, 1, (5, 0, 0), 30, 6, 3, 1, 30))
        fight = Fight(
            332,
            actors,
            {(x, 0, 0) for x in range(6)},
            {0: {a.position for a in actors[:-1]}, 1: {(5, 0, 0)}},
        )
        fight.ready(1)
        fight.ready(2)
        fight.actors[105].hp = 0
        fight.actors[109].hp = 1
        runtime = RuntimeMessages(fight)
        runtime.awaiting_ack = fight.turn_id
        runtime.pending = [(12613, b"already-frozen-birth")]
        owners = (
            Session(1, 105, "a-current", 1314, 796),
            Session(2, 108, "b-current", 1314, 796),
        )
        shared = SimpleNamespace(
            fight=fight,
            runtime=runtime,
            participants={owner.account_id: owner for owner in owners},
            publication_recovery_aborted={
                105: {"applied": True},
                108: {"applied": True},
            },
            reconnect_presentations={1: object(), 2: object()},
            returned=set(),
            withdrawals={},
        )
        registry = SimpleNamespace(
            lock=threading.RLock(),
            command_cancellations={owner: shared for owner in owners},
            lookup_character=lambda identity: None,
        )
        fixture = SimpleNamespace(shared=shared, registry=registry)
        before = (
            fight.phase,
            fight.winner,
            [(a.id, a.hp) for a in actors],
            deepcopy(runtime.pending),
            runtime.awaiting_ack,
            runtime.action_id,
        )
        for owner, last_hero, peer_exit in (
            (owners[0], 107, False),
            (owners[0], 107, True),
            (owners[1], 109, False),
        ):
            with self.subTest(
                selected=owner.character_id,
                last_controlled=last_hero,
                peer_exit=peer_exit,
            ):
                registry.command_cancellations[owner] = shared
                fight.turn_index = fight.order.index(last_hero)
                funcs, clock, seen, store, positions, world = self.harness(
                    fixture, owner, (SimpleNamespace(),)
                )
                # Capture the real Connection successful-write contract, not
                # an invented actor/spell UID or synthetic client callback.
                frame = struct.pack(">IHi", 10, 12847, fight.id)
                self.assertEqual(written_fight_id(frame, None), fight.id)
                cells = dict(
                    zip(
                        funcs[
                            "recover_aborted_publication_cohort"
                        ].__code__.co_freevars,
                        funcs["recover_aborted_publication_cohort"].__closure__,
                    )
                )
                cells["connection"].cell_contents.native_fight_id = written_fight_id(
                    frame, None
                )
                self.assertTrue(funcs["consume_command_combat_recovery"]())
                pending = funcs["state"]()["aborted_native_return"]
                packets = seen["bootstrap"][0][-1]
                self.assertEqual([opcode for opcode, _ in packets], [12238, 13420])
                self.assertEqual(packets[0][1][12], 0)  # original normal terminal
                self.assertIs(funcs["state"]()["fight"], fight)
                self.assertEqual(world.snapshot()[0]["map_id"], 1134)
                # Both selected and last controlled members are represented.
                raw = packets[0][1]
                own_count = raw[13]
                own_ids = struct.unpack_from(">" + "q" * own_count, raw, 14)
                self.assertIn(owner.character_id, own_ids)
                self.assertIn(last_hero, own_ids)
                self.assertTrue(funcs["command_recovery_holds_request"](13260))
                self.assertFalse(funcs["command_recovery_holds_request"](12925))
                self.assertEqual(len(seen["bootstrap"]), 1)
                if peer_exit:
                    text = b"!exitdungeon"
                    self.assertEqual(
                        funcs["receiver_native_return"](
                            12366, struct.pack(">H", len(text)) + text
                        ),
                        "held",
                    )
                    self.assertEqual(pending.command, "!exitdungeon")
                    replacement = b"!astrub"
                    self.assertEqual(
                        funcs["receiver_native_return"](
                            12366, struct.pack(">H", len(replacement)) + replacement
                        ),
                        "held",
                    )
                    self.assertEqual(pending.command, "!exitdungeon")
                    self.assertEqual(len(seen["bootstrap"]), 1)
                for body in (
                    b"",
                    struct.pack(">iB", fight.id + 1, 1),
                    struct.pack(">iB", fight.id, 0),
                ):
                    with self.assertRaises(ValueError):
                        funcs["finish_aborted_native_return"](body)
                current = store.current_character_session
                store.current_character_session = lambda *args: False
                with self.assertRaisesRegex(ValueError, "stale"):
                    funcs["finish_aborted_native_return"](
                        struct.pack(">iB", fight.id, 1)
                    )
                store.current_character_session = current
                if owner.account_id == 2:  # nonleader command issuer
                    pending.command = "!astrub"
                    command_calls = []

                    def command_after_ack(text):
                        command_calls.append(text)
                        if len(command_calls) == 1:
                            raise PositionOwnerBusy(
                                "command position lease busy after native return"
                            )
                        seen.setdefault("commands", []).append(text)

                    completion_cells = dict(
                        zip(
                            funcs[
                                "complete_aborted_native_return"
                            ].__code__.co_freevars,
                            funcs["complete_aborted_native_return"].__closure__,
                        )
                    )
                    completion_cells[
                        "execute_test_command"
                    ].cell_contents = command_after_ack
                store.busy = True
                self.assertEqual(
                    funcs["receiver_native_return"](
                        12925, struct.pack(">iB", fight.id, 1)
                    ),
                    "dispatched",
                )
                self.assertTrue(pending.acknowledged)
                self.assertEqual(len(seen["bootstrap"]), 1)
                store.busy = False
                clock.value += 2
                self.assertTrue(funcs["continue_aborted_publication_recovery"]())
                self.assertIsNone(funcs["state"]()["fight"])
                self.assertIsNone(funcs["state"]()["combat_session"])
                if owner.account_id == 2:
                    self.assertIs(funcs["state"]()["aborted_native_return"], pending)
                    self.assertTrue(pending.world_returned)
                    self.assertTrue(funcs["continue_aborted_publication_recovery"]())
                    self.assertEqual(seen["commands"], ["!astrub"])
                    self.assertEqual(command_calls, ["!astrub", "!astrub"])
                    self.assertEqual(len(seen["bootstrap"]), 1)
                elif peer_exit:
                    self.assertEqual(seen["commands"], ["!exitdungeon"])
                    self.assertEqual(len(seen["bootstrap"]), 1)
                else:
                    self.assertEqual(seen["bootstrap"][-1][-1], ((13974, b"world"),))
                    self.assertEqual(len(seen["bootstrap"]), 2)
                with self.assertRaisesRegex(ValueError, "No aborted"):
                    funcs["finish_aborted_native_return"](
                        struct.pack(">iB", fight.id, 1)
                    )
                self.assertFalse(funcs["continue_aborted_publication_recovery"]())
                self.assertEqual(
                    (
                        fight.phase,
                        fight.winner,
                        [(a.id, a.hp) for a in actors],
                        runtime.pending,
                        runtime.awaiting_ack,
                        runtime.action_id,
                    ),
                    before,
                )
                self.assertFalse(any(row[2] == 12613 for row in seen["sends"]))
                self.assertIsNone(cells["connection"].cell_contents.native_fight_id)
        # The shared return path is also used after settlement. Preserve the
        # existing actual terminal codec/outcome instead of substituting abort.
        AbortedNativeReturn = namespace["AbortedNativeReturn"]
        from wakfu_server.combat_results import terminal_event

        fight.phase, fight.winner = "finished", 0
        shared.settlement_ready = True
        settled = AbortedNativeReturn(owners[0], shared)
        packets = settled.packets()
        self.assertEqual(packets[0], terminal_event(copy(runtime)))
        self.assertEqual(runtime.action_id, before[-1])
        settled.acknowledge(struct.pack(">iB", fight.id, int(settled.callback_flag)))
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))

    def test_actual_session_entry_import_initializes_information_free_cell(self):
        helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
        fixture, first, source1, second, source2 = helper.fixture(active=True)
        helper.takeover(fixture, first, source1)
        before, _, _, *_ = self.harness(
            fixture, first, source1, omit_entry_information=True
        )
        self.assertIn(
            "information",
            before["attempt_shared_combat_attachment"].__code__.co_freevars,
        )
        with self.assertRaisesRegex(NameError, "information"):
            before["attempt_shared_combat_attachment"]()
        after, _, seen, *_ = self.harness(fixture, first, source1)
        self.assertIn(
            "information",
            after["attempt_shared_combat_attachment"].__code__.co_freevars,
        )
        self.assertFalse(after["attempt_shared_combat_attachment"]())
        self.assertEqual(len(seen["sends"]), 1)
        self.assertEqual(seen["sends"][0][2], 349)
        self.assertIsInstance(seen["sends"][0][3], bytes)

    def test_real_publication_progress_retries_early_and_unchanged_wait_is_coalesced(
        self,
    ):
        helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
        fixture, first, source1, second, source2 = helper.fixture(active=True)
        helper.takeover(fixture, first, source1)
        shared = fixture.shared
        original = (shared.fight, shared.runtime, shared.ack)
        pending = tuple(shared.runtime.pending)
        funcs, clock, seen, *_ = self.harness(fixture, first, source1)
        self.assertFalse(funcs["attempt_shared_combat_attachment"]())
        self.assertFalse(funcs["attempt_shared_combat_attachment"]())
        self.assertEqual(len(seen["adopt"]), 1)
        self.assertEqual(len(seen["sends"]), 1)
        self.assertEqual((shared.fight, shared.runtime, shared.ack), original)
        self.assertEqual(tuple(shared.runtime.pending), pending)
        source1[0].after_write(frames(2, instance=first.instance_id), source1[1])
        self.assertFalse(funcs["attempt_shared_combat_attachment"]())
        self.assertEqual(len(seen["adopt"]), 2)
        clock.value += 1.1
        self.assertFalse(funcs["attempt_shared_combat_attachment"]())
        self.assertEqual(len(seen["adopt"]), 3)
        self.assertEqual(len(seen["sends"]), 2)
        helper.takeover(fixture, second, source2)
        funcs["attempt_shared_combat_attachment"]()
        self.assertIsNone(funcs["state"]()["publication_recovery_attempt_token"])
        self.assertIsNone(funcs["state"]()["publication_recovery_shared"])

    def test_real_peers_restore_positions_and_world_after_abort_receipt_with_busy_retry(
        self,
    ):
        helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
        fixture, first, source1, second, source2 = helper.fixture(active=True)
        helper.takeover(fixture, first, source1)
        shared = fixture.shared
        # This adapter starts at the completed receipt boundary and does not
        # qualify the SQL health write that produces that receipt.
        shared.participants[second.account_id] = second
        shared.publication_recovery_aborted = {
            first.character_id: {"applied": True},
            second.character_id: {"applied": True},
        }
        original = (shared.fight, shared.runtime, shared.ack)
        for owner, source in ((first, source1), (second, source2)):
            funcs, clock, seen, store, positions, world = self.harness(
                fixture, owner, source
            )
            store.busy = True
            self.assertTrue(funcs["continue_aborted_publication_recovery"]())
            self.assertIs(funcs["state"]()["publication_recovery_shared"], shared)
            self.assertIs(funcs["state"]()["fight"], shared.fight)
            self.assertEqual(len(seen["sends"]), 1)
            self.assertTrue(funcs["continue_aborted_publication_recovery"]())
            self.assertEqual(len(seen["sends"]), 1)
            store.busy = False
            clock.value += 1.1
            self.assertTrue(funcs["continue_aborted_publication_recovery"]())
            state = funcs["state"]()
            for name in (
                "fight",
                "fight_messages",
                "combat_session",
                "group_lease",
                "checkpoint_id",
                "checkpoint_revision",
                "pending_terminal_world_recovery",
                "publication_recovery_shared",
            ):
                self.assertIsNone(state[name], name)
            key = (owner.account_id, owner.generation, owner.character_id)
            self.assertEqual(positions.entries[key]["current"]["map_id"], 527)
            self.assertEqual(world.snapshot()[0]["map_id"], 527)
            self.assertEqual(state["position"], dict(x=5, y=6, z=0))
            self.assertEqual(len(seen["bootstrap"]), 1)
            self.assertEqual(seen["sync"], [True])
        self.assertEqual((shared.fight, shared.runtime, shared.ack), original)

    def test_emergency_command_binds_selected_replacement_while_fight_attachment_is_deferred(
        self,
    ):
        from wakfu_server.combat_shared import Session

        helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
        fixture, first, source1, second, source2 = helper.fixture(active=True)
        replacement = Session(
            first.account_id,
            first.character_id,
            "new-emergency-generation",
            first.map_id,
            first.instance_id,
        )
        shared = fixture.shared
        fixture.registry.live_session = lambda owner: owner in (replacement, second)
        funcs, clock, seen, store, positions, world = self.harness(
            fixture, replacement, source1
        )
        funcs["set_state"](fight=None, fight_messages=None, combat_session=None)
        # This source-level test qualifies socket binding and no native replay;
        # durable participant takeover is qualified by the isolated SQL case.
        with patch("wakfu_server.fight_store.takeover_participant"):
            self.assertIs(funcs["attach_command_combat"](), shared)
        state = funcs["state"]()
        self.assertEqual(state["combat_session"], replacement)
        self.assertIs(state["fight"], shared.fight)
        self.assertNotIn(replacement.account_id, shared.connected)
        self.assertEqual(seen["bootstrap"], [])
        self.assertEqual(seen["sends"], [])

    def test_incoming_escape_chat_survives_cancel_recovery_but_stale_combat_action_is_held(
        self,
    ):
        for opcode, held in ((12366, False), (13952, True)):
            with self.subTest(opcode=opcode):
                helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
                fixture, first, source1, second, source2 = helper.fixture(active=True)
                helper.takeover(fixture, first, source1)
                shared = fixture.shared
                shared.publication_recovery_aborted = {
                    first.character_id: {"applied": True}
                }
                fixture.registry.command_cancellations = {first: shared}
                with shared.lock, fixture.registry.lock:
                    fixture.registry._remove_locked(fixture.registry, shared)
                funcs, clock, seen, store, positions, world = self.harness(
                    fixture, first, source1
                )
                self.assertEqual(funcs["command_recovery_holds_request"](opcode), held)
                self.assertIsNone(funcs["state"]()["fight"])
                self.assertIsNone(funcs["state"]()["combat_session"])
                self.assertEqual(len(seen["bootstrap"]), 1)

    def test_deferred_publication_guard_allows_chat_to_reach_authorized_escape_dispatch(
        self,
    ):
        source = Path(__file__).parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        guard = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and any(
                isinstance(child, ast.Constant)
                and child.value == "combat_publication_recovery_action_deferred"
                for stmt in node.body
                for child in ast.walk(stmt)
            )
        )
        expression = ast.fix_missing_locations(ast.Expression(guard.test))
        for opcode, pending, held in (
            (12366, None, False),
            (13130, None, True),
            (13260, None, True),
            (12925, None, True),
            (12925, object(), False),
        ):
            with self.subTest(opcode=opcode, pending=pending):
                self.assertEqual(
                    eval(
                        compile(expression, str(source), "eval"),
                        {
                            "opcode": opcode,
                            "deferred_native_combat_attachment": lambda: object(),
                            "aborted_native_return": pending,
                        },
                    ),
                    held,
                )

    def test_command_cancelled_peers_recover_at_socket_boundary_after_registry_retirement(
        self,
    ):
        helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
        fixture, first, source1, second, source2 = helper.fixture(active=True)
        helper.takeover(fixture, first, source1)
        shared = fixture.shared
        shared.participants[second.account_id] = second
        # SQL transaction qualification is separate. Begin with its committed
        # per-owner receipts and exercise the actual socket boundary helpers.
        shared.publication_recovery_aborted = {
            first.character_id: {"applied": True},
            second.character_id: {"applied": True},
        }
        shared.fight.actors[first.character_id].hp = 0
        fixture.registry.command_cancellations = {first: shared, second: shared}
        with shared.lock, fixture.registry.lock:
            fixture.registry._remove_locked(fixture.registry, shared)
        self.assertIsNone(fixture.registry.lookup_character(second.character_id))
        for owner, source in ((first, source1), (second, source2)):
            funcs, clock, seen, store, positions, world = self.harness(
                fixture, owner, source
            )
            if owner == second:
                funcs["set_state"](fight=None, fight_messages=None, combat_session=None)
            self.assertTrue(funcs["consume_command_combat_recovery"]())
            self.assertIsNone(funcs["state"]()["fight"])
            self.assertIsNone(funcs["state"]()["combat_session"])
            self.assertFalse(funcs["consume_command_combat_recovery"]())
            self.assertEqual(len(seen["bootstrap"]), 1)
            self.assertEqual(world.snapshot()[0]["map_id"], 527)
        self.assertFalse(fixture.registry.command_cancellations)

    def test_abort_requires_owned_waiting_generation_and_leaves_normal_combat_alone(
        self,
    ):
        from wakfu_server.combat_shared import Session

        helper = staged_fixtures.StagedPartyPublicationRecoveryTests()
        fixture, first, source1, second, source2 = helper.fixture(active=True)
        helper.takeover(fixture, first, source1)
        shared = fixture.shared
        foreign = Session(
            first.account_id,
            first.character_id,
            "foreign-generation",
            first.map_id,
            first.instance_id,
        )
        funcs, clock, seen, *_ = self.harness(fixture, foreign, source1)
        original = (shared.fight, shared.runtime, shared.ack)
        with self.assertRaisesRegex(ValueError, "recuperación"):
            funcs["abort_waiting_publication_cohort"]()
        self.assertIs(fixture.registry.lookup(99), shared)
        self.assertEqual((shared.fight, shared.runtime, shared.ack), original)
        self.assertFalse(seen["bootstrap"])
        helper.takeover(fixture, second, source2)
        funcs, clock, seen, *_ = self.harness(fixture, first, source1)
        self.assertFalse(funcs["abort_waiting_publication_cohort"]())
        self.assertIs(fixture.registry.lookup(99), shared)
        self.assertFalse(seen["bootstrap"])


if __name__ == "__main__":
    unittest.main()
