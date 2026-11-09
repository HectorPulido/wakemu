"""World dispatch must preserve ownership and handle invalid routing safely."""
import unittest
from types import SimpleNamespace
from threading import RLock
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.bridge import (
    backend_selection,
    world_entry,
    world_host,
)


class WakIADispatchSafetyTests(unittest.TestCase):
    def runtime(self):
        actor = SimpleNamespace(id=-1)
        fight = SimpleNamespace(id=7, phase="active", current=actor, turn_id=3)
        return SimpleNamespace(
            fight=fight,
            awaiting_ack=None,
            pending=[],
            end_server_turn=lambda actor_id, turn_id: [(actor_id, turn_id)],
        )

    def test_noncontrolled_actor_is_not_pinned(self):
        runtime = self.runtime()
        with patch.object(
            world_entry, "effective_server_controlled", return_value=False
        ), patch.object(backend_selection, "pin_backend") as pin, patch.object(
            world_host, "execute", return_value=iter(())
        ):
            self.assertEqual(
                list(
                    world_entry.run_npc_turn(
                        runtime, world_context={"globals": {}, "scopes": []}
                    )
                ),
                [],
            )
        pin.assert_not_called()

    def test_routing_error_reaches_turn_boundary_without_retry(self):
        runtime = self.runtime()

        def execute(runtime, context, runner):
            yield from runner(runtime)

        with patch.object(
            world_entry, "effective_server_controlled", return_value=True
        ), patch.object(
            backend_selection, "pin_backend", side_effect=ValueError("bad config")
        ) as pin, patch.object(
            world_host, "execute", side_effect=execute
        ), patch(
            "wakfu_server.combat_automatic_npc_turn.requires_automatic_npc_turn_end",
            return_value=False,
        ):
            outcomes = list(
                world_entry.run_npc_turn(
                    runtime, world_context={"globals": {}, "scopes": []}
                )
            )
        self.assertEqual(pin.call_count, 1)
        self.assertEqual(outcomes[-1][0], [(-1, 3)])
        self.assertEqual(outcomes[-1][1]["reason"], "complete_native_bridge_rejected")
        self.assertEqual(outcomes[-1][1]["detail"], "bad config")

    def test_shared_routing_error_stays_in_selected_transaction(self):
        from wakfu_server.wakia_bridge.wakfu_ai.bridge import world_shared

        runtime = self.runtime()
        shared = SimpleNamespace(runtime=runtime, lock=RLock())
        adapter = SimpleNamespace(registry=SimpleNamespace(lookup=lambda _: shared))
        session = object()
        context = {
            "globals": {
                "combat_session": session,
                "COMBAT_SESSIONS": adapter,
                "refresh_shared_combat": lambda: None,
            },
            "scopes": [],
        }

        def execute(runtime, _context, runner):
            yield from runner(runtime, shared_adapter=adapter, session=session)

        def coordinated(runtime, adapter, session, runner, **kwargs):
            yield from runner(runtime)

        with patch.object(
            world_entry, "effective_server_controlled", return_value=True
        ), patch.object(
            backend_selection,
            "pin_backend",
            side_effect=[ValueError("bad config"), {"backend": "current"}],
        ) as pin, patch.object(
            world_entry, "_legacy_runner"
        ) as legacy, patch.object(
            world_host, "execute", side_effect=execute
        ), patch.object(
            world_shared, "run_shared_turn", side_effect=coordinated
        ), patch(
            "wakfu_server.combat_automatic_npc_turn.requires_automatic_npc_turn_end",
            return_value=False,
        ):
            outcomes = list(world_entry.run_npc_turn(runtime, world_context=context))
        self.assertEqual(pin.call_count, 1)
        legacy.assert_not_called()
        self.assertEqual(outcomes[-1][1]["reason"], "complete_native_bridge_rejected")

    def test_missing_selected_legacy_sdk_fails_at_safe_turn_boundary(self):
        runtime = self.runtime()

        def execute(runtime, context, runner):
            yield from runner(runtime)

        with patch.object(
            world_entry, "effective_server_controlled", return_value=True
        ), patch.object(
            backend_selection, "pin_backend", return_value={"backend": "current"}
        ) as pin, patch.object(
            world_entry,
            "_legacy_runner",
            side_effect=FileNotFoundError("legacy missing"),
        ), patch.object(
            world_host, "execute", side_effect=execute
        ), patch(
            "wakfu_server.combat_automatic_npc_turn.requires_automatic_npc_turn_end",
            return_value=False,
        ):
            outcomes = list(
                world_entry.run_npc_turn(
                    runtime, world_context={"globals": {}, "scopes": []}
                )
            )
        self.assertEqual(pin.call_count, 1)
        self.assertEqual(outcomes[-1][1]["reason"], "complete_native_bridge_rejected")
        self.assertEqual(outcomes[-1][1]["detail"], "legacy missing")


if __name__ == "__main__":
    unittest.main()
