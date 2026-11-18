import struct
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "tools"))

# The driver imports its full acceptance-runner dependency graph at module
# load. This focused test exercises only its timeline loop and resume setup, so
# keep catalog/database-backed helpers out of the import path.
for name in (
    "tools.candidate_friendly_duel_socket_smoke",
    "tools.install_mission_bundle",
    "tools.quest_instance_combat_probe",
    "tools.regional_quest_tls_probe",
    "tools.rii_departure_probe",
):
    sys.modules[name] = types.ModuleType(name)
sys.modules["tools.candidate_friendly_duel_socket_smoke"].placement = lambda *_: None
sys.modules["tools.install_mission_bundle"].local_connection = lambda *_: None
sys.modules["tools.quest_instance_combat_probe"].fight_owned_room = lambda *_: None
regional = sys.modules["tools.regional_quest_tls_probe"]
regional.NativeRun = type("NativeRun", (), {})
regional.RegionalProbe = type("RegionalProbe", (), {})
rii = sys.modules["tools.rii_departure_probe"]
rii.ObservedPeer = type("ObservedPeer", (), {})
rii.login = lambda *_: None
import wakfu_server as wakfu

wakfu.dungeon_instances = types.SimpleNamespace()
wakfu.dungeon_runtime_config = types.SimpleNamespace()
store_module = types.ModuleType("wakfu_server.store")
store_module.Store = type("Store", (), {})
sys.modules["wakfu_server.store"] = store_module

import line2_rank23_native_tls_probe as probe


def native_timeline(fight_id, *, phase, turn, actor):
    """Build the real native timeline envelope used by core combat packets."""
    timeline = (
        struct.pack(">hiBq", phase, turn, 1, actor)
        + b"\x01"
        + struct.pack(">q", actor)
        + b"\x01"
        + struct.pack(">q", actor)
        + b"\x01"
        + struct.pack(">qh", actor, 1)
        + b"\x00\x00\x00"
    )
    return struct.pack(">ih", fight_id, len(timeline)) + timeline


def bootstrap_packet(fight_id, *, phase, turn, actor):
    timeline = native_timeline(fight_id, phase=phase, turn=turn, actor=actor)[6:]
    # Native 12847 body: fight/model/metadata, topology, timeline, leaders,
    # compact roster, followed by empty team/list/section collections.
    body = (
        struct.pack(">ibqqq", fight_id, 0, 0, 0, 0)
        + struct.pack(">i", 0)
        + struct.pack(">h", len(timeline))
        + timeline
        + struct.pack(">qqB", 0, 0, 1)
        + b"\x00"  # entities
        + b"\x00"  # teams
        + b"\x00\x00"  # two lists
        + struct.pack(">i", 0)  # sections
    )
    return body


class MockPeer:
    def __init__(self, records):
        self.records = records
        self.observation_lock = threading.Lock()
        self.sent = []

    def send(self, opcode, body=b""):
        self.sent.append((opcode, body))


class Line2Rank23RecoveryTests(unittest.TestCase):
    def test_resume_replays_login_bootstrap_and_witness_and_acks_once(self):
        fight_id, character_id = 876, 12345
        bootstrap = bootstrap_packet(fight_id, phase=1, turn=8, actor=character_id)
        witness = (
            struct.pack(">i", fight_id) + b"\x00" * 8 + struct.pack(">q", character_id)
        )
        unrelated = struct.pack(">i", fight_id) + b"\x00" * 16
        peer = MockPeer(
            [
                (7777, unrelated),
                (12847, bootstrap),
                (12502, witness),
            ]
        )
        run = object.__new__(probe.Rank23NativeRun)
        run.peer = peer
        run.fight_id = fight_id
        run.char = {"id": character_id}
        run.wire_cursor = 0  # resume must replay login records from their start
        run.native_global_turn = 0
        run.native_turn_actor = None
        run.native_timeline_phase = None
        run.native_timeline_members = frozenset()
        run.last_begin_identity = None
        run.last_acked_turn = None
        run.checkpoint = lambda: {"phase": "finished"}

        result = run.ready_for_input()

        self.assertEqual(result["phase"], "finished")
        self.assertEqual(peer.sent, [(13510, struct.pack(">i", 8))])
        self.assertEqual(run.wire_cursor, len(peer.records))

    def test_resuming_fight_uses_cursor_zero_before_its_recovery_request(self):
        peer = MockPeer([(12847, b"login bootstrap"), (12502, b"login witness")])
        captured = {}

        class CapturingRun:
            def __init__(self, *args):
                pass

            def ready_for_input(self):
                raise RuntimeError("stop after observing recovery setup")

        class StubProbe:
            store = object()
            account = {"id": 1}
            character = {"id": 2}
            receipt = {}

        instance = StubProbe()
        instance.peer = peer

        original_init = CapturingRun.__init__

        def capture_init(self, *args):
            original_init(self, *args)
            captured["runner"] = self

        CapturingRun.__init__ = capture_init
        with patch.object(probe, "Rank23NativeRun", CapturingRun), patch.object(
            probe, "_owned_class_spell_ids", return_value=(5562,)
        ), self.assertRaisesRegex(RuntimeError, "stop after observing"):
            probe._play_already_started_fight(instance, 99, 2, resume_existing=True)

        # Login's packets are already present before the recovery call. The
        # driver must begin consuming at zero, then request recovery.
        self.assertEqual(len(peer.records), 2)
        self.assertEqual(peer.sent, [(13332, struct.pack(">i", 99))])
        self.assertEqual(captured["runner"].wire_cursor, 0)


if __name__ == "__main__":
    unittest.main()
