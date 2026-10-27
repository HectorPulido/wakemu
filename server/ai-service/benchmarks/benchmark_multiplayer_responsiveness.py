"""Read native private chat during a real shared TCP AI background turn.

Private Registry leases qualify worker/reader concurrency, not durable login,
Rift checkpoint publication, client rendering, or successful map transport.
"""
import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import threading
import time

from benchmarks.benchmark_multiplayer_native import registered_multiplayer_fixture
from wakfu_ai.bridge.world_background import BackgroundTurn
from wakfu_ai.bridge.world_entry import native_exporter
from wakfu_ai.native.native_profiles import encounter_profiles
from wakfu_ai.native.native_stats import NativeStats
from wakfu_ai.native.native_turn import run_turn
from wakfu_ai.transport.framed_context import FramedContextTransport
from wakfu_server import native_catalog
from wakfu_server.combat_background_work import BackgroundDiagnostics, NATIVE_WORK
from wakfu_server import combat_turn_guard
from wakfu_server.world import World
from protocol_codec import decode_body


@dataclass
class PrivateAdapter:
    registry: object


class PrivateSessions:
    def __init__(self, identities):
        self.identities = set(identities)

    def current_character_session(self, account, generation, character):
        return (account, generation, character) in self.identities


class PrivateContacts:
    @staticmethod
    def private_chat_block_reason(*args):
        return None


class ObservedTransport(FramedContextTransport):
    def __init__(self):
        super().__init__("ai", 8090, timeout=30)
        self.request_entered = threading.Event()
        self.request_active = threading.Event()
        self.rpc = []

    def request(self, endpoint, payload):
        decision = endpoint in ("/v3/decide", "/v3/context/continue")
        if decision:
            self.request_active.set()
            self.request_entered.set()
        started = time.perf_counter()
        try:
            return super().request(endpoint, payload)
        finally:
            self.rpc.append(
                dict(endpoint=endpoint, wallMs=(time.perf_counter() - started) * 1000)
            )
            if decision:
                self.request_active.clear()


