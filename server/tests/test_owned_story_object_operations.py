"""One generic original-duration occupation: start, cancellation and finish."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from wakfu_server import owned_story_object_operations as operations
from wakfu_server.application import owned_story_dispatch

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server/maps/owned_story_profiles"


class OwnedStoryObjectOperationTests(TestCase):
    def test_native_decoration_repack_reaches_immediate_dispatch(self):
        with patch.object(operations.controller, "interact") as inspect:
            self.assertIsNone(
                operations.selection(
                    None, None, {}, struct.pack(">qHH", 8800123, 23, 0)
                )
            )
            inspect.assert_not_called()

    def test_original_workshop_duration_and_criterion(self):
        selected = json.loads((ROOT / "wild-estate-brak-723.v2.json").read_text())
        source = json.loads((ROOT / "wild-estate-brak-723.native.v2.json").read_text())
        step = next(s for s in selected["steps"] if s["id"] == "staff-workshop")
        with patch.object(
            operations.controller,
            "interact",
            return_value=dict(selected=selected, step=step),
        ), patch.object(
            operations.mechanics, "sources", return_value=source
        ), patch.object(
            operations.mechanics, "allowed", return_value=True
        ) as allowed:
            result = operations.selection(
                None, None, {}, struct.pack(">qHH", 20460, 0, 0)
            )
            self.assertEqual(result["duration_ms"], 3000)
            allowed.return_value = False
            with self.assertRaisesRegex(ValueError, "native prerequisites"):
                operations.selection(None, None, {}, struct.pack(">qHH", 20460, 0, 0))

    def test_school_dresser_clue_with_native_zero_duration_keeps_immediate_dispatch(
        self,
    ):
        selected = json.loads((ROOT / "huppermage-store-1024.json").read_text())
        source = json.loads((ROOT / "huppermage-store-1024.native.v1.json").read_text())
        step = next(row for row in selected["steps"] if row["reference"] == 26251)
        self.assertEqual(step["id"], "store-clue-inspected")
        clue = source["reviewed_clue_source"]
        self.assertEqual(clue["source"]["id"], 26251)
        self.assertEqual(clue["descriptor"]["descriptor_id"], 991)
        self.assertEqual(clue["descriptor"]["groups"][0]["cog"], 0)
        self.assertNotIn("programs", source)
        with patch.object(
            operations.controller,
            "interact",
            return_value=dict(selected=selected, step=step),
        ), patch.object(operations.mechanics, "sources", return_value=source):
            result = operations.selection(
                None, None, {}, struct.pack(">qHH", 26251, 0, 0)
            )
        self.assertIsNone(result)

    def test_repeated_start_keeps_deadline_and_movement_cancels(self):
        self.exercise(move=True)

    def test_only_due_unchanged_source_executes_normal_transaction_once(self):
        self.exercise(move=False)

    def test_changed_source_cancels_without_effects(self):
        self.exercise(move=False, source_change=True)

    def exercise(self, *, move, source_change=False):
        current = dict(
            id=91, account_id=2, map_id=723, instance_id=1001, x=12, y=-7, z=0
        )
        clock = [datetime(2026, 11, 17, tzinfo=timezone.utc)]
        operation = dict(
            duration_ms=3000,
            source_sha256="a" * 64,
            controller_id="test",
            step="workshop",
        )
        store = Mock()
        store.now.side_effect = lambda: clock[0]
        store.character.side_effect = lambda *_: dict(current)
        store.connection.side_effect = lambda: nullcontext(Mock())
        positions = Mock()
        positions.account_barrier.side_effect = lambda *_: nullcontext()
        state = SimpleNamespace(
            character=dict(current),
            account_id=2,
            generation=3,
            loaded=True,
            fight=None,
            combat_session=None,
            spectator_session=None,
            environment_ticket=None,
            body=struct.pack(">qHH", 20460, 0, 0),
            connection=SimpleNamespace(),
        )
        session = SimpleNamespace(
            state=state,
            runtime=SimpleNamespace(
                STORE=store, POSITIONS=positions, flush_positions=Mock()
            ),
            environment_blocked=lambda: False,
        )
        with patch.object(
            operations,
            "selection",
            side_effect=[operation, operation, dict(operation, source_sha256="b" * 64)]
            if source_change
            else None,
            return_value=operation,
        ), patch("wakfu_server.paid_containers._leased_owner"), patch.object(
            owned_story_dispatch, "interact", return_value={"packets": []}
        ) as apply, patch.object(
            owned_story_dispatch, "publish"
        ) as publish:
            self.assertTrue(operations.begin(session))
            deadline = state.connection.owned_story_object_operation["due_at"]
            clock[0] += timedelta(seconds=1)
            self.assertTrue(operations.begin(session))
            self.assertEqual(
                state.connection.owned_story_object_operation["due_at"], deadline
            )
            self.assertFalse(operations.poll(session))
            apply.assert_not_called()
            if move:
                state.character["x"] += 1
            clock[0] += timedelta(seconds=2)
            applied = not move and not source_change
            self.assertEqual(operations.poll(session), applied)
            self.assertIsNone(state.connection.owned_story_object_operation)
            self.assertFalse(operations.poll(session))
            self.assertEqual(apply.call_count, int(applied))
            self.assertEqual(publish.call_count, int(applied))
