"""Actual registry/outbox and socket-drainer audience isolation regressions."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

import test_combat_shared as shared_fixture
from wakfu_server.combat_shared import Session
from wakfu_server.fight_checkpoint_store import snapshot


class OwnedRecoverySpectatorDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = shared_fixture.SharedCombatTests()
        self.fixture.setUp()
        self.fixture.join()
        self.registry = self.fixture.registry
        self.shared = self.fixture.shared
        # These pure recipient tests do not claim native fighter initialization.
        # The real tactical producer can read an explicit empty property set.
        for actor in self.shared.fight.actors.values():
            actor.native_fight_properties = frozenset()
        for owner in (self.fixture.one, self.fixture.two):
            self.registry.drain(99, owner)
        self.sent = []
        self.observed = []

    def drain(self, owner):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        session = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        drain = deepcopy(
            next(
                node
                for node in ast.walk(session)
                if isinstance(node, ast.FunctionDef)
                and node.name == "drain_shared_combat"
            )
        )
        drain.decorator_list = []
        namespace = dict(
            combat_session=owner,
            fight=self.shared.fight,
            COMBAT_SESSIONS=SimpleNamespace(
                registry=self.registry,
                dispatch_connected=self.registry.dispatch_connected,
            ),
            WORLD=SimpleNamespace(
                send_batch_to=lambda identity, generation, packets: self.sent.append(
                    (identity, generation, packets)
                )
            ),
            connection=object(),
            service=object(),
            send_batch=lambda connection, service, packets: self.sent.append(
                (owner.character_id, owner.generation, packets)
            ),
            publish_external_marker=lambda shared: None,
            publish_spectator_state=lambda shared, packets: self.observed.append(
                packets
            ),
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[drain], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        namespace["drain_shared_combat"]()

    def replace_owner(self, bootstrap):
        self.fixture.live.remove(self.fixture.one)
        owner = Session(1, 10, "reconnected-owner", 1134, 0)
        self.fixture.live.add(owner)
        self.registry.takeover(99, owner, lambda *args: bootstrap)
        return owner

    def test_owned_recovery_birth_and_carriers_reach_only_recovered_owner(self):
        bootstrap = (
            (12847, b"owned-constructor"),
            (12613, b"original-tonel-birth"),
            (13420, struct.pack(">i", 99)),
            (13912, b"retained"),
            (12873, b"current-stats"),
            (12053, b"owned-recovery"),
            (12233, b"phase"),
            (12514, b"action"),
        )
        before = snapshot(self.shared.fight)
        owner = self.replace_owner(bootstrap)
        self.drain(owner)
        self.assertEqual(self.sent, [(10, owner.generation, bootstrap)])
        self.assertEqual(self.observed, [])
        self.assertEqual(snapshot(self.shared.fight), before)

    def test_genuine_identical_birth_after_recovery_remains_public_and_ordered(self):
        birth = (12613, b"same-exact-creation-bytes")
        owner = self.replace_owner(((12847, b"owned-constructor"), birth))
        # Recovery and actual gameplay coexist in one drain. No opcode/hash
        # blacklist may suppress a subsequent source-authored public event.
        public = (
            birth,
            (13420, struct.pack(">i", 99)),
            (13091, b"genuine-public-join"),
            (13482, b"current-turn"),
        )
        self.registry.publish(99, owner, public)
        self.drain(owner)
        self.assertEqual(
            self.sent,
            [
                (10, owner.generation, ((12847, b"owned-constructor"), birth) + public),
                (20, self.fixture.two.generation, public),
            ],
        )
        self.assertEqual(self.observed, [public])

    def test_join_bootstrap_does_not_replace_existing_public_join_delta(self):
        # Repeat a real Registry.join from its untouched placement fixture.
        self.fixture = shared_fixture.SharedCombatTests()
        self.fixture.setUp()
        self.registry, self.shared = self.fixture.registry, self.fixture.shared
        self.shared.fight.actors[10].native_fight_properties = frozenset()
        self.fixture.join()
        self.shared.fight.actors[20].native_fight_properties = frozenset()
        expected = tuple(
            packet for batch in self.shared.outboxes[1] for packet in batch.packets
        )
        self.assertEqual([opcode for opcode, _ in expected], [13091, 13652])
        self.drain(self.fixture.one)
        self.assertEqual(self.observed, [expected])
        joiner = next(
            packets for identity, generation, packets in self.sent if identity == 20
        )
        self.assertEqual(joiner, ((12847, b"owned-bootstrap"),))


if __name__ == "__main__":
    unittest.main()
