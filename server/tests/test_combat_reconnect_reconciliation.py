"""Reconnect recovery for stale placement fights uses durable abort authority."""
import unittest
import struct
import ast
import importlib
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_shared import Session
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server import combat_health


class ReconnectReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.live = set()

        class Store:
            def current_character_session(inner, account_id, generation, character_id):
                return (account_id, generation, character_id) in self.live

        self.store = Store()
        self.adapter = CombatSessionAdapter(self.store)
        self.old = Session(1, 10, "generation-old", 1134, 0)
        self.live.add((1, "generation-old", 10))
        self.fight = Fight(
            99,
            [
                Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (3, 0, 0), 20, 4, 2, 1, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        self.shared = self.adapter.registry.register(
            self.fight, self.old, group_lease=("group-99",)
        )

    @staticmethod
    def _fight_state(shared):
        fight = shared.fight
        return (
            fight.phase,
            tuple(fight.order),
            fight.turn_index,
            fight.turn_id,
            fight.native_table_turn,
            tuple(
                (
                    actor.id,
                    actor.hp,
                    actor.ap,
                    actor.mp,
                    actor.max_hp,
                    deepcopy(actor.effect_stats),
                    deepcopy(actor.effect_maxima),
                    actor.state_ledger.entries,
                )
                for actor in sorted(fight.actors.values(), key=lambda value: value.id)
            ),
            deepcopy(fight.native_spell_usage),
            deepcopy(fight.native_spell_grants),
            deepcopy(fight.state_wire_payloads),
            deepcopy(fight.native_owned_area_effects),
            deepcopy(fight.native_retained_records),
            tuple(deepcopy(fight.events)),
        )

    def _install_realistic_runtime_state(self, phase):
        shared = self.shared
        fight = shared.fight
        fight.phase = phase
        fight.native_effect_uid_next = 901
        fight.native_spell_usage = {"10": {"7359": 1}}
        fight.native_spell_grants = {10: {"spell_id": 7359, "level": 1}}
        fight.state_wire_payloads = {700: "01020304"}
        fight.native_owned_area_effects = {701: {"reference": 1134, "active": True}}
        fight.native_retained_records = {702: {"target_id": -200, "state_uid": 700}}
        fight.events.append({"sequence": 19, "kind": "spell_committed", "uid": 700})
        player = fight.actors[10]
        player.hp = 43
        player.ap = 2
        player.mp = 1
        player.effect_stats = {1: 43, 2: 2, 3: 1, 97: 12}
        player.effect_maxima = {1: 100, 2: 6, 3: 3, 97: 30}
        player.state_ledger._entries = (
            RunningState(
                uid=700,
                reference=6065,
                level=1,
                caster_id=10,
                target_id=10,
                duration=2,
                clock_actor="target",
                tick_at_turn_end=False,
                effect_ids=(416623,),
                realtime_duration=2,
                retained=True,
                timer=None,
            ),
        )
        if phase == "active":
            fight.order = [10, -200]
            fight.turn_index = 0
            fight.turn_id = 4
            fight.native_table_turn = 2
        shared.runtime = {
            "fight": fight,
            "native_rng_state": (17, 29),
            "pending_effect_uid": 700,
        }
        return self._fight_state(shared)

    def test_failed_finalizer_is_reconciled_on_new_login_then_actor_is_reusable(self):
        registry = self.adapter.registry
        self.assertEqual(registry.disconnect(self.old), [self.fight.id])
        self.live.remove((1, "generation-old", 10))
        self.shared.connected.add(1)
        replacement = Session(1, 10, "generation-new", 1134, 0)
        self.live.add((1, "generation-new", 10))

        # Model the old socket's durable abort/checkpoint failing. Registry
        # ownership remains fenced so neither the actor nor the fight leaks.
        with patch.object(
            combat_health,
            "persist_aborted_shared_fight",
            side_effect=RuntimeError("durable abort checkpoint failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "checkpoint failed"):
                self.adapter.reconcile_disconnected_pve(replacement)
        self.assertIs(registry.fights[self.fight.id], self.shared)
        self.assertEqual(registry.by_actor[10], self.fight.id)
        self.assertEqual(registry.by_character[10], self.fight.id)
        self.assertEqual(self.shared.connected, {1})
        self.assertTrue(self.shared.disconnect_abort_pending)
        self.assertEqual(self.shared.participants[1], self.old)

        exits = {10: {"applied": True, "character": {"id": 10, "hp": 57}}}
        with patch.object(
            combat_health, "persist_aborted_shared_fight", return_value=exits
        ) as persist:
            recovered = self.adapter.reconcile_disconnected_pve(replacement)
        self.assertIs(recovered["shared"], self.shared)
        self.assertIs(recovered["exits"], exits)
        persist.assert_called_once_with(
            self.store,
            self.shared,
            groups=None,
            reconnecting_session=replacement,
        )
        self.assertNotIn(self.fight.id, registry.fights)
        self.assertNotIn(10, registry.by_actor)
        self.assertNotIn(10, registry.by_character)
        self.assertIsNone(self.adapter.reconcile_disconnected_pve(replacement))

        # The durable abort released the stale actor reservation; the selected
        # replacement lease can now start a fresh fight without server restart.
        self.fight.id = 100
        registry.register(self.fight, replacement, group_lease=("group-100",))
        self.assertEqual(registry.by_actor[10], 100)
        self.assertEqual(registry.by_character[10], 100)

    def test_reconnect_does_not_abort_a_shared_fight_with_another_live_owner(self):
        registry = self.adapter.registry
        peer = Session(2, 20, "peer-generation", 1134, 0)
        self.live.add((2, "peer-generation", 20))
        peer_actor = Actor(20, 0, (1, 0, 0), 60, 6, 3, 90, 1, 2, True)
        registry.join(
            peer,
            struct.pack(">qB", 10, 0),
            peer_actor,
            actor_payload=lambda *args: (b"peer-stats", b"peer-effects"),
            bootstrap_packets=lambda *args: ((12847, b"peer-bootstrap"),),
        )

        self.assertEqual(registry.disconnect(self.old), [self.fight.id])
        self.live.remove((1, "generation-old", 10))
        replacement = Session(1, 10, "generation-new", 1134, 0)
        self.live.add((1, "generation-new", 10))
        self.assertIsNone(self.adapter.reconcile_disconnected_pve(replacement))
        self.assertIs(registry.fights[self.fight.id], self.shared)
        self.assertEqual(registry.by_actor[10], self.fight.id)
        self.assertEqual(registry.by_actor[20], self.fight.id)
        self.assertEqual(self.shared.participants[2], peer)
        self.assertIn(2, self.shared.connected)

    def test_placement_takeover_replays_same_fight_without_recreating_or_spending(self):
        before = self._install_realistic_runtime_state("placement")
        fight = self.shared.fight
        runtime = self.shared.runtime
        old_group = self.shared.group_lease
        self.assertEqual(self.adapter.registry.disconnect(self.old), [fight.id])
        self.live.remove((1, "generation-old", 10))
        replacement = Session(1, 10, "generation-new", 1134, 0)
        self.live.add((1, "generation-new", 10))
        durable = []
        bootstrap = []

        def prepare(shared_fight, shared, owner):
            bootstrap.append((shared_fight, shared, owner))
            return [(12847, b"continued-placement")]

        result = self.adapter.registry.takeover(
            fight.id,
            replacement,
            prepare,
            recover_disconnected=True,
            persist_takeover=lambda previous: durable.append(previous),
        )

        self.assertIs(result, self.shared)
        self.assertIs(self.shared.fight, fight)
        self.assertIs(self.shared.runtime, runtime)
        self.assertEqual(self._fight_state(self.shared), before)
        self.assertEqual(durable, [self.old])
        self.assertEqual(bootstrap, [(fight, self.shared, replacement)])
        self.assertEqual(self.shared.participants[1], replacement)
        self.assertIn(1, self.shared.connected)
        self.assertFalse(self.shared.disconnect_abort_pending)
        self.assertEqual(self.shared.group_lease, old_group)
        self.assertEqual(
            self.adapter.registry.drain(fight.id, replacement)[0].packets,
            ((12847, b"continued-placement"),),
        )

    def test_active_takeover_preserves_peer_outbox_and_rebinds_only_returning_ack(self):
        peer = Session(2, 20, "peer-generation", 1134, 0)
        self.live.add((2, "peer-generation", 20))
        peer_actor = Actor(20, 0, (1, 0, 0), 60, 6, 3, 90, 1, 2, True)
        self.adapter.registry.join(
            peer,
            struct.pack(">qB", 10, 0),
            peer_actor,
            actor_payload=lambda *args: (b"peer-stats", b"peer-effects"),
            bootstrap_packets=lambda *args: ((12847, b"peer-bootstrap"),),
        )
        before = self._install_realistic_runtime_state("active")
        fight = self.shared.fight
        runtime = self.shared.runtime
        self.adapter.registry.publish(
            fight.id, self.old, [(13482, b"before-reconnect")]
        )
        peer_outbox_before = deepcopy(self.shared.outboxes[2])
        self.adapter.registry.arm_ack(fight.id, 5)
        self.assertFalse(
            self.adapter.registry.acknowledge(
                fight.id,
                peer,
                struct.pack(">i", 5),
                lambda *args: self.fail("early release"),
            )
        )
        self.assertEqual(self.shared.ack.received, {2})

        self.assertEqual(self.adapter.registry.disconnect(self.old), [fight.id])
        self.live.remove((1, "generation-old", 10))
        replacement = Session(1, 10, "generation-new", 1134, 0)
        self.live.add((1, "generation-new", 10))
        durable = []
        result = self.adapter.registry.takeover(
            fight.id,
            replacement,
            lambda current_fight, shared, owner: [(12847, b"continued-active")],
            recover_disconnected=True,
            persist_takeover=lambda previous: durable.append(previous),
        )

        self.assertIs(result, self.shared)
        self.assertIs(self.shared.fight, fight)
        self.assertIs(self.shared.runtime, runtime)
        self.assertEqual(self._fight_state(self.shared), before)
        self.assertEqual(durable, [self.old])
        self.assertEqual(
            self.shared.ack.expected, {1: "generation-new", 2: "peer-generation"}
        )
        self.assertEqual(self.shared.ack.received, {2})
        self.assertFalse(self.shared.ack.complete)
        self.assertEqual(list(self.shared.outboxes[2]), list(peer_outbox_before))
        self.assertEqual(self.shared.participants[2], peer)
        self.assertEqual(self.shared.participants[1], replacement)
        self.assertEqual(self.shared.connected, {1, 2})
        self.assertEqual(
            self.adapter.registry.drain(fight.id, replacement)[0].packets,
            ((12847, b"continued-active"),),
        )

        released = self.adapter.registry.acknowledge(
            fight.id,
            replacement,
            struct.pack(">i", 5),
            lambda candidate, candidate_runtime, body: [(13482, b"after-reconnect")],
        )
        self.assertTrue(released)
        self.assertEqual(self.shared.ack.turn, None)
        peer_batches = list(self.shared.outboxes[2])
        self.assertEqual(
            peer_batches[: len(peer_outbox_before)], list(peer_outbox_before)
        )
        self.assertEqual(peer_batches[-1].packets, ((13482, b"after-reconnect"),))
        self.assertEqual(self._fight_state(self.shared), before)

    def test_placement_reconnect_bootstrap_is_owned_and_does_not_change_fight(self):
        from wakfu_server.combat.combat_session_adapter import CombatSessionAdapter

        self.shared.join_context = {
            "arena": {
                "map_id": 1134,
                "instance_id": 0,
                "x": 0,
                "y": 0,
                "width": 4,
                "height": 1,
                "min_z": 0,
                "max_z": 0,
                "cell_masks": [0, 0, 0, 0],
            },
            "terrain_effect_id": 99,
            "terrain_instance_id": 0,
            "leaders": {0: 10, 1: -200},
            "duration_ms": 60000,
            "actor_payload": lambda fight, actor, owner: (
                b"current-stats",
                b"current-effects",
            ),
        }
        before = self._fight_state(self.shared)
        packets = CombatSessionAdapter.placement_bootstrap(
            self.fight, self.shared, Session(1, 10, "generation-new", 1134, 0)
        )
        self.assertEqual(
            [opcode for opcode, _ in packets], [13652, 12847, 13684, 13026]
        )
        self.assertEqual(self._fight_state(self.shared), before)
        self.assertEqual(self.fight.native_fight_model, 2)

    def test_active_reconnect_snapshot_replays_retained_uid_without_reexecuting_effect(
        self,
    ):
        from types import SimpleNamespace
        from unittest.mock import patch

        from wakfu_server.combat.combat_state_carrier import state_carrier_payload
        from wakfu_server.combat.combat_retained_effects import RetainedEffect

        fight = self.fight
        fight.ready(1)
        fight.native_retained_tracking = True
        state = RunningState(
            uid=700,
            reference=6065,
            level=1,
            caster_id=10,
            target_id=10,
            duration=2,
            clock_actor="target",
            tick_at_turn_end=False,
            effect_ids=(416623,),
            realtime_duration=2,
            retained=True,
            timer=None,
            protected=False,
        )
        fight.actors[10].state_ledger._entries = (state,)
        fight.state_wire_payloads[700] = state_carrier_payload(
            uid=700,
            base_uid=700,
            caster_id=10,
            target_id=10,
            state_id=6065,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=0,
        ).hex()
        state_record = RetainedEffect(
            700,
            10,
            310,
            -1,
            manager_id=10,
            definition_type=0,
            state_unremovable=False,
            state_dispellable=True,
        )
        fight.native_retained_order[:] = [700]
        fight.native_retained_records = {700: vars(state_record)}
        self.shared.join_context = {
            "arena": {
                "map_id": 1134,
                "instance_id": 0,
                "x": 0,
                "y": 0,
                "width": 4,
                "height": 1,
                "min_z": 0,
                "max_z": 0,
                "cell_masks": [0, 0, 0, 0],
            },
            "terrain_effect_id": 99,
            "terrain_instance_id": 0,
            "leaders": {0: 10, 1: -200},
        }
        self.shared.runtime = SimpleNamespace(
            fight=fight,
            turn_deadline=None,
            native_action_id=41,
            awaiting_ack=None,
        )
        before = self._fight_state(self.shared)
        with patch.object(
            self.adapter, "actor_payload", return_value=(b"current", b"effects")
        ):
            packets = self.adapter.owned_reconnect_bootstrap(
                fight,
                self.shared,
                Session(1, 10, "generation-new", 1134, 0),
            )

        self.assertEqual(
            [opcode for opcode, _ in packets],
            [12847, 13912, 12873, 13912, 12873, 12233, 12514, 12053, 12613],
        )
        carrier = packets[-1][1]
        self.assertEqual(
            struct.unpack_from(">iiiBi", carrier), (fight.id, 41, -1, 0, 310)
        )
        self.assertEqual(self._fight_state(self.shared), before)
        self.assertEqual(
            fight.state_wire_payloads[700],
            state_carrier_payload(
                uid=700,
                base_uid=700,
                caster_id=10,
                target_id=10,
                state_id=6065,
                level=1,
                native_turn_clock=-1,
                native_realtime_remaining=0,
            ).hex(),
        )

    def test_failed_live_takeover_keeps_old_owner_and_all_runtime_state(self):
        peer = Session(2, 20, "peer-generation", 1134, 0)
        self.live.add((2, "peer-generation", 20))
        self.adapter.registry.join(
            peer,
            struct.pack(">qB", 10, 0),
            Actor(20, 0, (1, 0, 0), 60, 6, 3, 90, 1, 2, True),
            actor_payload=lambda *args: (b"peer-stats", b"peer-effects"),
            bootstrap_packets=lambda *args: ((12847, b"peer-bootstrap"),),
        )
        before = self._install_realistic_runtime_state("active")
        fight = self.shared.fight
        runtime = self.shared.runtime
        self.adapter.registry.arm_ack(fight.id, 5)
        self.assertFalse(
            self.adapter.registry.acknowledge(
                fight.id,
                peer,
                struct.pack(">i", 5),
                lambda *args: self.fail("early release"),
            )
        )
        peer_outbox_before = deepcopy(self.shared.outboxes[2])
        self.assertEqual(self.adapter.registry.disconnect(self.old), [fight.id])
        self.live.remove((1, "generation-old", 10))
        replacement = Session(1, 10, "generation-new", 1134, 0)
        self.live.add((1, "generation-new", 10))
        with self.assertRaisesRegex(RuntimeError, "takeover checkpoint failed"):
            self.adapter.registry.takeover(
                fight.id,
                replacement,
                lambda *args: [(12847, b"prepared-only")],
                recover_disconnected=True,
                persist_takeover=lambda previous: (_ for _ in ()).throw(
                    RuntimeError("takeover checkpoint failed")
                ),
            )

        self.assertIs(self.adapter.registry.lookup(fight.id), self.shared)
        self.assertIs(self.shared.fight, fight)
        self.assertIs(self.shared.runtime, runtime)
        self.assertEqual(self._fight_state(self.shared), before)
        self.assertEqual(self.shared.participants[1], self.old)
        self.assertNotIn(1, self.shared.connected)
        self.assertFalse(self.shared.disconnect_abort_pending)
        self.assertEqual(
            self.shared.ack.expected, {1: "generation-old", 2: "peer-generation"}
        )
        self.assertEqual(self.shared.ack.received, {2})
        self.assertEqual(list(self.shared.outboxes[2]), list(peer_outbox_before))
        self.assertIn(2, self.shared.connected)
        self.assertEqual(self.adapter.registry.by_actor[10], fight.id)
        self.assertEqual(self.adapter.registry.by_character[10], fight.id)

    def test_durable_abort_uses_reconnect_lease_for_health_and_old_receipt_for_abort(
        self,
    ):
        class DB:
            def execute(inner, query, params=()):
                sql = " ".join(query.split()).lower()
                if sql.startswith("select status from combat_fights"):
                    return Result({"status": "placement"})
                if sql.startswith("select account_id,character_id,session_generation"):
                    return Result(
                        [
                            {
                                "account_id": 1,
                                "character_id": 10,
                                "session_generation": "generation-old",
                                "entry_hp": 60,
                                "entry_max_hp": 100,
                                "entry_hp_damage": 40,
                                "entry_health_dead": False,
                            }
                        ]
                    )
                if sql.startswith("select id from accounts"):
                    return Result({"id": 1})
                if sql.startswith(
                    "select generation,character_id,expires_at from sessions"
                ):
                    return Result(
                        {
                            "generation": "generation-new",
                            "character_id": 10,
                            "expires_at": 100,
                        }
                    )
                if sql.startswith("select id from characters"):
                    return Result({"id": 10})
                raise AssertionError(f"Unexpected database query: {query}")

        class Result:
            def __init__(self, value):
                self.value = value

            def fetchone(self):
                return self.value if isinstance(self.value, dict) else None

            def __iter__(self):
                return iter(self.value if isinstance(self.value, list) else [])

        class Store:
            @contextmanager
            def connection(inner):
                yield DB()

            def current_character_session(inner, account_id, generation, character_id):
                return (account_id, generation, character_id) == (
                    1,
                    "generation-new",
                    10,
                )

            def now(inner):
                return 50

            def character(inner, account_id, character_id, db):
                return {
                    "id": character_id,
                    "hp": 44,
                    "max_hp": 100,
                    "hp_damage": 56,
                    "health_dead": False,
                }

        self.shared.connected.clear()
        self.shared.group_lease = None
        replacement = Session(1, 10, "generation-new", 1134, 0)
        captured_health = []
        captured_abort = []

        def capture_persist(store, account_id, generation, character, fight, **kwargs):
            captured_health.append((account_id, generation, character.copy(), kwargs))
            return {"applied": True}

        def capture_abort(
            store, account_id, character_id, fight_id, *, expected_generation, db
        ):
            captured_abort.append(
                (account_id, character_id, fight_id, expected_generation)
            )
            return True

        with patch.object(
            combat_health, "persist", side_effect=capture_persist
        ), patch.object(
            importlib.import_module("wakfu_server.fight_store"),
            "abort",
            side_effect=capture_abort,
        ):
            result = combat_health.persist_aborted_shared_fight(
                Store(), self.shared, reconnecting_session=replacement
            )

        self.assertEqual(result, {10: {"applied": True}})
        self.assertEqual(len(captured_health), 1)
        self.assertEqual(captured_health[0][0:2], (1, "generation-new"))
        self.assertEqual(captured_health[0][2]["hp"], 60)
        self.assertEqual(captured_health[0][3]["disconnected_baseline"]["hp"], 60)
        self.assertEqual(captured_abort, [(1, 10, self.fight.id, "generation-old")])

    def test_character_login_reconciles_before_withdrawal_and_health_initialization(
        self,
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        selection = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "opcode"
                and any(
                    isinstance(value, ast.Constant) and value.value == 23664
                    for value in test.comparators
                )
                for test in ast.walk(node.test)
            )
        )
        calls = [
            node.func.attr
            for statement in selection.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        self.assertIn("live_reconnect_available", calls)
        self.assertIn("reconcile_disconnected_pve", calls)
        self.assertIn("recover_withdrawn_pve", calls)
        self.assertLess(
            calls.index("live_reconnect_available"),
            calls.index("reconcile_disconnected_pve"),
        )
        self.assertLess(
            calls.index("reconcile_disconnected_pve"),
            calls.index("recover_withdrawn_pve"),
        )
        health_init = next(
            index
            for index, statement in enumerate(selection.body)
            if any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "initialize"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "health_store"
                for node in ast.walk(statement)
            )
        )
        reconciliation = next(
            index
            for index, statement in enumerate(selection.body)
            if any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "reconcile_disconnected_pve"
                for node in ast.walk(statement)
            )
        )
        self.assertLess(reconciliation, health_init)
        initialize_call = next(
            node
            for statement in selection.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "health_store"
            and node.func.attr == "initialize"
        )
        coefficient = next(
            keyword.value
            for keyword in initialize_call.keywords
            if keyword.arg == "coefficient"
        )
        self.assertIsInstance(coefficient, ast.IfExp)
        self.assertIsInstance(coefficient.test, ast.Name)
        self.assertEqual(coefficient.test.id, "live_reconnect")
        self.assertEqual(coefficient.body.value, 0)
        self.assertEqual(coefficient.orelse.value, 1)

    def test_live_reconnect_probe_requires_matching_live_owner_and_durable_phase(self):
        class Result:
            def __init__(self, row):
                self.row = row

            def fetchone(self):
                return self.row

        class DB:
            def __init__(self, row):
                self.row = row

            def execute(self, query, params):
                if "combat_fight_participants" not in query:
                    raise AssertionError(f"Unexpected query: {query}")
                return Result(self.row)

        self.live.remove((1, "generation-old", 10))
        replacement = Session(1, 10, "generation-new", 1134, 0)
        self.live.add((1, "generation-new", 10))
        registry = self.adapter.registry
        self.assertEqual(registry.disconnect(self.old), [self.fight.id])
        for phase in ("placement", "active"):
            with self.subTest(phase=phase):
                self.fight.phase = phase
                before = self._fight_state(self.shared)
                self.store.connection = lambda phase=phase: _Connection(
                    DB({"status": phase, "session_generation": "generation-old"})
                )
                self.assertTrue(self.adapter.live_reconnect_available(replacement))
                self.assertEqual(self._fight_state(self.shared), before)

        self.fight.phase = "active"
        self.store.connection = lambda: _Connection(
            DB({"status": "aborted", "session_generation": "generation-old"})
        )
        self.assertFalse(self.adapter.live_reconnect_available(replacement))
        self.assertIs(registry.fights[self.fight.id], self.shared)

        self.store.connection = lambda: _Connection(
            DB({"status": "active", "session_generation": "foreign-generation"})
        )
        with self.assertRaisesRegex(ValueError, "durable lease"):
            self.adapter.live_reconnect_available(replacement)


class _Connection:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc, traceback):
        return False


if __name__ == "__main__":
    unittest.main()
