"""Final setup INIT owns the first published timeline, without a second turn."""

import ast
from copy import deepcopy
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_ready import prepare_ready


ROOT = Path(__file__).resolve().parents[1] / "wakfu_server"


class InitialInitiativeTests(unittest.TestCase):
    def fight(self):
        actors = [
            Actor(84, 0, (0, 0, 0), 100, 6, 3, 0, 29, 1, True),
            Actor(85, 0, (1, 0, 0), 100, 6, 3, 0, 30, 2, True),
            Actor(-7, 1, (2, 0, 0), 100, 6, 3, 4, 4),
            Actor(-8, 1, (3, 0, 0), 100, 6, 3, 4, 4),
            Actor(-9, 1, (4, 0, 0), 100, 6, 3, 8, 8),
        ]
        cells = {a.position for a in actors}
        return Fight(
            670,
            actors,
            cells,
            {0: {(0, 0, 0), (1, 0, 0)}, 1: cells - {(0, 0, 0), (1, 0, 0)}},
        )

    def start_preparation(self, fight):
        fight.ready(1, defer_first_turn=True)
        fight.ready(2, defer_first_turn=True)
        self.assertEqual(fight.current.id, -9)
        self.assertFalse(any(row["kind"] == "turn_started" for row in fight.events))

    def test_owned_setup_bonus_changes_first_team_once_before_wire_delivery(self):
        fight = self.fight()
        fight.ready(1)
        before_start = []

        def initialize(preview, action_id):
            self.assertEqual(preview.current.id, -9)
            preview.actors[85].initiative += 15
            preview.finalize_initial_turn()
            before_start.append((preview.current.id, tuple(preview.order)))
            return preview, ()

        final, messages, packets = prepare_ready(
            fight,
            2,
            True,
            initialize=initialize,
            stats_serializer=lambda actor: b"stats",
            effects_serializer=lambda: b"\0\0",
        )
        self.assertEqual(before_start[0][0], 85)
        self.assertEqual(final.current.id, 85)
        self.assertIs(messages.fight, final)
        actor_packets = [
            struct.unpack_from(">q", body, 4)[0]
            for opcode, body in packets
            if opcode == 12873
        ]
        self.assertIn(85, actor_packets)
        self.assertEqual(
            [
                (row["actor_id"], row["actor_turn"])
                for row in final.events
                if row["kind"] == "turn_started"
            ],
            [(85, 1)],
        )
        self.assertEqual(
            {a.id: a.turn_count for a in final.actors.values()},
            {84: 0, 85: 1, -7: 0, -8: 0, -9: 0},
        )
        self.assertEqual((final.turn_id, final.native_timeline_round), (1, 1))
        self.assertTrue(
            all(value == 0 for value in final.native_timeline_member_counters.values())
        )
        order = tuple(final.order)
        final.actors[-7].initiative += 1000
        final.finalize_initial_turn()
        self.assertEqual(tuple(final.order), order)
        self.assertEqual(sum(row["kind"] == "turn_started" for row in final.events), 1)
        self.assertEqual(fight.phase, "placement")

    def test_constructor_finite_clock_stays_unbound_until_final_order(self):
        from wakfu_server.combat_state_ledger import RunningState
        from wakfu_server.wire import proto_field

        fight = self.fight()
        actor = fight.actors[-9]
        actor.state_ledger._entries = (
            RunningState(
                uid=900,
                reference=123,
                level=1,
                caster_id=actor.id,
                target_id=actor.id,
                duration=2,
                clock_actor="target",
                tick_at_turn_end=False,
                effect_ids=(),
                realtime_duration=0,
                retained=True,
                timer=None,
                protected=False,
            ),
        )
        fight.state_wire_payloads[900] = proto_field(90, b"").hex()
        fight.native_npc_initialization_receipts = {actor.id: {"initialized": True}}
        catalog = {
            "states": {
                "123": dict(
                    skip_turn_timer=False,
                    duration_base=2,
                    duration_per_level=0,
                    maximum_level=1,
                    tick_at_turn_end=False,
                    clock_actor="target",
                )
            }
        }
        with patch(
            "wakfu_server.combat_server_spell.states_catalog", return_value=catalog
        ):
            self.start_preparation(fight)
            self.assertIsNone(actor.state_ledger.entries[0].timer)
            fight.actors[85].initiative += 15
            fight.finalize_initial_turn()
            timer = actor.state_ledger.entries[0].timer
            self.assertEqual(
                (timer.actor_id, timer.expiration_round, timer.phase), (-9, 3, "start")
            )
            fight.finalize_initial_turn()
            self.assertIs(actor.state_ledger.entries[0].timer, timer)

    def test_native_307_insertion_keeps_its_slot_and_sy_counter_during_resort(self):
        from wakfu_server.combat_summon import (
            SummonSpecification,
            fresh_summon_insertion,
        )
        from wakfu_server.combat_timeline_snapshot import insert

        fight = self.fight()
        self.start_preparation(fight)
        spec = SummonSpecification(6, 1, False, 7, 0, "start", 2)
        order, index = fresh_summon_insertion(fight, spec, caster_id=85, actor_id=300)
        slot = order.index(300)
        insert(fight, 300, slot)
        fight.actors[300] = Actor(300, 0, (1, 1, 0), 50, 4, 2, 10000, 1)
        fight.order, fight.turn_index = order, index
        counter = fight.native_timeline_member_counters["300"]
        fight.actors[85].initiative += 15
        fight.finalize_initial_turn()
        self.assertEqual(fight.current.id, 85)
        self.assertEqual(fight.order.index(300), slot)
        self.assertEqual(fight.actors[300].turn_count, 0)
        self.assertEqual(fight.native_timeline_member_counters["300"], counter)
        self.assertEqual(len(fight.order), len(set(fight.order)))

    def test_actual_aptitude_callback_boundary_precedes_1003_and_1028_dispatch(self):
        tree = ast.parse((ROOT / "combat/combat_server_spell.py").read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "prepare_server_initialization"
        )
        aptitude = next(
            i
            for i, node in enumerate(function.body)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "initialize_aptitudes"
        )
        start = next(
            node
            for node in function.body[aptitude:]
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "fight_start"
        )
        deliver = next(
            node
            for node in ast.walk(start)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "deliver_fight_start"
        )
        boundary = deepcopy(function.body[aptitude : function.body.index(start)])
        boundary.append(
            ast.If(test=deepcopy(start.test), body=[deepcopy(deliver)], orelse=[])
        )
        fight = self.fight()
        self.start_preparation(fight)
        observations = []

        def aptitudes(preview, owned, factory, owner_id):
            preview.actors[85].initiative += 15
            return preview, ()

        namespace = dict(
            preview=fight,
            owned=None,
            factory=None,
            owner_id=2,
            initialize_aptitudes=aptitudes,
            packets=(),
            fight_start=True,
            before_fight_start=lambda initialized: initialized.finalize_initial_turn(),
            dispatcher=object(),
            deliver_fight_start=lambda *args, **kwargs: observations.append(
                fight.current.id
            ),
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=boundary, type_ignores=[])),
                "actual-initialization-boundary",
                "exec",
            ),
            namespace,
        )
        self.assertEqual(observations, [85])
        self.assertEqual(sum(row["kind"] == "turn_started" for row in fight.events), 1)

    def test_shared_owner_callback_is_last_only_and_legacy_always_finalizes(self):
        for file, shared in (
            ("combat/combat_session_adapter.py", True),
            ("application/session_combat.py", False),
        ):
            tree = ast.parse((ROOT / file).read_text())
            callback = next(
                keyword.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "prepare_server_initialization"
                for keyword in node.keywords
                if keyword.arg == "before_fight_start"
            )
            for index in (0, 1):
                fight = self.fight()
                self.start_preparation(fight)
                fight.actors[85].initiative += 15
                selected = eval(
                    compile(
                        ast.fix_missing_locations(ast.Expression(deepcopy(callback))),
                        file,
                        "eval",
                    ),
                    dict(index=index, actor_order=[84, 85]),
                )
                if shared and index == 0:
                    self.assertIsNone(selected)
                else:
                    selected(fight)
                    self.assertEqual(fight.current.id, 85)
