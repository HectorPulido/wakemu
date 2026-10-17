"""Independent evidence verification rejects routing and continuity contradictions."""
import copy
import unittest

from wakfu_server.combat_shared import Batch
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.combat_shared_reproduction import capture_shared_state
from wakfu_server.combat_delivery_reproduction import (
    verify_delivery_evidence,
    DeliveryEvidenceError,
)
import test_combat_shared_reproduction as shared_fixture


def session_fact(session):
    return dict(
        account_id=session.account_id,
        character_id=session.character_id,
        generation=session.generation,
        map_id=session.map_id,
        instance_id=session.instance_id,
    )


class DeliveryReproductionTests(unittest.TestCase):
    def fixture(self):
        source = shared_fixture.SharedReproductionTests()
        source.setUp()
        before = capture_shared_state(source.shared, registry=source.registry)
        source.shared.sequence = 1
        packets = ((13420, b"first-native-action"), (12873, b"second-native-action"))
        for queue in source.shared.outboxes.values():
            queue.append(Batch(1, packets))
        after = capture_shared_state(source.shared, registry=source.registry)
        streams, plan, attempts = [], [], []
        for index, session in enumerate((source.one, source.two)):
            fact = session_fact(session)
            bootstrap = dict(
                kind="bootstrap",
                packets=((12847, b"native-bootstrap"),),
                sequence=0,
                observation_id=1,
            )
            streams.append(
                dict(
                    session=fact,
                    bootstrap=bootstrap,
                    events=(bootstrap,),
                    bootstrap_missing=False,
                    history_gap=False,
                    history_evicted=False,
                    oversized=False,
                )
            )
            row = dict(session=fact, batches=(dict(sequence=1, packets=packets),))
            plan.append(row)
            attempts.append(
                dict(
                    row,
                    status="returned",
                    error=None,
                    observation_id=10 + index,
                    ordinal_boundary="serialized-registry-callback-completion",
                )
            )
        receipt = dict(
            schema="wakemu-shared-combat-incident-v1",
            before=before,
            after=after,
            delivery_correlation=dict(
                process_boot_id="actual-process", fight_id=88, before_sequence=0
            ),
            preceding_delivery_history=encode_state(
                dict(
                    schema="wakemu-combat-delivery-history-v1",
                    process_boot_id="actual-process",
                    fight_id=88,
                    streams=tuple(streams),
                )
            ),
        )
        sidecar = dict(
            schema="wakemu-combat-delivery-incident-v1",
            incident_id="actual-dispatch",
            process_boot_id="actual-process",
            fight_id=88,
            plan=encode_state(tuple(plan)),
            attempts=encode_state(tuple(attempts)),
            boundary="actual-delivery-callback-return-not-client-receipt",
            client_receipt_confirmed=False,
        )
        return receipt, sidecar, after

    def verify(self, receipt, sidecars, after):
        return verify_delivery_evidence(
            receipt,
            sidecars,
            expected_after=after,
            replay_outcome=dict(mailbox_matches=True),
        )

    def mutate_graph(self, sidecar, field, mutate):
        value = decode_state(sidecar[field])
        mutate(value)
        sidecar[field] = encode_state(value)

    def test_complete_exact_routing_qualifies_evidence_without_claiming_client_receipt(
        self,
    ):
        receipt, sidecar, after = self.fixture()
        original = copy.deepcopy((receipt, sidecar, after))
        result = self.verify(receipt, [sidecar], after)
        self.assertTrue(result["matches"], result["findings"])
        self.assertTrue(result["routing_matches"])
        self.assertTrue(result["shared_delivery_qualified"])
        self.assertEqual(result["expected_batch_attempts"], 2)
        self.assertEqual(result["observed_batch_attempts"], 2)
        self.assertFalse(result["client_receipt_confirmed"])
        self.assertFalse(result["client_reconstruction_verified"])
        self.assertEqual((receipt, sidecar, after), original)

    def test_first_failed_attempt_and_second_returned_are_preserved_as_observations(
        self,
    ):
        receipt, sidecar, after = self.fixture()
        self.mutate_graph(
            sidecar,
            "attempts",
            lambda rows: rows[0].update(
                status="raised",
                error=dict(
                    type="builtins.OSError",
                    message="socket failed",
                    message_truncated=False,
                ),
            ),
        )
        result = self.verify(receipt, [sidecar], after)
        self.assertTrue(result["shared_delivery_qualified"], result["findings"])
        self.assertEqual(
            result["attempt_failures"],
            [dict(path="sidecars[0].attempts[0]", exception_type="builtins.OSError")],
        )
        self.assertEqual(result["observed_batch_attempts"], 2)
        self.assertFalse(result["client_receipt_confirmed"])

    def test_changed_bytes_packet_order_and_attempt_order_cannot_qualify(self):
        for mutate in (
            lambda rows: rows[0]["batches"][0].update(packets=((13420, b"changed"),)),
            lambda rows: rows[0]["batches"][0].update(
                packets=tuple(reversed(rows[0]["batches"][0]["packets"]))
            ),
        ):
            receipt, sidecar, after = self.fixture()
            self.mutate_graph(sidecar, "attempts", mutate)
            result = self.verify(receipt, [sidecar], after)
            self.assertFalse(result["shared_delivery_qualified"])
            self.assertFalse(result["routing_matches"])
        receipt, sidecar, after = self.fixture()
        sidecar["attempts"] = encode_state(
            tuple(reversed(decode_state(sidecar["attempts"])))
        )
        result = self.verify(receipt, [sidecar], after)
        self.assertFalse(result["dispatch_qualified"])
        self.assertIn(
            "dispatch_recipient_attempt_order_differs",
            [item["code"] for item in result["findings"]],
        )

    def test_missing_duplicate_and_unplanned_attempts_are_detected(self):
        for mode in ("missing", "duplicate", "unplanned", "sidecar-duplicate"):
            with self.subTest(mode=mode):
                receipt, sidecar, after = self.fixture()
                rows = decode_state(sidecar["attempts"])
                if mode == "missing":
                    rows = rows[:1]
                elif mode == "duplicate":
                    rows = rows + (copy.deepcopy(rows[0]),)
                elif mode == "unplanned":
                    extra = copy.deepcopy(rows[0])
                    extra["session"]["account_id"] = 99
                    rows = rows + (extra,)
                sidecar["attempts"] = encode_state(rows)
                sidecars = (
                    [sidecar, sidecar] if mode == "sidecar-duplicate" else [sidecar]
                )
                result = self.verify(receipt, sidecars, after)
                self.assertFalse(result["shared_delivery_qualified"])
                self.assertFalse(result["matches"])

    def test_other_boot_fight_or_generation_are_not_accepted(self):
        for field, value in (
            ("process_boot_id", "another-process"),
            ("fight_id", 99),
            ("generation", "reconnected"),
        ):
            with self.subTest(field=field):
                receipt, sidecar, after = self.fixture()
                if field == "generation":
                    self.mutate_graph(
                        sidecar,
                        "plan",
                        lambda rows: rows[0]["session"].update(generation=value),
                    )
                    self.mutate_graph(
                        sidecar,
                        "attempts",
                        lambda rows: rows[0]["session"].update(generation=value),
                    )
                else:
                    sidecar[field] = value
                result = self.verify(receipt, [sidecar], after)
                self.assertFalse(result["shared_delivery_qualified"])
                self.assertFalse(result["routing_matches"])

    def test_missing_bootstrap_eviction_and_gap_remain_unqualified(self):
        for mode in ("missing", "evicted", "gap", "no-history"):
            with self.subTest(mode=mode):
                receipt, sidecar, after = self.fixture()
                history = decode_state(receipt["preceding_delivery_history"])
                stream = history["streams"][0]
                if mode == "missing":
                    stream.update(bootstrap=None, bootstrap_missing=True)
                elif mode == "evicted":
                    stream["history_evicted"] = True
                elif mode == "gap":
                    stream["history_gap"] = True
                receipt["preceding_delivery_history"] = (
                    None if mode == "no-history" else encode_state(history)
                )
                result = self.verify(receipt, [sidecar], after)
                self.assertTrue(result["routing_matches"], result["findings"])
                self.assertFalse(result["bootstrap_qualified"])
                self.assertFalse(result["shared_delivery_qualified"])

    def test_recorded_self_consistency_does_not_claim_actual_replay(self):
        receipt, sidecar, after = self.fixture()
        result = verify_delivery_evidence(receipt, [sidecar])
        self.assertTrue(result["routing_matches"])
        self.assertFalse(result["replay_mailboxes_compared"])
        self.assertFalse(result["shared_delivery_qualified"])
        self.assertEqual(
            result["expected_state_authority"], "recorded-after-self-consistency-only"
        )
        state = decode_state(after["graph"])
        state["outboxes"][1][0].packets = ((13420, b"replay-changed"),)
        changed_after = dict(after, graph=encode_state(state))
        result = self.verify(receipt, [sidecar], changed_after)
        self.assertFalse(result["mailbox_state_matches"])
        self.assertFalse(result["shared_delivery_qualified"])

    def test_history_enqueue_drain_discontinuity_is_independently_detected(self):
        receipt, sidecar, after = self.fixture()
        history = decode_state(receipt["preceding_delivery_history"])
        stream = history["streams"][0]
        stream["events"] += (
            dict(
                kind="drain",
                observation_id=2,
                batches=(dict(sequence=0, packets=((12847, b"never-enqueued"),)),),
            ),
        )
        receipt["preceding_delivery_history"] = encode_state(history)
        result = self.verify(receipt, [sidecar], after)
        self.assertFalse(result["bootstrap_qualified"])
        self.assertIn(
            "history_drain_without_matching_enqueue",
            [item["code"] for item in result["findings"]],
        )

    def test_unknown_schemas_and_malformed_typed_graphs_raise_infrastructure_error(
        self,
    ):
        receipt, sidecar, after = self.fixture()
        for broken in (
            dict(sidecar, schema="other"),
            dict(sidecar, attempts={"schema": "pickle"}),
        ):
            with self.assertRaises(DeliveryEvidenceError):
                self.verify(receipt, [broken], after)
        with self.assertRaises(DeliveryEvidenceError):
            verify_delivery_evidence(dict(receipt, schema="other"), [])

    def test_no_new_mailbox_batch_is_explicitly_not_a_delivery_claim(self):
        receipt, sidecar, after = self.fixture()
        receipt["after"] = receipt["before"]
        result = self.verify(receipt, [], receipt["before"])
        self.assertEqual(result["expected_batch_attempts"], 0)
        self.assertIsNone(result["routing_matches"])
        self.assertFalse(result["dispatch_qualified"])
        self.assertFalse(result["shared_delivery_qualified"])

    def prior_fixture(self):
        receipt, sidecar, after = self.fixture()
        prior = dict(sequence=0, packets=((12847, b"previously-queued"),))
        for phase in ("before", "after"):
            state = decode_state(receipt[phase]["graph"])
            for account, queue in state["outboxes"].items():
                state["outboxes"][account] = (
                    Batch(prior["sequence"], prior["packets"]),
                ) + queue
            receipt[phase] = dict(receipt[phase], graph=encode_state(state))
        for field in ("plan", "attempts"):
            rows = decode_state(sidecar[field])
            for row in rows:
                row["batches"] = (copy.deepcopy(prior),) + row["batches"]
            sidecar[field] = encode_state(rows)
        return receipt, sidecar, receipt["after"]

    def test_correct_target_plus_unknown_future_batch_cannot_qualify(self):
        receipt, sidecar, after = self.fixture()
        for field in ("plan", "attempts"):
            self.mutate_graph(
                sidecar,
                field,
                lambda rows: rows[0].update(
                    batches=rows[0]["batches"]
                    + (dict(sequence=999, packets=((13420, b"unknown-future"),)),)
                ),
            )
        result = self.verify(receipt, [sidecar], after)
        self.assertFalse(result["shared_delivery_qualified"])
        self.assertIn(
            "attempted_unknown_mailbox_batch",
            [item["code"] for item in result["findings"]],
        )

    def test_changed_prior_bytes_in_matching_plan_and_attempt_cannot_qualify(self):
        receipt, sidecar, after = self.prior_fixture()
        for field in ("plan", "attempts"):
            self.mutate_graph(
                sidecar,
                field,
                lambda rows: rows[0]["batches"][0].update(
                    packets=((12847, b"tampered-prior"),)
                ),
            )
        result = self.verify(receipt, [sidecar], after)
        self.assertFalse(result["shared_delivery_qualified"])
        self.assertIn(
            "attempted_mailbox_batch_bytes_differ",
            [item["code"] for item in result["findings"]],
        )

    def test_matching_plan_and_attempt_reversed_batch_order_cannot_qualify(self):
        receipt, sidecar, after = self.prior_fixture()
        for field in ("plan", "attempts"):
            self.mutate_graph(
                sidecar,
                field,
                lambda rows: rows[0].update(
                    batches=tuple(reversed(rows[0]["batches"]))
                ),
            )
        result = self.verify(receipt, [sidecar], after)
        self.assertFalse(result["shared_delivery_qualified"])
        self.assertIn(
            "attempted_mailbox_batch_order_differs",
            [item["code"] for item in result["findings"]],
        )

    def test_duplicate_prior_batch_cannot_qualify(self):
        receipt, sidecar, after = self.prior_fixture()
        for field in ("plan", "attempts"):
            self.mutate_graph(
                sidecar,
                field,
                lambda rows: rows[0].update(
                    batches=(rows[0]["batches"][0],) + rows[0]["batches"]
                ),
            )
        result = self.verify(receipt, [sidecar], after)
        self.assertFalse(result["shared_delivery_qualified"])
        self.assertIn(
            "attempted_duplicate_mailbox_batch",
            [item["code"] for item in result["findings"]],
        )

    def test_exact_prior_batch_and_contiguous_split_dispatch_remain_valid(self):
        receipt, sidecar, after = self.prior_fixture()
        result = self.verify(receipt, [sidecar], after)
        self.assertTrue(result["shared_delivery_qualified"], result["findings"])
        first, second = copy.deepcopy(sidecar), copy.deepcopy(sidecar)
        first["incident_id"], second["incident_id"] = (
            "prior-dispatch",
            "target-dispatch",
        )
        for selected, index in ((first, 0), (second, 1)):
            for field in ("plan", "attempts"):
                self.mutate_graph(
                    selected,
                    field,
                    lambda rows, index=index: [
                        row.update(batches=(row["batches"][index],)) for row in rows
                    ],
                )
                if field == "attempts":
                    self.mutate_graph(
                        selected,
                        field,
                        lambda rows, index=index: [
                            row.update(
                                observation_id=row["observation_id"] + index * 100
                            )
                            for row in rows
                        ],
                    )
        result = self.verify(receipt, [first, second], after)
        self.assertTrue(result["shared_delivery_qualified"], result["findings"])

    def split_dispatch_fixture(self):
        receipt, sidecar, after = self.prior_fixture()
        first, second = copy.deepcopy(sidecar), copy.deepcopy(sidecar)
        for selected, batch_index in ((first, 0), (second, 1)):
            selected["incident_id"] += str(batch_index)
            for field in ("plan", "attempts"):
                rows = decode_state(selected[field])
                for row in rows:
                    row["batches"] = (row["batches"][batch_index],)
                    if field == "attempts":
                        row["observation_id"] += batch_index * 100
                selected[field] = encode_state(rows)
        return receipt, first, second, after

    def test_split_sidecars_input_order_is_not_send_order_authority(self):
        receipt, first, second, after = self.split_dispatch_fixture()
        result = self.verify(receipt, [second, first], after)
        self.assertTrue(result["shared_delivery_qualified"], result["findings"])
        self.assertTrue(result["dispatch_order_qualified"])

    def test_actual_completion_ordinals_inverted_relative_to_queue_are_rejected(self):
        receipt, first, second, after = self.split_dispatch_fixture()
        self.mutate_graph(
            first,
            "attempts",
            lambda rows: [
                row.update(observation_id=row["observation_id"] + 1000) for row in rows
            ],
        )
        result = self.verify(receipt, [first, second], after)
        self.assertFalse(result["shared_delivery_qualified"])
        self.assertIn(
            "cross_dispatch_mailbox_order_differs",
            [item["code"] for item in result["findings"]],
        )

    def test_legacy_missing_ordinals_and_nonserialized_boundary_are_unknown(self):
        for mode in ("missing", "unknown-boundary"):
            with self.subTest(mode=mode):
                receipt, sidecar, after = self.fixture()
                rows = decode_state(sidecar["attempts"])
                for row in rows:
                    if mode == "missing":
                        row.pop("observation_id")
                    else:
                        row[
                            "ordinal_boundary"
                        ] = "callback-completion-without-invocation-order"
                sidecar["attempts"] = encode_state(rows)
                result = self.verify(receipt, [sidecar], after)
                self.assertTrue(result["routing_matches"], result["findings"])
                self.assertFalse(result["dispatch_order_qualified"])
                self.assertFalse(result["shared_delivery_qualified"])

    def test_duplicate_stream_ordinals_are_rejected_across_distinct_dispatches(self):
        receipt, first, second, after = self.split_dispatch_fixture()
        self.mutate_graph(
            second,
            "attempts",
            lambda rows: [
                row.update(observation_id=row["observation_id"] - 100) for row in rows
            ],
        )
        result = self.verify(receipt, [first, second], after)
        self.assertFalse(result["shared_delivery_qualified"])
        self.assertIn(
            "duplicate_stream_attempt_ordinal",
            [item["code"] for item in result["findings"]],
        )


if __name__ == "__main__":
    unittest.main()
