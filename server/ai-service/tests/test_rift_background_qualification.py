"""Rift background source qualification against the installed World engine."""
from copy import deepcopy
import socket
import struct
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_world_background import WorldBackgroundTests
from wakfu_ai.bridge.world_background import BackgroundTurn, admission, schedule
from wakfu_ai.bridge.world_host import execute
from wakfu_ai.bridge.world_sources import bind_private_sources
from wakfu_server.combat_background_work import BackgroundDiagnostics, BackgroundWork
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_state import Actor, Fight


def accepted_rift(shared, candidate, runtime, packets):
    candidate.rift_wave_state.setdefault("qualified_test_receipts", []).append(
        candidate.turn_id
    )
    return Transition(candidate, runtime, packets)


def rejected_rift(shared, candidate, runtime, packets):
    raise RuntimeError("fixture durable Rift receipt rejected")


def fixture():
    case = WorldBackgroundTests()
    case.setUp()
    case.session = Session(1, 10, "owner-generation", 1314, 77)
    case.registry = Registry(lambda session: session is case.session)
    player = Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 10, 1, True)
    npcs = [
        Actor(identity, 1, (index + 2, 0, 0), 20, 4, 2, 1, 10)
        for index, identity in enumerate(range(-200, -212, -1))
    ]
    case.fight = Fight(
        801,
        [player, *npcs],
        {(x, 0, 0) for x in range(16)},
        {0: {(0, 0, 0)}, 1: {npc.position for npc in npcs}},
    )
    case.fight.phase = "active"
    case.fight.order, case.fight.turn_index = [
        -201,
        10,
        *[npc.id for npc in npcs if npc.id != -201],
    ], 0
    case.fight.turn_id = 7
    for index, actor in enumerate(npcs):
        actor.native_obstacle_id = index + 1
    for actor in case.fight.actors.values():
        actor.effect_stats, actor.effect_maxima = {4: 0}, {4: 0}
    sources = {
        npc.id: dict(id=npc.id, ref=5, level=10, map_id=1314, instance_id=77)
        for npc in npcs
    }
    newborns = [npc.id for npc in npcs if npc.id != -200]
    case.fight.rift_monsters = sources
    case.fight.rift_wave_state = dict(
        instance_id=77,
        wave=2,
        turn_budget=40,
        wave_actor_ids=newborns,
        current_actor_ids=newborns,
        pending_wave=None,
        staged_receipts=[
            dict(
                completed_wave=1,
                next_actor_ids=newborns,
                next_species_refs=[5] * len(newborns),
            )
        ],
    )
    case.fight.native_rift_creation_deliveries = {
        identity: [
            dict(
                opcode=12608,
                payload_hex=(b"\x00\x01\x01" + struct.pack(">q", identity)).hex(),
            ),
            dict(opcode=13091, payload_hex=struct.pack(">iq", 801, identity).hex()),
        ]
        for identity in newborns
    }
    owner = dict(id=10, account_id=1, map_id=1314, instance_id=77)
    provider = OwnedExpirationFactory(
        characters={10: owner},
        monsters={-200: sources[-200]},
        decks={10: b"deck"},
        actor_id=10,
    )
    case.runtime = SimpleNamespace(
        fight=case.fight,
        awaiting_ack=None,
        pending=[],
        expiration_runtime_factory=provider,
        turn_start_provider=provider.turn_start,
        turn_end_provider=provider.turn_end,
        stats_serializer=None,
    )
    case.shared = case.registry.register(case.fight, case.session, runtime=case.runtime)
    case.shared.join_context = {"rift_accepted_action": accepted_rift}
    case.adapter = SimpleNamespace(registry=case.registry)
    case.viewer = owner
    return case


