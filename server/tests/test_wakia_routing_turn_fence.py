"""Routing stays bound to the actor whose SDK was selected."""
import unittest
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.bridge import (
    backend_selection,
    world_background,
    world_entry,
    world_host,
)


class RoutingTurnFenceTests(unittest.TestCase):
    def runtime(self, actor_id, turn, *, ack=None):
        fight = SimpleNamespace(
            id=9, phase="active", current=SimpleNamespace(id=actor_id), turn_id=turn
        )
        return SimpleNamespace(fight=fight, awaiting_ack=ack, pending=[])

    def check_refresh_changed_actor(self):
        old = self.runtime(-1, 1)
        new = self.runtime(-2, 2)
        shared = SimpleNamespace(runtime=old, lock=RLock())
        registry = SimpleNamespace(lookup=lambda _: shared)
        adapter = SimpleNamespace(registry=registry)
        calls = []

        def refresh():
            calls.append(None)
            if len(calls) == 2:
                shared.runtime = new

        context = {
            "globals": {
                "combat_session": object(),
                "COMBAT_SESSIONS": adapter,
                "refresh_shared_combat": refresh,
            },
            "scopes": [],
        }
        with patch.object(
            world_entry, "effective_server_controlled", return_value=True
        ), patch.object(
            backend_selection, "pin_backend", return_value={"backend": "jondo"}
        ), patch.object(
            world_host, "effective_server_controlled", return_value=True
        ), patch.object(
            world_background, "effective_server_controlled", return_value=True
        ):
            self.assertEqual(
                list(world_entry.run_npc_turn(old, world_context=context)), []
            )
        self.assertEqual(len(calls), 2)

    def test_jondo_rejects_changed_actor_after_refresh(self):
        self.check_refresh_changed_actor()

    def check_changed_actor_under_schedule_lock(self, module):
        runtime = self.runtime(-2, 2)
        shared = SimpleNamespace(runtime=runtime, fight=runtime.fight, lock=RLock())
        adapter = SimpleNamespace(registry=SimpleNamespace(_member=lambda *_: None))
        with patch.object(module, "effective_server_controlled", return_value=True):
            result = module.schedule(
                shared,
                adapter,
                object(),
                None,
                None,
                None,
                None,
                None,
                expected_turn=(-1, 1),
            )
            self.assertEqual(result, "stale")

    def test_wakia_rejects_changed_actor_under_schedule_lock(self):
        self.check_changed_actor_under_schedule_lock(world_background)

    def test_foreground_coordinator_receives_selected_turn(self):
        from wakfu_server.wakia_bridge.wakfu_ai.bridge import world_shared

        runtime = self.runtime(-1, 1)
        with patch.object(
            world_entry, "effective_server_controlled", return_value=True
        ), patch.object(
            backend_selection, "pin_backend", return_value={"backend": "jondo"}
        ), patch.object(
            world_shared, "run_shared_turn", return_value=iter(())
        ) as run:
            self.assertEqual(
                list(
                    world_entry.run_npc_turn(
                        runtime,
                        shared_adapter=object(),
                        session=object(),
                        _expected_turn=(-1, 1),
                    )
                ),
                [],
            )
        self.assertEqual(run.call_args.kwargs["expected_turn"], (-1, 1))

    def test_acknowledgement_blocks_pinned_turn(self):
        runtime = self.runtime(-1, 1, ack=object())
        context = {"globals": {"_wakia_expected_turn": (-1, 1)}, "scopes": []}
        with patch.object(
            world_host, "effective_server_controlled", return_value=True
        ), patch.object(
            world_host, "requires_automatic_npc_turn_end", return_value=False
        ):
            self.assertEqual(
                list(world_host.execute(runtime, context, lambda *a, **k: ())), []
            )

    def test_shared_runtime_removed_before_pin_is_ignored(self):
        runtime = self.runtime(-1, 1)
        shared = SimpleNamespace(runtime=runtime)

        class DropRuntimeOnLock:
            def __enter__(self):
                shared.runtime = None

            def __exit__(self, *_):
                return False

        shared.lock = DropRuntimeOnLock()
        adapter = SimpleNamespace(registry=SimpleNamespace(lookup=lambda _: shared))
        context = {
            "globals": {
                "combat_session": object(),
                "COMBAT_SESSIONS": adapter,
                "refresh_shared_combat": lambda: None,
            },
            "scopes": [],
        }
        with patch.object(
            world_entry, "effective_server_controlled", return_value=True
        ), patch.object(backend_selection, "pin_backend") as pin:
            self.assertEqual(
                list(world_entry.run_npc_turn(runtime, world_context=context)), []
            )
        pin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
