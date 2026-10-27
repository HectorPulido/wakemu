"""Real child preparation leaves native reads and durable scope fences live."""
import ast
from contextlib import contextmanager
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.ecology_admin_jobs import EcologyAdminJobs
from wakfu_server.ecology_admin_worker import PreparationProcess
from wakfu_server.world import World


class EcologyAdminJobsTests(PostgresCase):
    def test_real_child_preserves_reader_original_scope_and_partial_commit_fences(self):
        from test_ecology_admin_domain_postgres import (
            _load_domain_with_native_boundaries_stubbed,
        )
        from wakfu_server import native_catalog

        domain = _load_domain_with_native_boundaries_stubbed()
        account = self.store.register("async-ecology", "local-password")["id"]
        actor = self.store.create_character(account, "Async Ecology")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, actor["id"])
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=TRUE WHERE id=%s", (account,))
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0,x=5,y=6,z=0 WHERE id=%s",
                (actor["id"],),
            )
        actor = self.store.character(account, actor["id"])
        original = dict(actor)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        entered = Path(directory.name) / "entered"
        release = Path(directory.name) / "release"
        child_code = """
import os,pathlib,struct,sys,time
from types import MappingProxyType
from wakfu_server.ecology_admin_worker import decode,encode
entered,release=map(pathlib.Path,sys.argv[1:3])
revision=sys.argv[3]
while header:=sys.stdin.buffer.read(4):
    size=struct.unpack('>I',header)[0]
    domain,map_id,region_id=decode(sys.stdin.buffer.read(size))
    entered.write_text(str(os.getpid()))
    deadline=time.monotonic()+5
    while not release.exists():
        if time.monotonic()>deadline: raise TimeoutError('fixture was not released')
        time.sleep(.002)
    prepared=MappingProxyType({'map_id':map_id,'region_id':region_id,'child_pid':os.getpid(),
        'candidates':MappingProxyType({70:({'reference':701},)}),
        'adjacency':MappingProxyType({(1,2,3):((2,3,4),)})})
    sys.stdout.buffer.write(encode({'ok':True,'revision':revision,'prepared':prepared}))
    sys.stdout.buffer.flush()
"""
        processes = []

        def prepare_factory():
            process = PreparationProcess(
                timeout=5,
                command=[
                    sys.executable,
                    "-c",
                    child_code,
                    str(entered),
                    str(release),
                    native_catalog.release(),
                ],
            )
            processes.append(process)
            return process

        guards, mutations, publications, notifications = [], [], [], []
        guard_depth = [0]
        invalidate_after_publish = [False]
        live_players = [dict(id=actor["id"], map_id=1134)]

        @contextmanager
        def coordination(scope):
            guard_depth[0] += 1
            guards.append(("enter", scope))
            try:
                yield
            finally:
                guards.append(("exit", scope))
                guard_depth[0] -= 1

        def mutate(db, groups, map_id, instance_id, region_id, *, players, prepared):
            self.assertEqual(guard_depth[0], 1)
            self.assertEqual((map_id, instance_id), (1134, 0))
            self.assertEqual(prepared["candidates"][70][0]["reference"], 701)
            self.assertEqual(prepared["adjacency"][(1, 2, 3)], ((2, 3, 4),))
            self.assertNotEqual(prepared["child_pid"], os.getpid())
            self.assertEqual(players, live_players)
            mutations.append((map_id, instance_id, region_id, prepared["child_pid"]))
            return {
                "added": 1,
                "packets": [],
                "created_groups": [{"key": [map_id, instance_id, region_id]}],
            }

        def publish(outcome):
            self.assertEqual(guard_depth[0], 1)
            with self.store.connection() as db:
                row = db.execute(
                    "SELECT outcome FROM ecology_admin_operations WHERE id=%s",
                    (outcome["operation_id"],),
                ).fetchone()
            self.assertIsNotNone(row, "publication preceded durable scope commit")
            publications.append(outcome["operation_id"])
            if invalidate_after_publish[0]:
                self.store.begin_session(account)

        jobs = EcologyAdminJobs(
            self.store,
            SimpleNamespace(lock=threading.RLock()),
            players=lambda: list(live_players),
            coordination=coordination,
            publish=publish,
            prepare_factory=prepare_factory,
        )

        def wait_finished(handle):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                result = jobs.status(handle)
                if result["status"] != "running":
                    jobs.thread.join(timeout=1)
                    return result
                time.sleep(0.002)
            self.fail("bounded ecology job did not finish")

        def cleanup():
            release.touch()
            deadline = time.monotonic() + 5
            while jobs.active is not None and time.monotonic() < deadline:
                time.sleep(0.002)
            for process in processes:
                process.close()

        self.addCleanup(cleanup)

        def original_scopes(db, submitted, global_scope, *, genesis=False):
            self.assertEqual(
                tuple(
                    submitted[key] for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                tuple(
                    original[key] for key in ("map_id", "instance_id", "x", "y", "z")
                ),
            )
            return [(1134, 0, 7), (1134, 0, 8)]

        from native_multiplayer_lifecycle_fixture import (
            prepare_jamajam_encounter,
            kill_jamajam_and_continue,
        )

        encounter = prepare_jamajam_encounter()
        with patch.dict(
            sys.modules, {"wakfu_server.ecology_admin": domain}
        ), patch.object(domain, "_scopes", side_effect=original_scopes), patch.object(
            domain, "_genesis", side_effect=mutate
        ):
            started = time.monotonic()
            accepted = jobs.request(
                account_id=account,
                generation=generation,
                character=actor,
                command="!genesis-all",
                notify=notifications.append,
            )
            self.assertLess(time.monotonic() - started, 0.2)
            deadline = time.monotonic() + 3
            while not entered.exists() and time.monotonic() < deadline:
                time.sleep(0.002)
            self.assertTrue(entered.exists(), "real preparation child did not start")
            self.assertNotEqual(int(entered.read_text()), os.getpid())
            repeated = jobs.request(
                account_id=account,
                generation=generation,
                character=actor,
                command="!genesis-all",
            )
            self.assertTrue(repeated["coalesced"])
            self.assertEqual(repeated["handle"], accepted["handle"])
            with self.assertRaisesRegex(ValueError, "Ya hay una operación"):
                jobs.request(
                    account_id=account,
                    generation=generation,
                    character=actor,
                    command="!nuke",
                )
            self.assertEqual(len(processes), 1)
            self.assertEqual(mutations, [])
            self.assertEqual(guards, [])

            # Exercise the real socket receive function while the child remains
            # blocked. These are native frame opcodes, not queued mock returns.
            source = Path(__file__).resolve().parents[1] / "local_game_server.py"
            receive_node = next(
                node
                for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == "receive"
            )
            namespace = {"socket": socket}
            exec(
                compile(
                    ast.Module(body=[receive_node], type_ignores=[]),
                    str(source),
                    "exec",
                ),
                namespace,
            )
            reader, writer = socket.socketpair()
            self.addCleanup(reader.close)
            self.addCleanup(writer.close)
            reader.settimeout(0.1)
            opcodes = (13917, 12296, 23354)
            recipient, text = b"Receiver", b"Reader stays live"
            private_body = (
                struct.pack(">B", len(recipient))
                + recipient
                + struct.pack(">H", len(text))
                + text
            )
            writer.sendall(
                b"".join(
                    struct.pack(">IBH", 7 + len(body), 0, opcode) + body
                    for opcode, body in (
                        (13917, private_body),
                        (12296, b""),
                        (23354, b""),
                    )
                )
            )
            private_deliveries = []
            chat_world = World(
                lambda row: b"spawn",
                lambda row: b"remove",
                lambda *args: private_deliveries.append(args),
            )
            chat_world.join(generation, "issuer-peer", actor)
            chat_world.join(
                "recipient-lease",
                "recipient-peer",
                dict(
                    id=actor["id"] + 1000,
                    account_id=account + 1000,
                    name="Receiver",
                    map_id=527,
                    instance_id=0,
                ),
            )
            private_deliveries.clear()
            branch = next(
                node
                for node in ast.walk(ast.parse(source.read_text()))
                if isinstance(node, ast.If)
                and ast.unparse(node.test) == "opcode == 13917 and loaded"
            )
            # Retain the actual branch body, excluding unrelated later elifs.
            branch.orelse = []
            dispatch = ast.fix_missing_locations(
                ast.Module(
                    body=[
                        ast.For(
                            target=ast.Name(id="_frame", ctx=ast.Store()),
                            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                            body=[branch],
                            orelse=[],
                        )
                    ],
                    type_ignores=[],
                )
            )
            from protocol_codec import decode_body

            observed = []
            for opcode in opcodes:
                size = struct.unpack(
                    ">I", namespace["receive"](reader, 4, lambda: True)
                )[0]
                frame = namespace["receive"](reader, size - 4, lambda: True)
                route, actual = struct.unpack(">BH", frame[:3])
                observed.append(actual)
                self.assertEqual((route, actual), (0, opcode))
                if actual == 13917:
                    chat_namespace = dict(
                        opcode=actual,
                        loaded=True,
                        body=frame[3:],
                        decode_body=decode_body,
                        time=time,
                        last_chat=0,
                        WORLD=chat_world,
                        generation=generation,
                        character=actor,
                        account_id=account,
                        connection=reader,
                        service="world",
                        STORE=SimpleNamespace(
                            current_character_session=lambda *args: True
                        ),
                        SOCIAL_CONTACTS=SimpleNamespace(
                            private_chat_block_reason=lambda *args: None
                        ),
                        record=lambda **kwargs: None,
                    )
                    exec(compile(dispatch, str(source), "exec"), chat_namespace)
            self.assertEqual(
                [(row[0], row[1]) for row in private_deliveries],
                [("recipient-peer", 720), ("issuer-peer", 720)],
            )
            self.assertEqual(tuple(observed), opcodes)
            self.assertEqual(jobs.status(accepted["handle"])["status"], "running")

            # The isolated planner must also leave real shared native callbacks
            # and a paid lethal NPC action live, not just socket frame parsing.
            lifecycle = kill_jamajam_and_continue(encounter)
            self.assertEqual(
                (lifecycle["players"], lifecycle["owners"], lifecycle["npcCount"]),
                (5, 3, 7),
            )
            self.assertEqual(lifecycle["targetReference"], 1620)
            self.assertGreater(lifecycle["apSpent"], 0)
            self.assertGreater(lifecycle["retainedBefore"], 0)
            self.assertEqual(len(lifecycle["deathPublishedToAccounts"]), 3)
            self.assertEqual(lifecycle["postKillAck"], [False, False, True])
            self.assertEqual(lifecycle["phase"], "active")
            self.assertEqual(jobs.status(accepted["handle"])["status"], "running")
            self.assertEqual(mutations, [])
            self.assertEqual(guards, [])

            # A legal travel while preparing neither retargets nor cancels the
            # originally submitted ecology scopes. Commit reads fresh players.
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=527,x=50,y=60 WHERE id=%s",
                    (actor["id"],),
                )
            actor.update(map_id=527, x=50, y=60)
            live_players[:] = [dict(id=actor["id"], map_id=527)]
            release.touch()
            completed = wait_finished(accepted["handle"])
            self.assertEqual(completed.get("failures"), [])
            self.assertEqual(
                (completed["status"], completed["added"]), ("completed", 2)
            )
            self.assertEqual(completed["scopes"], [(1134, 0, 7), (1134, 0, 8)])
            self.assertEqual(len(publications), 2)
            self.assertEqual(len(completed["operation_ids"]), 2)
            self.assertNotEqual(completed["worker_pid"], os.getpid())

            invalidate_after_publish[0] = True
            before_mutations = len(mutations)
            partial = jobs.request(
                account_id=account,
                generation=generation,
                character=original,
                command="!genesis-all",
                notify=notifications.append,
            )
            interrupted = wait_finished(partial["handle"])
            self.assertEqual(interrupted["status"], "cancelled")
            self.assertEqual(interrupted["added"], 1)
            self.assertEqual(interrupted["scopes"], [(1134, 0, 7)])
            self.assertEqual(len(mutations), before_mutations + 1)
            self.assertEqual(len(interrupted["operation_ids"]), 1)
            with self.store.connection() as db:
                audits = db.execute(
                    "SELECT id FROM ecology_admin_operations ORDER BY id"
                ).fetchall()
            self.assertEqual(len(audits), 3)
            stale = jobs.request(
                account_id=account,
                generation=generation,
                character=original,
                command="!genesis",
            )
            rejected = wait_finished(stale["handle"])
            self.assertEqual(rejected["status"], "cancelled")
            self.assertEqual(len(mutations), before_mutations + 1)
            self.assertIn("sesión", rejected["message"])
            self.assertNotIn("Administrative ecology", rejected["message"])
            fresh_generation = self.store.begin_session(account)
            self.store.select_character(account, fresh_generation, actor["id"])
            invalidate_after_publish[0] = False
            before_mutations = len(mutations)
            # A foreground account writer must not trap the background worker
            # in an unbounded preflight row-lock wait.
            with self.store.connection() as db:
                db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
                started = time.monotonic()
                contended = jobs.request(
                    account_id=account,
                    generation=fresh_generation,
                    character=original,
                    command="!genesis",
                )
                bounded = wait_finished(contended["handle"])
                self.assertLess(time.monotonic() - started, 1.5)
                self.assertEqual(bounded["status"], "failed")
                self.assertEqual(bounded["error_type"], "LockNotAvailable")
            self.assertEqual(len(mutations), before_mutations)
            jobs.prepare_factory = lambda: PreparationProcess(
                timeout=1, command=[sys.executable, "-c", "import sys;sys.exit(9)"]
            )
            broken = jobs.request(
                account_id=account,
                generation=fresh_generation,
                character=original,
                command="!genesis",
            )
            failed = wait_finished(broken["handle"])
            self.assertEqual(failed["status"], "failed")
            self.assertIn("no pudo", failed["message"])
            self.assertEqual(len(mutations), before_mutations)
            writer.sendall(struct.pack(">IBH", 7, 0, 23354))
            self.assertEqual(
                struct.unpack(">I", namespace["receive"](reader, 4, lambda: True))[0], 7
            )
            self.assertEqual(
                struct.unpack(">BH", namespace["receive"](reader, 3, lambda: True)),
                (0, 23354),
            )
        self.assertEqual(len(notifications), 2)
