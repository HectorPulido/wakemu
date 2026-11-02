"""Actual loaded-bootstrap boundary and existing owned hydration consumer."""
import ast
import os
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

import test_rift_transition_recovery_callers as base
from test_dungeon_recovery_callers import caller
from wakfu_server import rift_transition_delivery
from wakfu_server.position_buffer import PositionBaselineChanged, PositionOwnerBusy


def loaded_receipt_boundary(namespace):
    source = Path(
        os.environ.get(
            "WAKFU_RECOVERY_DISPATCH_SOURCE",
            Path(__file__).resolve().parents[1] / "local_game_server.py",
        )
    )
    module = ast.parse(source.read_text())
    for node in ast.walk(module):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        indices = [
            i
            for i, statement in enumerate(body)
            if isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "recovered_travel"
                for target in statement.targets
            )
        ]
        if not indices:
            continue
        start = indices[0] - 1
        end = next(
            i
            for i in range(start, len(body))
            if isinstance(body[i], ast.Expr)
            and isinstance(body[i].value, ast.Call)
            and isinstance(body[i].value.func, ast.Name)
            and body[i].value.func.id == "resume_settled_shared_combat"
        )
        code = ast.Module(body=body[start:end], type_ignores=[])
        exec(compile(code, str(source), "exec"), namespace)
        return
    raise AssertionError("Actual loaded travel receipt boundary not found")


class TravelDeliveryCallerTests(base.RiftTransitionRecoveryCallerTests):
    def test_refresh_uses_current_location_defers_dirty_and_preserves_newer_wakeup(
        self,
    ):
        deliver, ns = self.delivery()
        rift_transition_delivery.queue_owned_position_refresh(
            self.account_id, self.generation, self.actor_id, self.first
        )
        witness = dict(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            )
        )
        ns["STORE"].character.return_value = dict(self.old, **self.latest)
        ns["POSITIONS"].has_dirty.return_value = True
        self.assertFalse(deliver())
        ns["WORLD"].leave.assert_not_called()
        ns["POSITIONS"].attach.assert_not_called()
        ns["POSITIONS"].has_dirty.return_value = False
        ns["POSITIONS"].account_barrier.side_effect = PositionOwnerBusy("busy owner")
        self.assertFalse(deliver())
        ns["WORLD"].leave.assert_not_called()
        ns[
            "POSITIONS"
        ].account_barrier.side_effect = lambda *args, **kwargs: nullcontext()
        ns["POSITIONS"].attach.side_effect = PositionBaselineChanged("new movement")
        self.assertFalse(deliver())
        ns["WORLD"].leave.assert_not_called()
        ns["POSITIONS"].attach.side_effect = None
        newer = dict(self.latest, x=12)
        ns["send"].side_effect = lambda *args: rift_transition_delivery.queue(
            (self.member,), newer
        )
        self.assertTrue(deliver())
        ns["join_world"].assert_called_once_with(
            self.generation, ns["connection"], dict(self.old, **self.latest)
        )
        self.assertEqual(
            newer,
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            ),
        )
        rift_transition_delivery.queue_owned_position_refresh(
            self.account_id, self.generation, self.actor_id, witness
        )
        self.assertEqual(
            newer,
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            ),
        )

    def test_loaded_ack_boundary_rehydrates_current_scene_after_supersession(self):
        from wakfu_server import haven_world_travel, item_teleports

        deliver, ns = self.delivery()
        ns["POSITIONS"].has_dirty.return_value = False
        ns["STORE"].character.return_value = dict(self.old, **self.latest)

        def superseded(*args):
            rift_transition_delivery.queue_owned_position_refresh(
                self.account_id, self.generation, self.actor_id, self.first
            )
            return False

        ns.update(character=self.old, deliver_rift_transition=deliver)
        with patch.object(
            item_teleports,
            "pending",
            return_value={"transition": {"token": "original"}},
        ), patch.object(
            item_teleports, "acknowledge", side_effect=superseded
        ) as acknowledge, patch.object(
            haven_world_travel, "pending", return_value=None
        ):
            loaded_receipt_boundary(ns)
        acknowledge.assert_called_once_with(
            ns["STORE"], self.account_id, self.generation, self.actor_id, "original"
        )
        ns["join_world"].assert_called_once_with(
            self.generation, ns["connection"], dict(self.old, **self.latest)
        )
        self.assertIsNone(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            )
        )

    def test_completed_login_bootstrap_retires_only_owned_current_refresh(self):
        store = Mock(current_character_session=Mock(return_value=True))
        fresh = dict(self.old, **self.latest)
        store.character.return_value = fresh
        acknowledge = caller("acknowledge_rift_login_bootstrap", {"STORE": store})
        rift_transition_delivery.queue_owned_position_refresh(
            self.account_id, self.generation, self.actor_id, self.first
        )
        acknowledge(self.account_id, self.generation, fresh)
        self.assertIsNone(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            )
        )
        rift_transition_delivery.queue_owned_position_refresh(
            self.account_id, self.generation, self.actor_id, self.first
        )
        store.current_character_session.return_value = False
        with self.assertRaisesRegex(ValueError, "replaced session"):
            acknowledge(self.account_id, self.generation, fresh)
        store.current_character_session.return_value = True
        store.character.return_value = dict(fresh, x=fresh["x"] + 1)
        acknowledge(self.account_id, self.generation, fresh)
        self.assertIsNotNone(
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            )
        )
        rift_transition_delivery.queue((self.member,), self.first)
        acknowledge(self.account_id, self.generation, fresh)
        self.assertEqual(
            self.first,
            rift_transition_delivery.pending(
                self.account_id, self.generation, self.actor_id
            ),
        )
