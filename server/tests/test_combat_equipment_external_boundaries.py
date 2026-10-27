"""Compound accepted-boundary regression; native effect arithmetic is separate."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_equipment_external_events as external
from wakfu_server.combat_equipment_tackle_events import deliver_tackle_boundary
from wakfu_server.combat_native_events import subscription_selection
import test_combat_tackle_movement as tackle_fixture


class EquipmentExternalBoundaryTests(unittest.TestCase):
    def test_actual_paid_fei_roles_failed_preview_retry_and_completed_round_once(self):
        fight, mover, locker = tackle_fixture.NativeTackleMovementTests().fixture()
        # The miniature replay harness applies actual Qi subscription selection;
        # it deliberately does not claim to execute native armor/MP arithmetic.
        effects = {
            11: dict(manager=mover.id, event=1032, reverse=False),
            12: dict(manager=locker.id, event=1032, reverse=True),
            13: dict(manager=mover.id, event=1032, reverse=True),
            14: dict(manager=locker.id, event=1032, reverse=False),
            15: dict(manager=mover.id, event=1032, reverse=False),
            21: dict(manager=mover.id, event=1004, reverse=False),
        }
        eligible = frozenset((11, 12, 13, 14, 21))  # UID15 is unrelated custody.
        committed_outbox = []

        def dispatcher(current, outbox):
            def replay(source, *, authority, eligible_uids):
                source.validate()
                for uid, row in effects.items():
                    if (
                        row["manager"] != source.manager_actor_id
                        or uid not in eligible_uids
                    ):
                        continue
                    masks = [None] * 7
                    masks[5] = [row["event"]]
                    selected = subscription_selection(
                        masks=masks,
                        event_ids=source.event_ids,
                        channel=source.channel,
                        global_subscription=False,
                        reversed_subscription=row["reverse"],
                        flags=[],
                        source_present=False,
                    )
                    if selected == "activate":
                        current.fixture_uid_counts[uid] = (
                            current.fixture_uid_counts.get(uid, 0) + 1
                        )
                        outbox.append(uid)
                return ()

            return SimpleNamespace(
                native_retention=SimpleNamespace(fight=current),
                native_clone_authority=object(),
                replay_event=replay,
            )

        fight.fixture_uid_counts = {}
        original = (mover.ap, mover.mp, mover.position, deepcopy(fight.events))

        def move_preview(reject):
            current = deepcopy(fight)
            outbox = []
            runtime = dispatcher(current, outbox)

            def step(state, actor, before, after):
                deliver_tackle_boundary(
                    runtime,
                    actor_id=actor.id,
                    from_cell=before,
                    to_cell=after,
                    action_id=1,
                )
                # A duplicate callback on the exact same paid scope is no-op.
                deliver_tackle_boundary(
                    runtime,
                    actor_id=actor.id,
                    from_cell=before,
                    to_cell=after,
                    action_id=1,
                )
                if reject:
                    raise ValueError("failed unpublished movement")

            with patch.object(external, "qualified_uids", return_value=eligible):
                current.move(3, mover.id, [(0, 1, 0)], step_callback=step)
            return current, outbox

        with self.assertRaisesRegex(ValueError, "unpublished"):
            move_preview(True)
        self.assertEqual((mover.ap, mover.mp, mover.position, fight.events), original)
        self.assertEqual(fight.fixture_uid_counts, {})
        self.assertEqual(committed_outbox, [])
        accepted, outbox = move_preview(False)
        committed_outbox.extend(outbox)
        self.assertEqual(
            (accepted.actors[mover.id].ap, accepted.actors[mover.id].mp), (5, 3)
        )
        self.assertEqual(accepted.fixture_uid_counts, {11: 1, 12: 1})
        self.assertEqual(committed_outbox, [11, 12])
        # Same event with no actual paid departure scope cannot notify anyone.
        self.assertEqual(
            deliver_tackle_boundary(
                dispatcher(accepted, outbox),
                actor_id=mover.id,
                from_cell=(0, 0, 0),
                to_cell=(0, 1, 0),
                action_id=1,
            ),
            (),
        )
        accepted.native_start_event_delivered = True
        accepted.native_owned_equipment_initializations = {
            mover.id: {"sources": ["qualified fixture"]}
        }
        accepted._advance()  # First actor ends: no complete table yet.
        self.assertFalse(getattr(accepted, "native_equipment_completed_rounds", {}))
        accepted._advance()  # Actual SU wraps and queues one completed round.
        self.assertEqual(accepted.native_timeline_round, 2)
        self.assertFalse(accepted.native_equipment_completed_rounds["1"]["delivered"])
        runtime = dispatcher(accepted, committed_outbox)
        with patch.object(external, "qualified_uids", return_value=eligible), patch(
            "wakfu_server.combat_global_pv_collections.global_pv_iterator",
            side_effect=lambda state, **kwargs: tuple(state.actors),
        ), patch(
            "wakfu_server.combat_external_event_removal.has_removal_subscription",
            return_value=False,
        ):
            external.deliver_completed_round(runtime)
            external.deliver_completed_round(runtime)
        self.assertEqual(accepted.fixture_uid_counts, {11: 1, 12: 1, 21: 1})
        self.assertEqual(committed_outbox, [11, 12, 21])
        self.assertTrue(accepted.native_equipment_completed_rounds["1"]["delivered"])
