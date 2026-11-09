"""Advisory continuations require fresh roots and confirmed publications."""
from copy import deepcopy
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.planning import (
    turn_continuation as continuation,
)


FIRST = dict(type="cast", spellId=10, level=1, targetId=9, target=[3, 0, 0])
NEXT = dict(type="move", path=[[1, 0, 0]])


def runtime():
    return SimpleNamespace(
        fight=SimpleNamespace(
            id=7,
            current=SimpleNamespace(id=1, hp=30, position=(0, 0, 0), team=1),
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


def movement_packet(fight_id, actor_id, points):
    body = struct.pack(">iiiqBB", fight_id, 1, -1, actor_id, 0, 0)
    return (
        13624,
        body + b"".join(struct.pack(">iih", *point) for point in points),
    )


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

    def test_published_zigzag_records_origin_and_intermediate_cells_from_wire(self):
        value = runtime()
        origin, middle, endpoint = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        holder = continuation.TurnContinuation(publication_required=True)
        holder.begin(value, publication_revision=1)
        value.fight.current.position = endpoint
        holder.record_published_action(
            value,
            {"type": "move", "path": [list(middle), list(endpoint)]},
            packets=(
                movement_packet(
                    value.fight.id, value.fight.current.id, [origin, middle, endpoint]
                ),
            ),
        )

        cells, actions = holder.confirmed_actions(value)
        self.assertEqual(cells, {origin, middle, endpoint})
        self.assertEqual(actions, [{"type": "move", "target": list(endpoint)}])

    def test_truncated_move_records_only_cells_in_published_packet(self):
        value = runtime()
        origin, published, truncated_tail = (0, 0, 0), (1, 0, 0), (2, 0, 0)
        holder = continuation.TurnContinuation(publication_required=True)
        holder.begin(value, publication_revision=1)
        value.fight.current.position = published
        holder.record_published_action(
            value,
            {"type": "move", "path": [list(published), list(truncated_tail)]},
            packets=(
                movement_packet(
                    value.fight.id, value.fight.current.id, [origin, published]
                ),
            ),
        )

        cells, actions = holder.confirmed_actions(value)
        self.assertEqual(cells, {origin, published})
        self.assertNotIn(truncated_tail, cells)
        self.assertEqual(actions, [{"type": "move", "target": list(published)}])

    def test_unpublished_candidate_does_not_enter_confirmed_movement_history(self):
        value = runtime()
        holder = continuation.TurnContinuation(publication_required=True)
        holder.begin(value, publication_revision=1)
        # Registry publication failed: world_shared must not call
        # record_published_action for the still-private move candidate.
        cells, actions = holder.confirmed_actions(value)
        self.assertEqual(cells, {(0, 0, 0)})
        self.assertEqual(actions, [])

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