def _reader_and_chat(source):
    tree = ast.parse(source.read_text())
    receive = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "receive"
    )
    namespace = {"socket": socket}
    exec(
        compile(ast.Module(body=[receive], type_ignores=[]), str(source), "exec"),
        namespace,
    )
    branch = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "opcode == 13917 and loaded"
    )
    branch.orelse = []
    module = ast.fix_missing_locations(
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
    return namespace["receive"], compile(module, str(source), "exec")


def measure():
    source = Path(os.environ.get("BENCHMARK_MAIN", "/app/local_game_server.py"))
    guard_source = os.environ.get("BENCHMARK_GUARD")
    if guard_source:
        # A preliminary run may use this exact candidate definition over an
        # older validated engine; final-image qualification needs no injection.
        path = Path(guard_source)
        exec(compile(path.read_bytes(), str(path), "exec"), combat_turn_guard.__dict__)
    (
        registry,
        shared,
        sessions,
        characters,
        monsters,
        decks,
        excluded,
        _,
    ) = registered_multiplayer_fixture()
    session = sessions[0]
    runtime = shared.runtime
    runtime.tactical_encounter_id = "private-reader-background-" + str(os.getpid())
    transport = ObservedTransport()
    exporter = native_exporter()
    transport.request("/health", {})
    transport.catalog(exporter)
    profiles = encounter_profiles(runtime, native_catalog._database(), monsters)
    serializer = NativeStats(
        characters=characters, monsters=monsters, fight_id=shared.fight.id
    )
    diagnostics = BackgroundDiagnostics()
    entered_runner, finished = threading.Event(), threading.Event()
    worker_times = {}

    def runner(candidate, **unused):
        entered_runner.set()
        profile = profiles.get(
            monsters[candidate.fight.current.id]["ref"], profiles[None]
        )
        yield from run_turn(
            candidate,
            characters=characters,
            monsters=monsters,
            decks=decks,
            excluded_decks=excluded,
            viewer_id=session.character_id,
            flags=dict(native_start_events=True, native_area_callbacks=True),
            transport=transport,
            exporter=exporter,
            policy=profile["policy"],
            policy_version=profile["identity"],
            stats_serializer=serializer,
            budget_seconds=20,
        )

    job = BackgroundTurn(
        shared,
        PrivateAdapter(registry),
        session,
        runner,
        None,
        characters[session.character_id],
        monsters,
        diagnostics,
    )

    def execute_job():
        wall, cpu = time.perf_counter(), time.thread_time()
        try:
            job()
        finally:
            worker_times.update(
                wallMs=(time.perf_counter() - wall) * 1000,
                threadCpuMs=(time.thread_time() - cpu) * 1000,
            )
            finished.set()

    # Use the stable actual executor key that the foreground guard consults.
    class TrackedJob:
        def __call__(self):
            execute_job()

        def cancel(self):
            job.cancel()

    key = ("native-ai", id(shared))
    sockets = []
    timer = None
    result = {}
    try:
        assert NATIVE_WORK.submit(key, TrackedJob()) == "submitted"
        assert entered_runner.wait(15), "Real native runner was not entered"
        assert transport.request_entered.wait(
            30
        ), "Original AI TCP request was not entered"
        assert not finished.is_set(), "Worker ended before the reader probe"
        receive, chat_code = _reader_and_chat(source)
        deliveries = []

        def deliver(peer, opcode, body):
            peer.sendall(struct.pack(">IBH", 7 + len(body), 0, opcode) + body)
            deliveries.append((opcode, len(body)))

        world = World(lambda row: b"spawn", lambda row: b"remove", deliver)
        server, client = socket.socketpair()
        sockets.extend((server, client))
        receiver, receiver_client = socket.socketpair()
        sockets.extend((receiver, receiver_client))
        server.settimeout(0.02)
        client.settimeout(3)
        receiver_client.settimeout(3)
        sender = dict(characters[session.character_id], name="CombatSender")
        target = dict(sender, id=8001, account_id=9901, name="Receiver")
        world.join(session.generation, server, sender)
        world.join("outside-reader", receiver, target)
        # Spawn/removal setup traffic is not part of the native chat exchange.
        for connection in (client, receiver_client):
            connection.setblocking(False)
            try:
                while connection.recv(65536):
                    pass
            except BlockingIOError:
                pass
            connection.settimeout(3)
        deliveries.clear()
        store = PrivateSessions(
            (
                (session.account_id, session.generation, sender["id"]),
                (9901, "outside-reader", 8001),
            )
        )
        idle_calls = []
        sdk_loader_calls = []
        sent = []

        def on_idle():
            started = time.perf_counter()
            answer = combat_turn_guard.run_shared_npc_attempt(
                shared,
                lambda: sdk_loader_calls.append("unexpected duplicate SDK load"),
                lambda *args: None,
            )
            idle_calls.append(
                dict(wallMs=(time.perf_counter() - started) * 1000, result=answer)
            )
            return True

        recipient, text = (
            b"Receiver",
            b"Reader remains responsive during native planning",
        )
        body = (
            struct.pack(">B", len(recipient))
            + recipient
            + struct.pack(">H", len(text))
            + text
        )

        def send_private():
            sent.append(time.perf_counter())
            client.sendall(struct.pack(">IBH", 7 + len(body), 0, 13917) + body)

        timer = threading.Timer(0.08, send_private)
        timer.start()
        size = struct.unpack(">I", receive(server, 4, on_idle))[0]
        frame = receive(server, size - 4, on_idle)
        route, opcode = struct.unpack(">BH", frame[:3])
        assert (route, opcode) == (0, 13917)
        namespace = dict(
            opcode=opcode,
            loaded=True,
            body=frame[3:],
            decode_body=decode_body,
            time=time,
            last_chat=0,
            WORLD=world,
            generation=session.generation,
            character=sender,
            account_id=session.account_id,
            connection=server,
            service="world",
            STORE=store,
            SOCIAL_CONTACTS=PrivateContacts(),
            record=lambda **kwargs: None,
        )
        exec(chat_code, namespace)
        response_opcodes = []
        for connection in (client, receiver_client):
            size = struct.unpack(">I", receive(connection, 4))[0]
            response = receive(connection, size - 4)
            response_opcodes.append(struct.unpack(">BH", response[:3])[1])
        latency = (time.perf_counter() - sent[0]) * 1000
        assert response_opcodes == [720, 720], response_opcodes
        assert idle_calls and not sdk_loader_calls, (idle_calls, sdk_loader_calls)
        assert all(not row["result"] for row in idle_calls)
        assert (
            not finished.is_set()
        ), "Reader evidence was collected after planning finished"
        result.update(
            readerLatencyMs=latency,
            idleAttempts=idle_calls,
            duplicateSdkLoads=len(sdk_loader_calls),
            responseOpcodes=response_opcodes,
            workerStillRunningAtChatResponse=True,
            observedRequestActiveAtResponse=transport.request_active.is_set(),
        )
        assert finished.wait(
            45
        ), "Real background turn did not finish in its bounded allowance"
        rows, dropped = diagnostics.drain(
            (session.account_id, session.generation, session.character_id)
        )
        failures = [
            row for row in rows if row.get("event") == "combat_background_native_failed"
        ]
        assert not failures, failures
        assert (
            type(shared.runtime.awaiting_ack) is int
        ), "No native ACK barrier after actual worker"
        assert shared.sequence > 0, "No native action publication"
        result.update(
            worker=worker_times,
            diagnostics=rows,
            diagnosticDrops=dropped,
            sequence=shared.sequence,
            awaitingAck=shared.runtime.awaiting_ack,
            rpc=transport.rpc,
            roster=dict(players=5, owners=3, npcs=7),
            sourceMainSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            candidateGuardInjected=bool(guard_source),
            limits=[
                "Private in-memory leases and contacts policy; not durable login or Store admission",
                "Real native socket receive and private-chat branch; not the full live client handler loop",
                "Ordinary shared encounter; durable Rift checkpoint/wave and map travel not qualified",
                "Single latency probe, not a p95 distribution",
            ],
        )
        return result
    finally:
        if timer is not None:
            timer.cancel()
        if not finished.is_set():
            NATIVE_WORK.cancel(key)
        finished.wait(5)
        for connection in sockets:
            connection.close()
        transport.close()
        NATIVE_WORK.shutdown()


if __name__ == "__main__":
    print(json.dumps(measure(), default=str))
