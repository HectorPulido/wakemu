"""Focused ticket, deadline and dispatch coverage for native generic entries."""

from contextlib import nullcontext
from datetime import datetime, timezone
import struct
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server import owned_story_generic_entry as entry
from wakfu_server import dungeon_runtime_config
from wakfu_server.application import owned_story_generic_entry_dispatch as dispatch
from wakfu_server.application import source_quest_encounter_dispatch


class OwnedStoryGenericEntryTimingTests(unittest.TestCase):
    def test_owned_return_handle_queues_real_return_operation_without_transfer(self):
        state = SimpleNamespace(
            body=struct.pack(">qHH", 25482, 1, 0),
            character={"id": 91, "instance_id": 940},
            account_id=7,
            generation="lease-3",
            loaded=True,
            environment_ticket=None,
            quest_source_ticket=None,
        )
        store, positions = Mock(), Mock()
        store.connection.side_effect = lambda: nullcontext(Mock())
        positions.account_barrier.side_effect = lambda *_: nullcontext()
        runtime = SimpleNamespace(
            STORE=store, POSITIONS=positions, flush_positions=Mock()
        )
        app = SimpleNamespace(
            state=state, runtime=runtime, environment_blocked=Mock(return_value=False)
        )
        fake_runtime = SimpleNamespace(
            configuration_for_instance=Mock(return_value=("night", {}))
        )
        with patch.dict(
            sys.modules, {"wakfu_server.dungeon_runtime": fake_runtime}
        ), patch(
            "wakfu_server.owned_story_generic_return.selection", return_value={}
        ), patch(
            "wakfu_server.owned_story_generic_return.begin_operation",
            return_value={"due_ms": 3000},
        ) as begin, patch(
            "wakfu_server.owned_story_generic_transfer.selection"
        ) as transfer:
            self.assertTrue(dispatch.handle(app))
        self.assertEqual(state.quest_source_ticket, {"due_ms": 3000})
        begin.assert_called_once()
        transfer.assert_not_called()

    def setUp(self):
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        self.body = struct.pack(">qHH", 7001, 12870, 0)
        self.character = dict(
            id=91, account_id=7, map_id=700, instance_id=0, x=2, y=3, z=0
        )
        self.source = dict(id=7001, map_id=700)
        self.group = dict(cog=3000, cod=777, coe=2, cof=True)
        self.action = dict(wire_action=12870, criterion="True")
        self.route = dict(
            key="route-A",
            start_map_id=701,
            native_generic_entry={"approaches": [[2, 3, 0]]},
        )
        self.selected = {"route": self.route}
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = None
        self.store = Mock()
        self.store.now.return_value = self.now
        self.store.connection.side_effect = lambda: nullcontext(self.db)
        self.store.character.side_effect = lambda *_: dict(self.character)
        self.configuration = Mock(return_value=self.selected)

    def ticket(self):
        return dict(
            schema=entry.OPERATION_SCHEMA,
            token="a" * 32,
            account_id=7,
            generation="lease-3",
            owner=91,
            route_key="route-A",
            route_sha256=dungeon_runtime_config.canonical_hash(self.route),
            body_hex=self.body.hex(),
            position={
                k: self.character[k] for k in ("map_id", "instance_id", "x", "y", "z")
            },
            due_ms=int(self.now.timestamp() * 1000) + 3000,
        )

    def test_original_three_second_operation_issues_bound_ticket_without_entry(self):
        storage = __import__("wakfu_server.achievements.storage", fromlist=["storage"])
        stubs = {
            "wakfu_server.simple_item_actions": SimpleNamespace(_idle=Mock()),
            "wakfu_server.dungeon_transport": SimpleNamespace(enter_resolved=Mock()),
            "wakfu_server.dungeon_instances": SimpleNamespace(route=Mock()),
            "wakfu_server.dungeon_criteria": SimpleNamespace(
                evaluate=Mock(return_value=True)
            ),
            "wakfu_server.dungeon_runtime_config": SimpleNamespace(
                canonical_hash=Mock(return_value="route-hash")
            ),
            "wakfu_server.dungeon_achievement_authority": SimpleNamespace(
                queries_from_state=Mock(return_value={})
            ),
        }
        enter = stubs["wakfu_server.dungeon_transport"].enter_resolved
        with patch("wakfu_server.paid_containers._leased_owner") as lease, patch.dict(
            sys.modules, stubs
        ), patch.object(entry, "configuration", self.configuration), patch.object(
            entry,
            "validate_route",
            return_value=(self.source, self.group, self.action, {}, {}, 0),
        ), patch.object(
            storage, "load_locked", return_value={}
        ), patch.object(
            storage, "record_event", return_value=True
        ) as record:
            result = entry.begin_operation(
                self.store,
                7,
                "lease-3",
                self.character,
                self.body,
                loaded=True,
                blocked=False,
            )
        self.assertEqual(result["due_ms"], int(self.now.timestamp() * 1000) + 3000)
        self.assertEqual(result["body_hex"], self.body.hex())
        self.assertEqual(
            result["position"],
            {k: self.character[k] for k in ("map_id", "instance_id", "x", "y", "z")},
        )
        lease.assert_called_once()
        record.assert_called_once()
        enter.assert_not_called()

    def test_due_ticket_rejects_owner_lease_body_route_hash_position_and_consumption(
        self,
    ):
        ticket = self.ticket()
        saved = {"payload": ticket}
        self.db.execute.side_effect = lambda sql, args=(): Mock(
            fetchone=Mock(
                return_value=(
                    {"1": 1}
                    if args and str(args[-1]).startswith("owned-generic-entry-ended:")
                    else saved
                )
            )
        )
        with patch(
            "wakfu_server.dungeon_runtime_config.canonical_hash",
            wraps=dungeon_runtime_config.canonical_hash,
        ):
            # Before deadline is rejected before event lookups.
            with self.assertRaisesRegex(ValueError, "due original operation"):
                entry.require_operation(
                    self.db,
                    self.store,
                    self.character,
                    7,
                    "lease-3",
                    self.selected,
                    self.body,
                    ticket,
                )
            self.store.now.return_value = datetime.fromtimestamp(
                (ticket["due_ms"] + 5) / 1000, timezone.utc
            )
            for key, value in (
                ("account_id", 8),
                ("generation", "other-lease"),
                ("owner", 92),
                ("body_hex", "00"),
                ("route_key", "route-B"),
                ("route_sha256", "other-hash"),
                ("position", dict(ticket["position"], x=99)),
            ):
                altered = dict(ticket, **{key: value})
                with self.subTest(key=key), self.assertRaisesRegex(
                    ValueError, "due original operation"
                ):
                    entry.require_operation(
                        self.db,
                        self.store,
                        self.character,
                        7,
                        "lease-3",
                        self.selected,
                        self.body,
                        altered,
                    )
            # A valid ticket is accepted once, then an event-end record blocks replay.
            self.db.execute.side_effect = lambda sql, args=(): Mock(
                fetchone=Mock(
                    return_value=(
                        saved
                        if args
                        and str(args[-1]).startswith("owned-generic-entry-start:")
                        else None
                    )
                )
            )
            entry.require_operation(
                self.db,
                self.store,
                self.character,
                7,
                "lease-3",
                self.selected,
                self.body,
                ticket,
            )
            self.db.execute.side_effect = lambda sql, args=(): Mock(
                fetchone=Mock(
                    return_value=(
                        saved
                        if args
                        and str(args[-1]).startswith("owned-generic-entry-start:")
                        else {"1": 1}
                    )
                )
            )
            with self.assertRaisesRegex(ValueError, "missing, changed or consumed"):
                entry.require_operation(
                    self.db,
                    self.store,
                    self.character,
                    7,
                    "lease-3",
                    self.selected,
                    self.body,
                    ticket,
                )
            self.db.execute.side_effect = lambda *_args: Mock(
                fetchone=Mock(return_value=None)
            )
            with self.assertRaisesRegex(ValueError, "missing, changed or consumed"):
                entry.require_operation(
                    self.db,
                    self.store,
                    self.character,
                    7,
                    "lease-3",
                    self.selected,
                    self.body,
                    ticket,
                )

    def test_native_cost_is_checked_and_forwarded_only_during_actual_due_entry(self):
        storage = __import__("wakfu_server.achievements.storage", fromlist=["storage"])
        actual = dict(self.character)
        operation = self.ticket()
        self.store.now.return_value = datetime.fromtimestamp(
            (operation["due_ms"] + 5) / 1000, timezone.utc
        )
        self.store.lock_character.return_value = None
        self.store.character.side_effect = lambda *_: dict(actual)
        self.db.execute.side_effect = lambda sql, args=(): Mock(
            fetchone=Mock(
                return_value=(
                    {"payload": operation}
                    if args and str(args[-1]).startswith("owned-generic-entry-start:")
                    else None
                )
            )
        )
        costs = Mock(return_value=2)
        transport = Mock(return_value={"entered": True})
        stubs = {
            "wakfu_server.simple_item_actions": SimpleNamespace(_idle=Mock()),
            "wakfu_server.dungeon_instances": SimpleNamespace(
                route=Mock(return_value=self.route)
            ),
            "wakfu_server.dungeon_transport": SimpleNamespace(enter_resolved=transport),
            "wakfu_server.dungeon_criteria": SimpleNamespace(
                evaluate=Mock(return_value=True)
            ),
            "wakfu_server.dungeon_achievement_authority": SimpleNamespace(
                queries_from_state=Mock(return_value={})
            ),
            "wakfu_server.combat_inventory_date_conditions": SimpleNamespace(
                complete_owned_item_quantity=costs
            ),
        }
        with patch.dict(sys.modules, stubs), patch.object(
            entry, "configuration", self.configuration
        ), patch.object(
            entry,
            "validate_route",
            return_value=(
                self.source,
                self.group,
                self.action,
                {"action_reference": 701},
                {"map_id": 701, "x": 9, "y": 9, "z": 0},
                2,
            ),
        ), patch.object(
            storage, "load_locked", return_value={}
        ), patch.object(
            storage, "record_event"
        ):
            result = entry.enter(
                self.store,
                7,
                "lease-3",
                self.character,
                self.body,
                loaded=True,
                blocked=False,
                allowed_position_accounts={7},
                operation_ticket=operation,
                _db=self.db,
            )
        self.assertEqual(result, {"entered": True})
        costs.assert_called_once_with(actual, (777,))
        self.assertEqual(
            transport.call_args.args[4]["native_destination"],
            {
                "cyW": 2,
                "item_reference": 777,
            },
        )

    def test_poll_waits_until_due_then_enters_inside_common_party_barrier_and_zero_ms_stays_immediate(
        self,
    ):
        ticket = self.ticket()
        state = SimpleNamespace(
            account_id=7,
            generation="lease-3",
            character=dict(self.character),
            body=self.body,
            loaded=True,
            environment_ticket=None,
            quest_source_ticket=ticket,
            connection=object(),
            service="world",
        )
        runtime = SimpleNamespace(
            STORE=self.store,
            POSITIONS=Mock(),
            COMBAT_GROUPS=object(),
            send_batch=Mock(),
            record=Mock(),
        )
        runtime.POSITIONS.account_barrier.side_effect = lambda *_: nullcontext()
        app = SimpleNamespace(
            state=state,
            runtime=runtime,
            environment_blocked=Mock(return_value=False),
            deliver_dungeon_transitions=Mock(),
        )
        barrier_calls = []

        def run_barrier(_store, _positions, account_id, character_id, *, transition):
            barrier_calls.append((account_id, character_id))
            return transition(frozenset({account_id, 8}))

        fake_runtime = SimpleNamespace(
            initialize_instance=Mock(), entry_destination=Mock(return_value={})
        )
        fake_terrain = SimpleNamespace(map_geometry=Mock(return_value=701))
        with patch.object(entry, "configuration", self.configuration), patch(
            "wakfu_server.dungeon_position_barrier.run_party_entry",
            side_effect=run_barrier,
        ), patch.dict(
            sys.modules,
            {
                "wakfu_server.dungeon_runtime": fake_runtime,
                "wakfu_server.combat_terrain": fake_terrain,
            },
        ), patch.object(
            entry, "enter", return_value={"source_packets": []}
        ) as enter:
            self.assertFalse(dispatch.poll(app))
            enter.assert_not_called()
            with patch.object(
                dispatch, "poll", return_value="generic-poll"
            ) as generic_poll:
                self.assertEqual(
                    source_quest_encounter_dispatch.poll(app), "generic-poll"
                )
            generic_poll.assert_called_once_with(app)
            self.store.now.return_value = datetime.fromtimestamp(
                (ticket["due_ms"] + 5) / 1000, timezone.utc
            )
            self.assertTrue(dispatch.poll(app))
        self.assertEqual(barrier_calls, [(7, 91)])
        self.assertEqual(enter.call_count, 1)
        self.assertEqual(
            enter.call_args.kwargs["allowed_position_accounts"], frozenset({7, 8})
        )
        self.assertEqual(enter.call_args.kwargs["operation_ticket"], ticket)
        self.assertIsNone(state.quest_source_ticket)

        # A native zero occupation follows the legacy immediate transition path.
        self.group["cog"] = 0
        with patch.object(entry, "configuration", self.configuration), patch.object(
            entry,
            "validate_route",
            return_value=(self.source, self.group, self.action, {}, {}, 0),
        ), patch.dict(
            sys.modules, {"wakfu_server.dungeon_runtime": SimpleNamespace()}
        ), patch.object(
            dispatch, "_transition", return_value=True
        ) as transition:
            state.quest_source_ticket = None
            self.assertTrue(dispatch.handle(app))
        transition.assert_called_once_with(app, self.selected, self.body, owned=False)

    def test_due_generic_return_uses_normal_owned_exit_fence_without_early_exit(self):
        ticket = self.ticket()
        ticket["operation_kind"] = "owned_generic_return"
        state = SimpleNamespace(
            account_id=7,
            generation="lease-3",
            character=dict(self.character),
            loaded=True,
            environment_ticket=None,
            quest_source_ticket=ticket,
        )
        runtime = SimpleNamespace(
            STORE=self.store,
            POSITIONS=Mock(),
            record=Mock(),
        )
        app = SimpleNamespace(
            state=state,
            runtime=runtime,
            environment_blocked=Mock(return_value=False),
            deliver_dungeon_transitions=Mock(),
        )
        returned = {"character": {"id": 91, "map_id": 88}}
        with patch.object(entry, "configuration", self.configuration), patch(
            "wakfu_server.owned_story_generic_return.complete_operation",
            return_value=returned,
        ) as complete, patch(
            "wakfu_server.dungeon_position_barrier.run_account_exit",
            side_effect=lambda *_a, transition, **_kw: transition(),
        ) as exit_fence:
            self.store.now.return_value = self.now
            self.assertFalse(source_quest_encounter_dispatch.poll(app))
            complete.assert_not_called()
            exit_fence.assert_not_called()
            self.store.now.return_value = datetime.fromtimestamp(
                (ticket["due_ms"] + 5) / 1000, timezone.utc
            )
            self.assertTrue(source_quest_encounter_dispatch.poll(app))
        exit_fence.assert_called_once()
        self.assertEqual(
            exit_fence.call_args.args, (runtime.STORE, runtime.POSITIONS, 7)
        )
        self.assertTrue(exit_fence.call_args.kwargs["defer_rebind_busy"])
        complete.assert_called_once_with(
            runtime.STORE,
            7,
            "lease-3",
            state.character,
            ticket,
            loaded=True,
            blocked=False,
        )
        self.assertIsNone(state.quest_source_ticket)
        app.deliver_dungeon_transitions.assert_called_once_with(before_action=True)


if __name__ == "__main__":
    unittest.main()
