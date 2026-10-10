"""Pure registration identity tests without importing the native game engine."""
from copy import deepcopy
import hashlib
import sys
from pathlib import Path
import unittest

_AI_SERVICE = Path(__file__).resolve().parents[1]
if str(_AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(_AI_SERVICE))

from wakfu_ai.context.native_context import encode_bytes
from wakfu_ai.context.native_fingerprint import fingerprint as complete_fingerprint
from wakfu_ai.bridge.world_bridge import NativeSession


class IdentityOracle:
    def __init__(self, *, split_authority_alias=False):
        self.flags = {"futureFlag": {"binary": b"\x00\xff"}}
        self.split_authority_alias = split_authority_alias
        self.identity_calls = 0
        self.transition_identity_calls = 0

    def authorities(self, runtime):
        fight = runtime["fight"]
        if self.split_authority_alias:
            fight = deepcopy(fight)
        return {"fightAlias": fight, "futureAuthority": {"kept": True}}

    def complete_state_bytes(self, runtime):
        return encode_bytes(
            dict(
                runtime=runtime, authorities=self.authorities(runtime), flags=self.flags
            )
        )

    def complete_transition_bytes(self, runtime, transition):
        return encode_bytes(
            dict(
                runtime=runtime,
                authorities=self.authorities(runtime),
                flags=self.flags,
                transition=transition,
            )
        )

    def state_identity(self, runtime):
        self.identity_calls += 1
        return complete_fingerprint(
            dict(
                runtime=runtime, authorities=self.authorities(runtime), flags=self.flags
            )
        )


class CapturingTransport:
    native_graph_parts = False

    def __init__(self):
        self.payloads = {}

    def instance_bytes(self, payload):
        digest = hashlib.sha256(payload).hexdigest()
        self.payloads[digest] = payload
        return digest


def runtime_fixture():
    fight = {"actors": [{"id": -20, "futureActorField": b"retained"}]}
    fight["self"] = fight
    return {
        "fight": fight,
        "fightAlias": fight,
        "futureRuntimeField": {"version": 2, "bytes": b"\x01\xfe"},
    }


def registration(oracle, runtime, *, transition=None):
    session = object.__new__(NativeSession)
    session.oracle = oracle
    session.transport = CapturingTransport()
    session.states = {}
    session.state_identities = {}
    session.preparation_stages_ms = {}
    session.native_query_metrics = {}
    digest = session.register(runtime, transition=transition)
    return session, digest


class NativeRegistrationIdentityTests(unittest.TestCase):
    def test_root_register_preserves_full_identity_and_serialized_graph(self):
        oracle = IdentityOracle()
        runtime = runtime_fixture()
        session, digest = registration(oracle, runtime)

        payload = session.transport.payloads[digest]
        expected_identity = complete_fingerprint(
            dict(
                runtime=runtime,
                authorities=oracle.authorities(runtime),
                flags=oracle.flags,
            )
        )
        self.assertEqual(session.state_identities[digest], expected_identity)
        self.assertEqual(oracle.identity_calls, 1)
        self.assertIs(session.states[digest], runtime)
        self.assertEqual(
            payload,
            encode_bytes(
                dict(
                    runtime=runtime,
                    authorities=oracle.authorities(runtime),
                    flags=oracle.flags,
                )
            ),
        )

    def test_clone_with_preserved_aliases_has_same_identity(self):
        oracle = IdentityOracle()
        original = runtime_fixture()
        clone = deepcopy(original)
        first, first_digest = registration(oracle, original)
        second, second_digest = registration(oracle, clone)

        self.assertEqual(
            first.state_identities[first_digest], second.state_identities[second_digest]
        )
        self.assertEqual(
            first.transport.payloads[first_digest],
            second.transport.payloads[second_digest],
        )

    def test_future_field_and_alias_topology_change_identity(self):
        base = runtime_fixture()
        changed_field = deepcopy(base)
        changed_field["futureRuntimeField"]["version"] += 1
        broken_alias = deepcopy(base)
        broken_alias["fightAlias"] = deepcopy(broken_alias["fight"])

        base_session, base_digest = registration(IdentityOracle(), base)
        changed_session, changed_digest = registration(IdentityOracle(), changed_field)
        alias_session, alias_digest = registration(IdentityOracle(), broken_alias)
        split_session, split_digest = registration(
            IdentityOracle(split_authority_alias=True), base
        )
        identities = [
            base_session.state_identities[base_digest],
            changed_session.state_identities[changed_digest],
            alias_session.state_identities[alias_digest],
            split_session.state_identities[split_digest],
        ]
        self.assertEqual(len(set(identities)), 4)

    def test_transition_receipts_keep_existing_runtime_identity_semantics(self):
        oracle = IdentityOracle()
        runtime = runtime_fixture()
        root, root_digest = registration(oracle, runtime)
        first, first_digest = registration(
            oracle, runtime, transition={"packets": [b"receipt-one"]}
        )
        second, second_digest = registration(
            oracle, deepcopy(runtime), transition={"packets": [b"receipt-two"]}
        )

        self.assertNotEqual(first_digest, second_digest)
        self.assertEqual(
            root.state_identities[root_digest], first.state_identities[first_digest]
        )
        self.assertEqual(
            first.state_identities[first_digest], second.state_identities[second_digest]
        )
        self.assertEqual(oracle.identity_calls, 3)


if __name__ == "__main__":
    unittest.main()
