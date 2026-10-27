"""Bounded, asynchronous shared turn expiry through the session adapter."""
import unittest
import sys
from types import ModuleType
from threading import Lock
from unittest.mock import patch

# These registry tests do not touch progression. Keep the production combat
# import from bootstrapping the native XP catalog (which requires PostgreSQL).
_level_stub = ModuleType("wakfu_server.character_levels")
_level_stub.MAX_CHARACTER_LEVEL = 200
_level_stub.MIN_CHARACTER_LEVEL = 1
_level_stub.XP_BY_LEVEL = {level: (level - 1) * 100 for level in range(1, 201)}
_level_stub.validate_character_level = lambda level: None
_previous_levels_module = sys.modules.get("wakfu_server.character_levels")
_previous_progression_module = sys.modules.get("wakfu_server.progression")
if _previous_levels_module is None:
    sys.modules["wakfu_server.character_levels"] = _level_stub

from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight

# RuntimeMessages builds its wire action allowlist at import time. The expiry
# transition in this test uses only the normal turn packets, so supply the
# tiny catalog projection without opening the catalog database.
from wakfu_server import native_catalog as _native_catalog

_real_catalog_load = _native_catalog.load
_native_catalog.load = lambda path: (
    {"packets": []}
    if "native-combat-action-packets" in str(path)
    else {"spells": []}
    if str(path).endswith("spells.json")
    else {}
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_session_adapter import CombatSessionAdapter

_native_catalog.load = _real_catalog_load
if _previous_levels_module is None:
    sys.modules.pop("wakfu_server.character_levels", None)
if _previous_progression_module is None:
    sys.modules.pop("wakfu_server.progression", None)


class DeferredWork:
    """Capture submitted work so the reader/worker boundary is deterministic."""

    def __init__(self):
        self.jobs = []

    def submit(self, key, operation):
        self.jobs.append((key, operation))
        return "submitted"


class CombatTurnExpiryBackgroundTests(unittest.TestCase):
    def setup_fight(self):
        first = Session(1, 30, "first", 1134, 0)
        second = Session(2, 40, "second", 1134, 0)
        live = {first, second}
        registry = Registry(lambda session: session in live)
        fight = Fight(
            901,
            [
                Actor(30, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(40, 1, (3, 0, 0), 60, 6, 3, 90, 1, 2, True),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0)}, 1: {(3, 0, 0)}},
        )
        shared = registry.register_duel(
            fight, (first, second), initial_packets={1: (), 2: ()}
        )
        with patch.object(
            _native_catalog,
            "load",
            side_effect=lambda path: (
                {"packets": []}
                if "native-combat-action-packets" in str(path)
                else {"spells": []}
                if str(path).endswith("spells.json")
                else {"items": []}
                if "item-equipment-" in str(path)
                else {"xp_by_level": {str(i): (i - 1) * 100 for i in range(1, 201)}}
                if str(path).endswith("level-xp.json")
                else {"breeds": {}}
                if str(path).endswith("base-health.json")
                else {}
            ),
        ):
            registry.ready(901, first, True, lambda *_: ())
            registry.ready(901, second, True, lambda *_: ())
        for session in (first, second):
            registry.drain(901, session)
        runtime = RuntimeMessages(shared.fight, turn_duration_ms=100, clock=lambda: 0)
        runtime.turn_started()
        runtime.turn_deadline = 10
        runtime.deadline_turn = shared.fight.turn_id
        shared.runtime = runtime
        adapter = CombatSessionAdapter.__new__(CombatSessionAdapter)
        adapter.registry = registry
        return registry, shared, (first, second), live, adapter

    def test_due_turn_is_claimed_once_and_published_after_background_completion(self):
        registry, shared, sessions, _, adapter = self.setup_fight()
        work = DeferredWork()
        # Before the deadline, no work is queued and the caller gets the
        # existing (expired, error) boolean contract.
        from wakfu_server import combat_background_work

        with patch.object(combat_background_work, "NATIVE_WORK", work):
            self.assertEqual(
                adapter.expire_current_turn(901, sessions[0], now_ms=1), (False, None)
            )
        self.assertEqual(work.jobs, [])

        shared.runtime.turn_deadline = -1
        with patch.object(combat_background_work, "NATIVE_WORK", work):
            self.assertEqual(
                adapter.expire_current_turn(901, sessions[0], now_ms=2), (False, None)
            )
        self.assertEqual(len(work.jobs), 1)
        key, operation = work.jobs[0]
        self.assertEqual(key, ("turn-expiry", id(registry), 901))
        # A peer polling while the same expiry is queued cannot submit a second
        # native transition for this fight.
        self.assertEqual(
            registry.poll_expired_turn(901, sessions[1], now_ms=2, work=work),
            (False, None),
        )
        self.assertEqual(len(work.jobs), 1)
        self.assertIsNone(shared.ack.turn)
        self.assertEqual(shared.fight.turn_id, 1)

        operation()
        with patch.object(combat_background_work, "NATIVE_WORK", work):
            result = adapter.expire_current_turn(901, sessions[0], now_ms=3)
        self.assertEqual(result, (True, None))
        self.assertEqual(shared.fight.turn_id, 2)
        self.assertEqual(shared.ack.turn, 1)
        self.assertEqual(shared.runtime.awaiting_ack, 1)
        with patch.object(combat_background_work, "NATIVE_WORK", work):
            self.assertEqual(
                adapter.expire_current_turn(901, sessions[0], now_ms=4), (False, None)
            )
        published = []
        for session in sessions:
            batches = registry.drain(901, session)
            self.assertEqual(len(batches), 1)
            self.assertEqual(batches[0].sequence, shared.sequence)
            published.append(batches[0].packets)
        self.assertEqual(published[0], published[1])

    def test_busy_fight_lock_and_stale_sequence_never_block_or_apply_expiry(self):
        for stale_kind in ("sequence", "turn", "session"):
            with self.subTest(stale_kind=stale_kind):
                registry, shared, sessions, live, _ = self.setup_fight()
                work = DeferredWork()
                shared.runtime.turn_deadline = -1
                shared.lock = Lock()
                shared.lock.acquire()
                try:
                    self.assertEqual(
                        registry.poll_expired_turn(
                            901, sessions[0], now_ms=2, work=work
                        ),
                        (False, None),
                    )
                finally:
                    shared.lock.release()
                self.assertEqual(work.jobs, [])

                registry.poll_expired_turn(901, sessions[0], now_ms=2, work=work)
                self.assertEqual(len(work.jobs), 1)
                operation = work.jobs[0][1]
                turn = shared.fight.turn_id
                if stale_kind == "sequence":
                    shared.sequence += 1
                elif stale_kind == "turn":
                    shared.fight.turn_id += 1
                else:
                    live.remove(sessions[0])
                operation()
                self.assertEqual(
                    shared.fight.turn_id, turn if stale_kind != "turn" else turn + 1
                )
                self.assertIsNone(shared.ack.turn)
                if stale_kind == "session":
                    with self.assertRaisesRegex(ValueError, "Stale combat session"):
                        registry.poll_expired_turn(
                            901, sessions[0], now_ms=3, work=work
                        )
                else:
                    self.assertEqual(
                        registry.poll_expired_turn(
                            901, sessions[0], now_ms=3, work=work
                        ),
                        (False, None),
                    )
