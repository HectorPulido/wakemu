"""Real retained runtime/codec tests; bounded fixtures, no monster qualification."""
from dataclasses import asdict
import json
import re
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from wakfu_server.combat_retained_runtime import NativeRetainedRuntime, group_payload
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_state_carrier import state_carrier_payload
from wakfu_server.combat_state_ledger import RunningState, StateLedger
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_native_container import capture_owned_state_container
from wakfu_server.combat_running_container import running_container_scope

from wakfu_server import combat_state_cleanup as module

FIXTURE = json.loads(
    (
        Path(__file__).resolve().parent / "fixtures/native_state_cleanup_982.json"
    ).read_text()
)


class CleanupRuntimeTests(unittest.TestCase):
    def fixture(self, *, second_flag=False, container_kind=25, container_identity=500):
        ledger = StateLedger(7)
        first = RunningState(
            100, 1144, 1, 7, 7, -1, "target", False, (), -1, True, None
        )
        second = RunningState(
            200, 1144, 1, 7, 7, -1, "target", False, (), -1, True, None
        )
        ledger._entries = (first, second)
        actor = Actor(7, 0, (0, 0, 0), 50, 6, 3, 10, 1, 3, True)
        opponent = Actor(-7, 1, (1, 0, 0), 50, 6, 3, 5, 1)
        fight = Fight(
            12,
            [actor, opponent],
            {actor.position, opponent.position},
            {0: {actor.position}, 1: {opponent.position}},
        )
        actor.state_ledger = ledger
        events, packets = fight.events, []

        def record(entry):
            fight.native_retained_records[entry.uid] = asdict(entry)
            fight.native_retained_order.append(entry.uid)

        for state, kind, identity, flag in (
            (first, container_kind, container_identity, False),
            (second, None, None, second_flag),
        ):
            with running_container_scope(
                {"container_present": kind is not None, "container_type": kind},
                identity,
            ):
                payload = state_carrier_payload(
                    uid=state.uid,
                    base_uid=state.uid,
                    caster_id=7,
                    target_id=7,
                    state_id=state.reference,
                    level=state.level,
                    native_turn_clock=-1,
                    native_realtime_remaining=-1,
                    flag18=flag,
                )
            fight.state_wire_payloads[state.uid] = payload.hex()
            record(
                RetainedEffect(
                    state.uid,
                    7,
                    310,
                    -1,
                    manager_id=7,
                    container_present=kind is not None,
                    container_type=kind,
                    container_id=identity,
                )
            )
        packed = (1144 << 16) | 1
        for uid, kind, identity, owner in (
            (90, container_kind, container_identity, None),
            (101, 1, packed, 100),
            (201, 1, packed, 200),
            (91, 11, 600, None),
        ):
            payload = group_payload(
                uid=uid,
                base_uid=uid,
                generic_effect=350552,
                caster_id=7,
                target_id=7,
                cell=(0, 0, 0),
                container_type=kind,
                container_id=identity,
                timing_payload=b"",
            )
            fight.native_owned_group_effects[uid] = dict(
                target_id=7, effect_class=949, state_uid=owner, payload=payload.hex()
            )
            record(
                RetainedEffect(
                    uid,
                    7,
                    949,
                    350552,
                    owner_uid=owner,
                    manager_id=7,
                    container_present=True,
                    container_type=kind,
                    container_id=identity,
                )
            )
        capture_owned_state_container(fight, 100)
        capture_owned_state_container(fight, 200)
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=3,
            timing=None,
            metadata={},
        )
        retention.stat_handler = SimpleNamespace(fight=fight)
        return fight, retention, packets, events

    def test_native_container_and_shared_state_qf_groups_use_real_removal_codecs(self):
        fight, retention, packets, events = self.fixture()
        module.RetainedCleanupAuthority(retention, 7).execute()
        self.assertEqual(
            [struct.unpack(">q", packet[-8:])[0] for _, packet in packets],
            [90, 101, 201, 100],
        )
        self.assertTrue(all(opcode == 13560 for opcode, _ in packets))
        self.assertEqual(set(fight.native_retained_records), {200, 91})
        self.assertEqual(
            [state.uid for state in fight.actors[7].state_ledger.entries], [200]
        )
        self.assertEqual(fight.actors[7].hp, 50)
        self.assertFalse(any(event["kind"] == "1046" for event in events))

    def test_second_phase_reads_owned_additional18_and_preserves_active_spell(self):
        fight, retention, packets, _ = self.fixture(second_flag=True)
        module.RetainedCleanupAuthority(retention, 7).execute()
        self.assertEqual(
            [struct.unpack(">q", packet[-8:])[0] for _, packet in packets],
            [90, 101, 201, 100, 200],
        )
        self.assertEqual(set(fight.native_retained_records), {91})
        native = FIXTURE["native_trace"]
        self.assertEqual(
            [int(uid) for uid in re.findall(r"remove:(\d+)", native["trace"])],
            [struct.unpack(">q", packet[-8:])[0] for _, packet in packets],
        )
        self.assertEqual(native["remaining"], "[91]")

    def test_malformed_registered_state_wire_rejects_before_first_packet(self):
        fight, retention, packets, _ = self.fixture()
        fight.state_wire_payloads[200] = state_carrier_payload(
            uid=200,
            base_uid=200,
            caster_id=7,
            target_id=7,
            state_id=1145,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=-1,
        ).hex()
        before = dict(fight.native_retained_records)
        with self.assertRaisesRegex(ValueError, "operand differs"):
            module.RetainedCleanupAuthority(retention, 7).execute()
        self.assertEqual(packets, [])
        self.assertEqual(fight.native_retained_records, before)

    def test_forged_passive_container_metadata_rejects_before_mutation(self):
        fight, retention, packets, _ = self.fixture()
        fight.native_retained_records[91]["container_type"] = 25
        with self.assertRaisesRegex(ValueError, "PL key differs"):
            module.RetainedCleanupAuthority(retention, 7).execute()
        self.assertEqual(packets, [])
        self.assertIn(100, fight.state_wire_payloads)
        self.assertIn(91, fight.native_owned_group_effects)

    def test_handler_uses_actual_sealed982_record_and_real_runner_identity(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_runner_callbacks import runner_value_scope

        fight, retention, packets, _ = self.fixture(second_flag=True)
        effect = FIXTURE["effect110340"]["record"]
        phases, observed = [], []

        class Lifecycle:
            def phase(self, effect, invocation, **kwargs):
                phases.append(
                    (kwargs["channel"], kwargs["uid"], kwargs["runner_modifier"].family)
                )

        handler = module.NativeStateCleanupHandler(
            retention,
            allocate_uid=lambda: 999,
            rng=lambda: 0.5,
            event_lifecycle=Lifecycle(),
        )
        with runner_value_scope(
            lambda invocation, value: observed.append(value)
        ) as observer:
            invocation = EffectInvocation(
                110340, 1, 7, 7, (0, 0, 0), native_value_scope=observer
            )
            invocation = handler.prepare(effect, {"parameters": []}, invocation)
            self.assertTrue(handler(effect, {"parameters": []}, invocation))
        self.assertEqual(
            phases, [(1, 999, 982), (2, 999, 982), (3, 999, 982), (4, 999, 982)]
        )
        self.assertEqual(observed, [0])
        self.assertEqual(handler.prepared, {})
        self.assertEqual(set(fight.native_retained_records), {91})
        self.assertEqual(len(packets), 5)

    def test_actual_fight_transaction_rejects_after_cleanup_without_mutating_original(
        self,
    ):
        from copy import deepcopy
        from wakfu_server.combat_effect_dispatch import run_effect_transaction

        fight, _, _, _ = self.fixture(second_flag=True)
        before = deepcopy(
            (
                fight.state_wire_payloads,
                fight.native_retained_records,
                fight.native_owned_group_effects,
                fight.native_owned_state_containers,
                fight.actors[7].state_ledger.entries,
                fight.events,
            )
        )
        actor, ledger = fight.actors[7], fight.actors[7].state_ledger

        class FailingDispatcher:
            def __init__(self, preview):
                self.preview = preview

            def execute(self, invocation):
                packets = []
                retention = NativeRetainedRuntime(
                    self.preview,
                    packets,
                    plan={"native_retained_container": {"present": False}},
                    state_catalog={},
                    action_id=3,
                    timing=None,
                    metadata={},
                )
                retention.stat_handler = SimpleNamespace(fight=self.preview)
                module.RetainedCleanupAuthority(retention, 7).execute()
                self_check.assertEqual(len(packets), 5)
                raise ValueError("publication rejected after actual cleanup")

        self_check = self
        with self.assertRaisesRegex(ValueError, "publication rejected"):
            run_effect_transaction(fight, [object()], FailingDispatcher)
        self.assertIs(fight.actors[7], actor)
        self.assertIs(actor.state_ledger, ledger)
        self.assertEqual(
            (
                fight.state_wire_payloads,
                fight.native_retained_records,
                fight.native_owned_group_effects,
                fight.native_owned_state_containers,
                fight.actors[7].state_ledger.entries,
                fight.events,
            ),
            before,
        )

    def test_real_native_hash_fixture_matches_actual_hashset_order(self):
        receipt = FIXTURE["native_identity_hashset"]
        entries = tuple(SimpleNamespace(uid=row["uid"]) for row in receipt["states"])
        hashes = {row["uid"]: row["identityHash"] for row in receipt["states"]}
        actual = module.identity_hashset_order(entries, lambda entry: hashes[entry.uid])
        self.assertEqual([entries.index(entry) for entry in actual], receipt["order"])
        self.assertTrue(
            all(row["hash"] == row["identityHash"] for row in receipt["states"])
        )

    def test_multiple_flagged_states_without_native_identity_hash_fail_closed(self):
        entries = (SimpleNamespace(uid=1), SimpleNamespace(uid=2))
        with self.assertRaisesRegex(ValueError, "native identity hashes"):
            module.identity_hashset_order(entries, None)


if __name__ == "__main__":
    unittest.main()