class RiftBackgroundQualificationTests(unittest.TestCase):
    def test_complete_birth_sources_background_reader_commit_cancel_and_invalid_authority(
        self,
    ):
        case = fixture()
        self.assertIsNone(admission(case.shared))
        locked, unlock = threading.Event(), threading.Event()

        def hold_shared():
            with case.shared.lock:
                locked.set()
                unlock.wait(2)

        holder = threading.Thread(target=hold_shared)
        holder.start()
        self.assertTrue(locked.wait(2))
        called = []
        try:
            started = time.monotonic()
            self.assertEqual(admission(case.shared), "defer_shared_native_work")
            list(
                execute(
                    case.runtime,
                    case.context(),
                    lambda *args, **kwargs: called.append(True),
                )
            )
            self.assertEqual(
                schedule(
                    case.shared,
                    case.adapter,
                    case.session,
                    object(),
                    object(),
                    case.viewer,
                    {},
                    BackgroundDiagnostics(),
                ),
                "busy",
            )
            self.assertLess(time.monotonic() - started, 0.1)
            self.assertEqual(called, [])
        finally:
            unlock.set()
            holder.join(2)
        original = deepcopy(case.runtime.expiration_runtime_factory.monsters)
        candidate = deepcopy(case.runtime)
        bind_private_sources(candidate, case.session)
        self.assertEqual(
            set(candidate.expiration_runtime_factory.monsters),
            set(case.fight.rift_monsters),
        )
        self.assertEqual(candidate.stats_serializer.monsters, case.fight.rift_monsters)
        self.assertEqual(case.runtime.expiration_runtime_factory.monsters, original)
        self.assertIs(
            candidate.turn_start_provider.__self__, candidate.expiration_runtime_factory
        )
        encoded = []
        encoder = SimpleNamespace(
            actual_actor_stats=lambda *args, **kwargs: b"player-stats",
            actual_monster_actor_stats=lambda source, actor, fight_id, **kwargs: encoded.append(
                source
            )
            or b"stats",
        )
        with patch.dict(sys.modules, {"wakfu_server.combat_actor": encoder}):
            self.assertEqual(
                candidate.stats_serializer(
                    candidate.fight.actors[-201], candidate.fight
                ),
                b"stats",
            )
        self.assertEqual(encoded, [case.fight.rift_monsters[-201]])

        for damage in (
            "callback",
            "accepted-closure",
            "missing-source",
            "receipt",
            "birth",
            "species",
            "map",
            "captured",
        ):
            broken = fixture()
            if damage == "callback":
                broken.runtime.turn_start_provider = lambda *args: None
            elif damage == "accepted-closure":
                value = object()
                broken.shared.join_context["rift_accepted_action"] = lambda *args: value
            elif damage == "missing-source":
                broken.fight.rift_monsters.pop(-201)
            elif damage == "receipt":
                broken.fight.rift_wave_state["staged_receipts"] = []
            elif damage == "birth":
                broken.fight.native_rift_creation_deliveries[-201][1][
                    "payload_hex"
                ] = "00"
            elif damage == "species":
                broken.fight.rift_monsters[-201]["ref"] = 41
            elif damage == "map":
                broken.runtime.expiration_runtime_factory.characters[10]["map_id"] = 999
            else:
                broken.runtime.expiration_runtime_factory.monsters[-200]["ref"] = 41
            with self.subTest(damage=damage):
                self.assertEqual(admission(broken.shared), "rift_providers_unqualified")

        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        threads = []
        work = BackgroundWork(max_jobs=1)
        self.addCleanup(work.shutdown)
        packet = (12588, b"qualified-rift-action")

        def runner(native, **kwargs):
            threads.append(threading.get_ident())
            self.assertEqual(
                set(native.expiration_runtime_factory.monsters),
                set(case.fight.rift_monsters),
            )
            native.fight.actors[10].hp -= 5
            entered.set()
            self.assertTrue(release.wait(2))
            native.fight.turn_index = 1
            native.awaiting_ack, native.pending = 7, [(12503, b"next-turn")]
            yield [packet], {"action": {"type": "cast"}}

        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        # The fixture is deliberately a generic runtime. Registry's native
        # RuntimeMessages type check must not bootstrap unrelated catalogs.
        runtime_type = SimpleNamespace(
            RuntimeMessages=type("NativeRuntimeBoundary", (), {})
        )
        with patch.dict(
            sys.modules, {"wakfu_server.combat_runtime_messages": runtime_type}
        ), patch("wakfu_server.combat_background_work.NATIVE_WORK", work):
            list(execute(case.runtime, case.context(), runner))
            self.assertTrue(entered.wait(2))
            list(execute(case.runtime, case.context(), runner))
            right.sendall(b"chat")
            self.assertEqual(left.recv(4), b"chat")
            self.assertEqual(case.shared.fight.actors[10].hp, 60)
            self.assertEqual(case.shared.sequence, 0)
            self.assertNotEqual(threads[0], threading.get_ident())
            self.assertEqual(len(threads), 1)
            release.set()
            case._wait_until(lambda: not work.jobs)
        diagnostic_rows, _ = case.connection.native_ai_diagnostics.drain(
            (1, "owner-generation", 10)
        )
        self.assertFalse(
            [
                row
                for row in diagnostic_rows
                if row.get("event") == "combat_background_native_failed"
            ],
            diagnostic_rows,
        )
        self.assertEqual(case.shared.sequence, 1)
        self.assertEqual(case.shared.fight.actors[10].hp, 55)
        self.assertEqual(
            case.shared.fight.rift_wave_state["qualified_test_receipts"], [7]
        )
        self.assertEqual(
            case.shared.fight.rift_wave_state["staged_receipts"],
            case.fight.rift_wave_state["staged_receipts"],
        )
        self.assertEqual(case.registry.drain(801, case.session)[0].packets, (packet,))
        self.assertEqual(
            case.shared.runtime.stats_serializer.monsters,
            case.shared.fight.rift_monsters,
        )
        self.assertEqual(case.socket_send_threads, [])

        failed = fixture()
        failed.shared.join_context["rift_accepted_action"] = rejected_rift

        def rejected_runner(native, **kwargs):
            native.fight.actors[10].hp -= 9
            native.awaiting_ack, native.pending = 7, [(12503, b"uncommitted")]
            yield [packet], {"action": {"type": "cast"}}

        with patch.dict(
            sys.modules, {"wakfu_server.combat_runtime_messages": runtime_type}
        ):
            BackgroundTurn(
                failed.shared,
                failed.adapter,
                failed.session,
                rejected_runner,
                object(),
                failed.viewer,
                {},
                BackgroundDiagnostics(),
            )()
        self.assertEqual(failed.shared.sequence, 0)
        self.assertEqual(failed.shared.fight.actors[10].hp, 60)
        self.assertFalse(getattr(failed.shared, "native_ai_turn_claim", None))
        self.assertTrue(all(not rows for rows in failed.shared.outboxes.values()))
        self.assertNotIn("qualified_test_receipts", failed.shared.fight.rift_wave_state)

        cancelled = fixture()
        pending, finish = threading.Event(), threading.Event()
        self.addCleanup(finish.set)

        def cancelled_runner(native, **kwargs):
            native.fight.actors[10].hp -= 20
            pending.set()
            self.assertTrue(finish.wait(2))
            yield [packet], {"action": {"type": "cast"}}

        job = BackgroundTurn(
            cancelled.shared,
            cancelled.adapter,
            cancelled.session,
            cancelled_runner,
            object(),
            cancelled.viewer,
            {},
            BackgroundDiagnostics(),
        )
        thread = threading.Thread(target=job)
        thread.start()
        self.assertTrue(pending.wait(2))
        job.cancel()
        finish.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(cancelled.shared.sequence, 0)
        self.assertEqual(cancelled.shared.fight.actors[10].hp, 60)
        self.assertFalse(getattr(cancelled.shared, "native_ai_turn_claim", None))
        self.assertTrue(all(not rows for rows in cancelled.shared.outboxes.values()))
