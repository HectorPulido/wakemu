"""Advisory continuations require fresh roots and confirmed publications."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.planning import turn_continuation as continuation


FIRST = dict(type="cast", spellId=10, level=1, targetId=9, target=[3, 0, 0])
NEXT = dict(type="move", path=[[1, 0, 0]])


def runtime():
    return SimpleNamespace(
        fight=SimpleNamespace(
            id=7,
            current=SimpleNamespace(id=1, hp=30),
            turn_id=4,
            sequence=10,
            phase="active",
        ),
        awaiting_ack=None,
        pending=[],
    )


def bind(value, **overrides):
    options = dict(
        instance="encounter",
        catalog="c" * 64,
        policy_version="v1",
        policy={"weights": {}},
        source="source",
        root="root",
        request="request",
    )
    options.update(overrides)
    return continuation.binding(value, **options)


def decision(**overrides):
    value = dict(
        sourceKey="source",
        rootState="root",
        requestId="request",
        action=deepcopy(FIRST),
        plan=[deepcopy(FIRST), deepcopy(NEXT)],
    )
    value.update(overrides)
    return value


class TurnContinuationTests(unittest.TestCase):
    def published(self):
        value = runtime()
        holder = continuation.TurnContinuation(publication_required=True)
        holder.begin(value, publication_revision=1)
        source = bind(value)
        value.fight.sequence += 1
        holder.stage(decision(), source, value)
        holder.confirm(value, publication_revision=2)
        return value, holder

    def test_private_commit_does_not_publish_a_continuation(self):
        value = runtime()
        holder = continuation.TurnContinuation(publication_required=True)
        source = bind(value)
        value.fight.sequence += 1
        holder.stage(decision(), source, value)
        self.assertIsNotNone(holder.pending)
        self.assertIsNone(holder.published)
        holder.confirm(value, publication_revision=2)
        self.assertEqual(
            holder.proposal(value, bind(value)),
            dict(schema=continuation.SCHEMA, actions=[NEXT]),
        )

    def test_new_source_and_request_are_expected_after_publication(self):
        value, holder = self.published()
        fresh = bind(
            value, source="fresh source", root="fresh root", request="fresh request"
        )
        self.assertEqual(holder.proposal(value, fresh)["actions"], [NEXT])

    def test_changed_fight_actor_turn_revision_or_liveness_discards_hint(self):
        changes = [
            lambda value: setattr(value.fight, "id", 8),
            lambda value: setattr(value.fight.current, "id", 2),
            lambda value: setattr(value.fight, "turn_id", 5),
            lambda value: setattr(value.fight, "sequence", 12),
            lambda value: setattr(value.fight.current, "hp", 0),
            lambda value: setattr(value.fight, "phase", "complete"),
            lambda value: setattr(value, "awaiting_ack", 88),
            lambda value: setattr(value, "pending", [(42, b"pending")]),
        ]
        for change in changes:
            with self.subTest(change=change):
                value, holder = self.published()
                change(value)
                self.assertIsNone(holder.proposal(value, bind(value)))
                self.assertIsNone(holder.published)

    def test_changed_catalogue_policy_or_encounter_discards_hint(self):
        for override in (
            dict(instance="another"),
            dict(catalog="d" * 64),
            dict(policy_version="v2"),
            dict(policy={"weights": {"damage": 2}}),
        ):
            with self.subTest(override=override):
                value, holder = self.published()
                self.assertIsNone(holder.proposal(value, bind(value, **override)))

    def test_external_publication_revision_invalidates_even_without_fight_event(self):
        value, holder = self.published()
        holder.begin(value, publication_revision=3)
        self.assertIsNone(holder.proposal(value, bind(value)))

    def test_fresh_action_discards_unconfirmed_private_candidate(self):
        value, holder = self.published()
        source = bind(value)
        holder.stage(decision(), source, value)
        holder.begin(value, publication_revision=2)
        self.assertIsNone(holder.pending)
        self.assertIsNone(holder.proposal(value, source))

    def test_wrong_decision_provenance_or_plan_never_stages(self):
        for override in (
            dict(sourceKey="foreign"),
            dict(rootState="foreign"),
            dict(requestId="foreign"),
            dict(plan=[NEXT, FIRST]),
            dict(plan=[FIRST]),
            dict(plan=[FIRST, dict(type="end_turn")]),
            dict(plan=[FIRST, dict(type="move", path=[[True, 0, 0]])]),
        ):
            with self.subTest(override=override):
                value = runtime()
                holder = continuation.TurnContinuation()
                holder.stage(decision(**override), bind(value), value)
                holder.confirm(value)
                self.assertIsNone(holder.proposal(value, bind(value)))

    def test_failed_or_ack_interrupted_publication_never_confirms(self):
        for field, changed in (("awaiting_ack", 20), ("pending", [(20, b"pending")])):
            value = runtime()
            holder = continuation.TurnContinuation()
            holder.stage(decision(), bind(value), value)
            setattr(value, field, changed)
            holder.confirm(value)
            self.assertIsNone(holder.published)

    def test_a_different_published_action_cannot_confirm_the_staged_tail(self):
        value = runtime()
        holder = continuation.TurnContinuation()
        holder.stage(decision(), bind(value), value)
        holder.confirm(value, action=NEXT)
        self.assertIsNone(holder.published)

    def test_tail_is_bounded_and_both_inputs_and_outputs_are_copied(self):
        value = runtime()
        holder = continuation.TurnContinuation()
        proposed = decision(plan=[FIRST] + [deepcopy(NEXT) for _ in range(8)])
        holder.stage(proposed, bind(value), value)
        holder.confirm(value)
        proposed["plan"][1]["path"][0][0] = 99
        first = holder.proposal(value, bind(value))
        self.assertEqual(len(first["actions"]), 3)
        first["actions"][0]["path"][0][0] = 88
        self.assertEqual(holder.proposal(value, bind(value))["actions"][0], NEXT)

    def test_confirmed_hint_survives_a_private_runtime_copy_without_mutating_world(
        self,
    ):
        value, holder = self.published()
        copied = deepcopy(value)
        before = deepcopy(vars(copied.fight))
        self.assertIsNotNone(holder.proposal(copied, bind(copied)))
        self.assertEqual(vars(copied.fight), before)
        self.assertFalse(any("continuation" in name for name in vars(copied)))

    def test_scopes_restore_parent_and_discard_on_exception(self):
        self.assertIsNone(continuation.current())
        with continuation.scope(publication_required=True) as outer:
            with continuation.scope(reuse=True) as reused:
                self.assertIs(reused, outer)
            with self.assertRaisesRegex(RuntimeError, "failed"):
                with continuation.scope() as inner:
                    self.assertIsNot(inner, outer)
                    inner.published = {"uncommitted": True}
                    raise RuntimeError("failed")
            self.assertIs(continuation.current(), outer)
            self.assertIsNone(inner.published)
        self.assertIsNone(continuation.current())


class ContinuationSessionTests(unittest.TestCase):
    def test_real_envelope_only_exposes_confirmed_tail_after_a_fresh_source_guard(self):
        from test_native_session import make_runtime, StubOracle, StubTransport
        from wakfu_ai.bridge.world_bridge import NativeSession

        value = make_runtime()
        transport = StubTransport()

        def session():
            return NativeSession(
                StubOracle(value),
                transport,
                object(),
                policy={},
                policy_version="v1",
                fight_instance_id="encounter",
            )

        def envelope(native):
            root = dict(
                currentId=value.fight.current.id,
                turnId=value.fight.turn_id,
                stateRevision=value.fight.sequence,
            )
            with patch.object(native, "describe", return_value=root):
                return native.envelope()

        with continuation.scope(publication_required=True) as holder:
            holder.begin(value)
            original = session()
            self.assertNotIn("warmStart", envelope(original))
            value.fight.sequence += 1
            selected = decision(
                sourceKey=original.source,
                rootState=original.root,
                requestId=original.request_id,
            )
            holder.stage(selected, original.continuation_binding, value)
            self.assertNotIn("warmStart", envelope(session()))
            # Asking for another proposal before confirming is intentionally
            # conservative and drops the pending private candidate.
            holder.stage(selected, original.continuation_binding, value)
            holder.confirm(value)
            fresh = session()
            self.assertEqual(envelope(fresh)["warmStart"]["actions"], [NEXT])
            value.fight.current.hp -= 1
            with self.assertRaisesRegex(ValueError, "source changed"):
                envelope(fresh)

    def test_direct_turn_confirms_only_when_delivery_consumer_resumes(self):
        from test_native_turn import FakeOracle, runtime_fixture
        from wakfu_ai.native import native_turn

        value = runtime_fixture()
        seen, holders = [], []

        class Session:
            catalog = "c" * 64

            def __init__(self, oracle, transport, exporter, **options):
                self.continuation_binding = continuation.binding(
                    value,
                    instance=options["fight_instance_id"],
                    catalog=self.catalog,
                    policy_version=options["policy_version"],
                    policy=options["policy"],
                    source="source",
                    root="root",
                    request="request",
                )

            def decide(self, **kwargs):
                holder = continuation.current()
                holders.append(holder)
                seen.append(holder.proposal(value, self.continuation_binding))
                return (
                    decision()
                    if len(seen) == 1
                    else decision(action=dict(type="end_turn"), plan=[])
                )

            def guard(self):
                pass

        with patch.object(
            native_turn, "NativeOracle", return_value=FakeOracle(value)
        ), patch.object(native_turn, "NativeSession", Session):
            driver = native_turn.run_turn(
                value,
                characters={},
                monsters={},
                decks={},
                excluded_decks={},
                viewer_id=1,
                flags={},
                transport=object(),
                exporter=object(),
                policy={},
                policy_version="v1",
                stats_serializer=lambda *args: b"stats",
            )
            next(driver)
            self.assertIsNone(continuation.current())
            holder = holders[0]
            self.assertIsNone(holder.published)
            self.assertIsNotNone(holder.pending)
            next(driver)
            self.assertEqual(
                seen, [None, dict(schema=continuation.SCHEMA, actions=[NEXT])]
            )
            driver.close()
            self.assertIsNone(continuation.current())


if __name__ == "__main__":
    unittest.main()
