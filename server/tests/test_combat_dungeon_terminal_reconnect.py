"""Join shared terminal ACKs to durable dungeon progress and reconnect state."""

import ast
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace

from postgres_case import PostgresCase
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_rewards import Policy
from wakfu_server.fight_store import create, join_participant
from wakfu_server.maps.dungeon_progression import (
    bind_encounter,
    initialize_run,
    settle_encounter,
)


class TerminalPositionRetryWiringTests(unittest.TestCase):
    def test_normal_12925_defers_post_flush_work_without_replaying_ack(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        session = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        branch = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "opcode == 12925 and fight_messages is not None"
        )
        calls = [node for node in ast.walk(branch) if isinstance(node, ast.Call)]
        pending_type = next(
            node
            for node in ast.walk(branch)
            if isinstance(node, ast.Name) and node.id == "PendingPositionReturn"
        )
        self.assertEqual(pending_type.id, "PendingPositionReturn")
        return_call = next(
            call
            for call in calls
            if isinstance(call.func, ast.Name) and call.func.id == "return_to_world"
        )
        pending_assignments = [
            node
            for node in ast.walk(branch)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "pending_combat_return"
                for target in node.targets
            )
        ]
        self.assertEqual(len(pending_assignments), 1)
        self.assertLess(return_call.lineno, pending_assignments[0].lineno)
        pending_assignment = pending_assignments[0]
        initial_attempt = next(
            call
            for call in calls
            if isinstance(call.func, ast.Attribute)
            and call.func.attr == "attempt"
            and call.lineno < pending_assignment.lineno
        )
        self.assertEqual(
            {keyword.arg for keyword in initial_attempt.keywords},
            {"now", "flush", "complete", "busy"},
        )
        self.assertTrue(
            any(
                isinstance(node, ast.Name) and node.id == "finish_return"
                for node in ast.walk(pending_assignment)
            )
        )
        self.assertFalse(
            any(
                isinstance(call.func, ast.Name)
                and call.func.id == "retry_position_owner_barrier"
                for call in calls
            )
        )
        # The ACK/return is applied once; the post-flush callback owns world
        # entry and terminal registry cleanup after a later idle retry.
        self.assertEqual(
            sum(
                1
                for call in calls
                if isinstance(call.func, ast.Name) and call.func.id == "return_to_world"
            ),
            1,
        )
        for terminal_call in (
            "return_to_world",
            "return_abandon",
            "duel_return_packets",
        ):
            matching = [
                call
                for call in calls
                if isinstance(call.func, ast.Name) and call.func.id == terminal_call
            ]
            self.assertTrue(matching, terminal_call)
            self.assertTrue(
                all(call.lineno < pending_assignments[0].lineno for call in matching),
                f"{terminal_call} must settle before the shared deferred flush path",
            )
        finish = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef)
            and node.name == "finish_combat_return_after_position_flush"
        )
        finish_calls = {
            call.func.id if isinstance(call.func, ast.Name) else call.func.attr
            for call in ast.walk(finish)
            if isinstance(call, ast.Call)
        }
        self.assertIn("attach_combat_return_position", finish_calls)
        self.assertIn("mark_returned", finish_calls)
        self.assertIn("disconnect", finish_calls)
        finish_callback = next(
            node
            for node in ast.walk(branch)
            if isinstance(node, ast.FunctionDef) and node.name == "finish_return"
        )
        self.assertEqual(
            {
                keyword.arg
                for call in ast.walk(finish_callback)
                if isinstance(call, ast.Call)
                for keyword in call.keywords
            },
            {"abandoned", "shared_return", "shared_state"},
        )
        idle = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef) and node.name == "idle"
        )
        idle_calls = {
            call.func.attr
            for call in ast.walk(idle)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        }
        self.assertIn("attempt", idle_calls)
        idle_attempt = next(
            call
            for call in ast.walk(idle)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "attempt"
        )
        self.assertEqual(
            {keyword.arg for keyword in idle_attempt.keywords},
            {"now", "flush", "complete", "busy"},
        )
        self.assertTrue(
            any(
                isinstance(node, ast.If)
                and any(
                    isinstance(child, ast.Name) and child.id == "pending_combat_return"
                    for child in ast.walk(node.test)
                )
                and any(isinstance(child, ast.Return) for child in ast.walk(node))
                for node in ast.walk(idle)
            )
        )
        dispatch_guard = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(child, ast.Name) and child.id == "pending_combat_return"
                for child in ast.walk(node.test)
            )
            and any(isinstance(child, ast.Continue) for child in ast.walk(node))
        )
        self.assertIsNotNone(dispatch_guard)
        self.assertTrue(
            any(
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "shared_state"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Constant)
                and node.value.value is None
                for node in ast.walk(session)
            ),
            "nonshared normal/abandon returns need a bound shared_state=None",
        )


class SharedDungeonTerminalReconnectPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        # Reuse only the fixture builders; do not import a TestCase class into
        # this module namespace, where unittest would collect its whole suite.
        from test_dungeon_instances import DungeonInstanceTests

        self.dungeon_fixture = object.__new__(DungeonInstanceTests)
        self.dungeon_fixture.store = self.store
        self.dungeon_fixture.install_context_policy(1)

    def _mixed_dungeon_party(self):
        from wakfu_server import dungeon_instances

        members, party_id = self.dungeon_fixture.party(2)
        route = dungeon_instances.route("jalato_normal")
        result = dungeon_instances.create_or_reuse(
            self.store,
            members[0]["account"],
            members[0]["generation"],
            members[0]["character"]["id"],
            route.key,
            authorize_entry=lambda _character, _route: True,
        )
        instance_id = result["instance_id"]
        monster = SimpleNamespace(
            ref_id=1,
            count=1,
            native_min_level=1,
            native_max_level=5,
            role="monster",
        )
        plan = SimpleNamespace(
            document_sha256="d" * 64,
            roster_ready=True,
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            ),
        )
        with self.store.connection() as db:
            initialize_run(db, instance_id, party_id, plan)
        return members, party_id, instance_id

    def test_two_owner_terminal_returns_keep_room_progress_through_busy_retry_and_reconnect(
        self,
    ):
        from wakfu_server import dungeon_instances
        from wakfu_server.combat_lifecycle import prepare_finish_shared, return_to_world
        from wakfu_server.combat_results import continuation
        from wakfu_server.fight_store import recoverable_finished_fight
        from wakfu_server.position_buffer import PositionOwnerBusy
        from wakfu_server.position_lifecycle import PendingPositionReturn
        from wakfu_server.wire import proto_fields

        members, party_id, instance_id = self._mixed_dungeon_party()
        left, right = members
        fight_id = create(
            self.store,
            left["account"],
            left["generation"],
            left["character"]["id"],
        )
        with self.store.connection() as db:
            self.assertTrue(
                join_participant(
                    self.store,
                    db,
                    right["account"],
                    right["generation"],
                    right["character"]["id"],
                    fight_id,
                    target_character_id=left["character"]["id"],
                    team=0,
                )
            )
            bind_encounter(
                db,
                instance_id,
                party_id,
                left["character"]["id"],
                fight_id,
                player_team=0,
            )

        actors = []
        metadata = {}
        for index, member in enumerate(members):
            character = member["character"]
            actor = Actor(
                character["id"],
                0,
                (index, 0, 0),
                character["hp"] - 5,
                6,
                3,
                100 - index,
                character["level"],
                member["account"],
                True,
                max_hp=character["max_hp"],
            )
            actors.append(actor)
            metadata[actor.id] = dict(
                kind="player",
                account_id=member["account"],
                name=character["name"],
                breed=character["breed"],
                is_male=character["sex"] == 0,
            )
        enemy_id = -fight_id
        actors.append(Actor(enemy_id, 1, (3, 0, 0), 8, 4, 2, 10, 1))
        metadata[enemy_id] = dict(kind="monster", ref=5525)
        cells = {actor.position for actor in actors}
        fight = Fight(
            fight_id,
            actors,
            cells,
            {
                0: {actor.position for actor in actors if actor.team == 0},
                1: {actors[-1].position},
            },
        )
        # Settlement receives the same authoritative terminal snapshot that the
        # normal winner path supplies after fight simulation.
        fight.phase, fight.winner = "finished", 0
        runtime = RuntimeMessages(fight)

        def commit_dungeon_result(db, _account_id, _character_id, defeated):
            self.assertTrue(defeated)
            room_result = settle_encounter(db, fight)
            self.assertEqual(room_result["current_room"], 2)
            return {"applied": True, "packets": []}

        owner_packets = prepare_finish_shared(
            self.store,
            left["account"],
            left["generation"],
            left["character"]["id"],
            runtime,
            metadata,
            duration_ms=4800,
            fight_instance_id=fight_id,
            policy_resolver=lambda _db, _member, _character: Policy(xp=0, kamas=0),
            expected_accounts={member["account"] for member in members},
            owner_character_ids={
                member["account"]: member["character"]["id"] for member in members
            },
            group_settlement=commit_dungeon_result,
        )
        self.assertEqual(set(owner_packets), {member["account"] for member in members})
        for member in members:
            packets = owner_packets[member["account"]]
            opcodes = [opcode for opcode, _payload in packets]
            self.assertLess(opcodes.index(12755), opcodes.index(12238))
            self.assertEqual(opcodes.count(12755), 1)
            report = dict(
                proto_fields(
                    next(payload for op, payload in packets if op == 12755)[12:]
                )
            )
            team_players = [
                dict(proto_fields(payload))
                for field, payload in proto_fields(report[42])
                if field == 18
            ]
            self.assertEqual(len(team_players), 2)

        with self.store.connection() as db:
            run = db.execute(
                "SELECT current_room,status,revision FROM dungeon_room_runs "
                "WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()
        self.assertEqual((run["current_room"], run["status"]), (2, "active"))

        ack_body = struct.pack(">iB", fight_id, 0)
        continuation(fight_id, ack_body)
        for member in members:
            current = self.store.character(member["account"], member["character"]["id"])
            returned = return_to_world(
                self.store,
                member["account"],
                member["generation"],
                current,
                runtime,
                ack_body,
                wp=6,
            )
            self.assertTrue(returned["applied"])
            self.assertEqual(returned["character"]["hp_damage"], 5)
            calls = []
            now = 0.0
            pending = PendingPositionReturn(now=now)

            def flush_owned_position():
                calls.append(member["account"])
                if member is right and now < 1.2:
                    raise PositionOwnerBusy("test-only transient owner contention")
                return 1

            completion = []
            for _ in range(20):
                done = pending.attempt(
                    now=now,
                    flush=flush_owned_position,
                    complete=lambda: completion.append(member["character"]["id"]),
                    busy=lambda _error, _attempt: None,
                )
                if done:
                    break
                now = max(now + 0.1, pending.next_attempt_at)
            self.assertTrue(pending.completed)
            if member is right:
                self.assertGreaterEqual(now, 1.2)
            self.assertEqual(len(completion), 1)
            self.assertGreater(len(calls), 2 if member is right else 0)
            self.assertTrue(
                pending.attempt(
                    now=now + 10,
                    flush=lambda: self.fail("completed ACK attempted another flush"),
                    complete=lambda: completion.append("duplicate"),
                    busy=lambda _error, _attempt: None,
                )
            )
            self.assertEqual(len(completion), 1)

        with self.store.connection() as db:
            exits = db.execute(
                "SELECT count(*) AS n FROM fight_health_exits WHERE fight_id=%s "
                "AND reason='return' AND return_acknowledged_at IS NOT NULL",
                (fight_id,),
            ).fetchone()["n"]
            reward_count = db.execute(
                "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                (fight_id,),
            ).fetchone()["n"]
        self.assertEqual(exits, 2)
        self.assertEqual(reward_count, 2)
        self.assertEqual(
            dungeon_instances.authorize_member(
                self.store,
                right["account"],
                right["generation"],
                right["character"]["id"],
                instance_id,
            )["role"],
            "member",
        )

        # A dropped transport can reconnect against the already committed room
        # result and replace only its session generation; no result/reward replay.
        self.store.end_session(right["account"], right["generation"])
        new_generation = self.store.begin_session(right["account"], ttl=10_000)
        self.store.select_character(
            right["account"], new_generation, right["character"]["id"]
        )
        reused = dungeon_instances.create_or_reuse(
            self.store,
            left["account"],
            left["generation"],
            left["character"]["id"],
            dungeon_instances.route("jalato_normal").key,
            authorize_entry=lambda _character, _route: True,
        )
        self.assertEqual(reused["instance_id"], instance_id)
        self.assertIsNotNone(
            dungeon_instances.authorize_member(
                self.store,
                right["account"],
                new_generation,
                right["character"]["id"],
                instance_id,
            )
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                    (instance_id,),
                ).fetchone()["current_room"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT session_generation FROM dungeon_instance_members "
                    "WHERE instance_id=%s AND character_id=%s",
                    (instance_id, right["character"]["id"]),
                ).fetchone()["session_generation"],
                new_generation,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()["n"],
                2,
            )
        self.assertIsNone(
            recoverable_finished_fight(
                self.store, right["account"], right["character"]["id"]
            )
        )
