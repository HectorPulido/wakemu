import struct
import unittest
import ast
from pathlib import Path

from postgres_case import PostgresCase
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.friendly_duel_wire import (
    cancellation,
    decode_answer,
    decode_challenge,
    invite,
)


class FriendlyDuelWireTests(unittest.TestCase):
    def test_adapter_routes_turn_expiry_to_shared_registry(self):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        adapter = CombatSessionAdapter(object())
        calls = []

        class RegistryStub:
            def expire_current_turn(self, fight_id, session, *, now_ms):
                calls.append((fight_id, session, now_ms))
                return True, None

        adapter.registry = RegistryStub()
        session = object()
        self.assertEqual(
            adapter.expire_current_turn(17, session, now_ms=1234),
            (True, None),
        )
        self.assertEqual(calls, [(17, session, 1234)])

    def test_native_fixtures_round_trip(self):
        challenge = bytes.fromhex("0000000000003039fffffffc0000000000000001")
        self.assertEqual(
            decode_challenge(challenge),
            {
                "target_character_id": 12345,
                "claimed_position": (-4, 0, 0),
                "auto_lock": False,
                "mode": 1,
            },
        )
        self.assertEqual(invite(12345, 1), (13179, bytes.fromhex("000000000000303901")))
        self.assertEqual(
            decode_answer(bytes.fromhex("00000000000030390100")),
            {"challenger_character_id": 12345, "accepted": True, "auto_lock": False},
        )
        self.assertEqual(
            decode_answer(bytes.fromhex("00000000000030390000"))["accepted"], False
        )
        self.assertEqual(cancellation(7), (12708, b"\x07"))

    def test_malformed_native_challenge_and_answer_reject(self):
        challenge = struct.pack(">qii hBB", 9, 1, 2, 3, 0, 1)
        answer = struct.pack(">qBB", 9, 1, 0)
        for body in (
            challenge[:-1],
            challenge + b"\0",
            struct.pack(">qii hBB", 0, 1, 2, 3, 0, 1),
            struct.pack(">qii hBB", 9, 1, 2, 3, 2, 1),
            struct.pack(">qii hBB", 9, 1, 2, 3, 0, 2),
        ):
            with self.assertRaises(ValueError):
                decode_challenge(body)
        for body in (
            answer[:-1],
            answer + b"\0",
            struct.pack(">qBB", 0, 1, 0),
            struct.pack(">qBB", 9, 2, 0),
            struct.pack(">qBB", 9, 1, 2),
        ):
            with self.assertRaises(ValueError):
                decode_answer(body)

    def test_dispatcher_routes_duel_abandon_through_shared_forfeit_and_settlement(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        route = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "opcode"
                and any(
                    isinstance(value, ast.Constant) and value.value == 13952
                    for value in test.comparators
                )
                for test in ast.walk(node.test)
            )
        )
        calls = [node for node in ast.walk(route) if isinstance(node, ast.Call)]
        forfeit = next(
            node
            for node in calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "forfeit_duel"
        )
        self.assertTrue(
            any(
                keyword.arg == "reason"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "defeat"
                for keyword in forfeit.keywords
            )
        )
        settlement = next(
            node
            for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == "complete_test_fight"
        )
        self.assertLess(forfeit.lineno, settlement.lineno)

    def test_dispatcher_skips_pve_world_roster_cleanup_for_duel_return(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        route = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "opcode"
                and any(
                    isinstance(value, ast.Constant) and value.value == 12925
                    for value in test.comparators
                )
                for test in ast.walk(node.test)
            )
        )
        duel_assignment = next(
            node
            for node in ast.walk(route)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "duel_return"
                for target in node.targets
            )
            and any(
                isinstance(child, ast.Constant) and child.value == "is_duel"
                for child in ast.walk(node.value)
            )
        )
        cleanup = next(
            node
            for node in ast.walk(route)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "dead_world_removals"
        )
        cleanup_guard = next(
            node
            for node in ast.walk(route)
            if isinstance(node, ast.If)
            and cleanup in list(ast.walk(node))
            and "duel_return" in ast.unparse(node.test)
        )
        self.assertIn("duel_return", ast.unparse(cleanup_guard.test))
        self.assertIn("not", ast.unparse(cleanup_guard.test))

    def test_dispatcher_does_not_reattach_owner_after_12925_return(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        adopt = next(
            node
            for node in ast.walk(session)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "adopt_shared_duel"
        )
        returned_guard = next(
            node
            for node in ast.walk(adopt)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "account_id"
            and any(
                isinstance(value, ast.Attribute) and value.attr == "returned"
                for value in node.test.comparators
            )
        )
        takeover = next(
            node
            for node in ast.walk(adopt)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "takeover"
        )
        self.assertLess(returned_guard.lineno, takeover.lineno)

    def test_dispatcher_checkpoints_before_retiring_last_duel_owner(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        route = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "opcode"
                and any(
                    isinstance(value, ast.Constant) and value.value == 12925
                    for value in test.comparators
                )
                for test in ast.walk(node.test)
            )
        )
        calls = [node for node in ast.walk(route) if isinstance(node, ast.Call)]
        terminal_save = next(
            node
            for node in calls
            if isinstance(node.func, ast.Name)
            and node.func.id == "checkpoint_fight"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "ended"
        )
        mark_returned = next(
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "mark_returned"
        )
        self.assertLess(terminal_save.lineno, mark_returned.lineno)


class FriendlyDuelRegistryTests(unittest.TestCase):
    def setUp(self):
        self.first = Session(1, 11, "one", 1134, 0)
        self.second = Session(2, 22, "two", 1134, 0)
        self.live = {self.first, self.second}
        self.registry = Registry(lambda session: session in self.live)
        first_actor = Actor(11, 0, (0, 0, 0), 60, 6, 3, 10, 1, 1, True)
        second_actor = Actor(22, 1, (2, 0, 0), 60, 6, 3, 9, 1, 2, True)
        self.fight = Fight(
            99,
            [first_actor, second_actor],
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )

    def test_registers_two_distinct_owners_on_opposing_teams(self):
        shared = self.registry.register_duel(
            self.fight,
            (self.first, self.second),
            auto_locked=True,
            initial_packets={1: ((12847, b"first"),), 2: ((12847, b"second"),)},
        )
        self.assertEqual(set(shared.participants), {1, 2})
        self.assertEqual(shared.connected, {1, 2})
        self.assertTrue(shared.auto_locked)
        self.assertIsNone(shared.group_lease)
        self.assertFalse(self.registry.lease_generation_active("one"))
        self.assertEqual(
            self.registry.drain(99, self.first)[0].packets, ((12847, b"first"),)
        )
        self.assertEqual(
            self.registry.drain(99, self.second)[0].packets, ((12847, b"second"),)
        )
        self.assertIs(self.registry.lookup_character(11), shared)
        self.assertIs(self.registry.lookup_character(22), shared)

    def test_unpublished_duel_reservation_can_be_compensated(self):
        self.registry.register_duel(
            self.fight,
            (self.first, self.second),
            initial_packets={1: (), 2: ()},
        )
        self.assertTrue(self.registry.unregister_unpublished(99))
        self.assertIsNone(self.registry.lookup_character(11))
        self.assertIsNone(self.registry.lookup_character(22))

    def test_disconnect_forfeits_without_fabricating_actor_death(self):
        self.registry.register_duel(
            self.fight,
            (self.first, self.second),
            initial_packets={1: (), 2: ()},
        )
        self.assertTrue(self.registry.forfeit_duel(self.first))
        self.assertEqual((self.fight.phase, self.fight.winner), ("finished", 1))
        self.assertEqual(self.fight.actors[11].hp, 60)
        shared = self.registry.lookup(99)
        self.assertEqual(shared.duel_finish_reason, "disconnect")
        self.assertEqual(shared.duel_disconnected_character_id, 11)

    def test_voluntary_duel_forfeit_settles_and_cleans_registry_after_both_return(self):
        shared = self.registry.register_duel(
            self.fight,
            (self.first, self.second),
            initial_packets={1: (), 2: ()},
        )
        shared.runtime = type(
            "Runtime",
            (),
            {
                "fight": shared.fight,
                "awaiting_ack": 1,
                "pending": [(12502, b"stale-turn")],
                "turn_deadline": 30,
                "deadline_turn": 1,
            },
        )()
        shared.ack.arm(1, (self.first, self.second))
        self.assertTrue(self.registry.forfeit_duel(self.first, reason="defeat"))
        self.assertEqual((shared.fight.phase, shared.fight.winner), ("finished", 1))
        self.assertEqual(shared.duel_finish_reason, "defeat")
        self.assertIsNone(shared.duel_disconnected_character_id)
        self.assertIsNone(shared.ack.turn)
        self.assertIsNone(shared.runtime.awaiting_ack)
        self.assertEqual(shared.runtime.pending, [])
        self.assertEqual(shared.fight.actors[11].hp, 60)
        self.assertTrue(
            self.registry.settle_finished(
                99,
                self.first,
                lambda _current: {
                    1: ((12755, b"first"),),
                    2: ((12755, b"second"),),
                },
            )
        )
        self.assertFalse(self.registry.mark_returned(99, self.first))
        self.assertIs(self.registry.lookup_character(11), shared)
        self.assertTrue(self.registry.mark_returned(99, self.second))
        self.assertIsNone(self.registry.lookup_character(11))
        self.assertIsNone(self.registry.lookup_character(22))
        self.assertNotIn(99, self.registry.fights)

    def test_disconnected_duelist_can_finalize_durable_result_before_logout(self):
        shared = self.registry.register_duel(
            self.fight,
            (self.first, self.second),
            initial_packets={1: (), 2: ()},
        )
        self.registry.disconnect(self.first)
        self.assertTrue(self.registry.forfeit_duel(self.first))
        delivered = {}
        self.assertTrue(
            self.registry.settle_finished(
                99,
                self.first,
                lambda current: {
                    1: ((12755, b"first-result"),),
                    2: ((12755, b"second-result"),),
                },
            )
        )
        self.assertTrue(shared.settlement_ready)
        self.assertEqual(shared.connected, {2})
        self.registry.dispatch_connected(
            99,
            lambda owner, batches: delivered.setdefault(
                owner.account_id,
                tuple(packet for batch in batches for packet in batch.packets),
            ),
        )
        self.assertEqual(delivered, {2: ((12755, b"second-result"),)})
        # The disconnected owner's immutable result remains queued for its
        # next lease even though it was excluded from socket delivery.
        self.assertEqual(shared.settlement_batches[1], ((12755, b"first-result"),))

    def test_rejects_same_team_stale_or_single_owner_rosters(self):
        same_team = Fight(
            100,
            [
                Actor(11, 0, (0, 0, 0), 60, 6, 3, 10, 1, 1, True),
                Actor(22, 0, (1, 0, 0), 60, 6, 3, 9, 1, 2, True),
                Actor(-1, 1, (2, 0, 0), 20, 4, 2, 1, 1),
            ],
            {(0, 0, 0), (1, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
        )
        with self.assertRaises(ValueError):
            self.registry.register_duel(same_team, (self.first, self.second))
        with self.assertRaises(ValueError):
            self.registry.register_duel(self.fight, (self.first,))
        self.live.remove(self.second)
        with self.assertRaises(ValueError):
            self.registry.register_duel(
                self.fight,
                (self.first, self.second),
                initial_packets={1: (), 2: ()},
            )


class FriendlyDuelStoreTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1_700_000_000
        self.account_a = self.store.register("duel-owner-a", "local-password")["id"]
        self.account_b = self.store.register("duel-owner-b", "local-password")["id"]
        self.char_a = self.store.create_character(self.account_a, "Duel Alpha")
        self.char_b = self.store.create_character(self.account_b, "Duel Bravo")
        self.generation_a = self.store.begin_session(self.account_a)
        self.generation_b = self.store.begin_session(self.account_b)
        self.store.select_character(
            self.account_a, self.generation_a, self.char_a["id"]
        )
        self.store.select_character(
            self.account_b, self.generation_b, self.char_b["id"]
        )
        self.session_a = Session(
            self.account_a, self.char_a["id"], self.generation_a, 1134, 0
        )
        self.session_b = Session(
            self.account_b, self.char_b["id"], self.generation_b, 1134, 0
        )
        self.set_policy()

    def set_policy(self, *, ttl=60, quarantine=60, value=None):
        from psycopg.types.json import Jsonb

        if value is None:
            value = {
                "invitation_ttl_seconds": ttl,
                "reply_quarantine_seconds": quarantine,
            }
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='friendly_duel_policy'",
                (Jsonb(value),),
            )

    def challenge(self):
        from wakfu_server.friendly_duels import invite_challenge

        body = struct.pack(">qii hBB", self.char_b["id"], 999, 999, 10, 0, 1)
        return invite_challenge(self.store, self.session_a, self.session_b, body)

    def answer(self, accepted, prepare=None):
        from wakfu_server.friendly_duels import answer_challenge

        body = struct.pack(">qBB", self.char_a["id"], int(accepted), 0)
        return answer_challenge(self.store, self.session_b, body, prepare_duel=prepare)

    def test_invitation_uses_server_position_and_refusal_creates_no_fight(self):
        from wakfu_server.friendly_duels import cancellation

        invite_result = self.challenge()
        self.assertEqual(invite_result["packet"][0], 13179)
        self.assertEqual(invite_result["source"]["x"], self.char_a["x"])
        self.assertNotEqual(invite_result["source"]["x"], 999)
        result = self.answer(False)
        self.assertEqual(result["packet"], cancellation(1))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_fights").fetchone()["n"], 0
            )
            row = db.execute(
                "SELECT status FROM friendly_duel_invitations WHERE id=%s",
                (invite_result["invitation_id"],),
            ).fetchone()
        self.assertEqual(row["status"], "rejected")

    def test_acceptance_preparation_failure_rolls_back_consent_and_fight(self):
        self.challenge()

        def fail(_db, _fight, _invite, _a, _b):
            raise ValueError("native serialization failed")

        with self.assertRaisesRegex(ValueError, "serialization"):
            self.answer(True, fail)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_fights").fetchone()["n"], 0
            )
            status = db.execute(
                "SELECT status FROM friendly_duel_invitations"
            ).fetchone()["status"]
        self.assertEqual(status, "pending")

    def test_invitation_is_single_pending_target_and_expires_without_fight(self):
        from wakfu_server.friendly_duels import answer_challenge, expire

        self.set_policy(ttl=10, quarantine=10)
        self.challenge()
        account_c = self.store.register("duel-owner-c", "local-password")["id"]
        char_c = self.store.create_character(account_c, "Duel Charlie")
        generation_c = self.store.begin_session(account_c)
        self.store.select_character(account_c, generation_c, char_c["id"])
        session_c = Session(account_c, char_c["id"], generation_c, 1134, 0)
        request_c = struct.pack(">qii hBB", self.char_b["id"], 0, 0, 0, 0, 1)
        with self.assertRaisesRegex(ValueError, "pending duel invitation"):
            from wakfu_server.friendly_duels import invite_challenge

            invite_challenge(self.store, session_c, self.session_b, request_c)
        # Invitation expiry occurs while both 60-second session leases remain live.
        self.store.clock = lambda: 1_700_000_011
        expired = expire(self.store)
        self.assertEqual(len(expired), 1)
        response = answer_challenge(
            self.store,
            self.session_b,
            struct.pack(">qBB", self.char_a["id"], 1, 0),
        )
        self.assertFalse(response["accepted"])
        self.assertEqual(response["fight_id"], None)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_fights").fetchone()["n"], 0
            )

    def test_stale_challenger_generation_cannot_be_accepted(self):
        self.challenge()
        self.store.end_session(self.account_a, self.generation_a)
        result = self.answer(True, lambda *_: self.fail("must not prepare stale duel"))
        self.assertFalse(result["accepted"])
        self.assertIsNone(result["fight_id"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_fights").fetchone()["n"], 0
            )
            self.assertEqual(
                db.execute("SELECT status FROM friendly_duel_invitations").fetchone()[
                    "status"
                ],
                "cancelled",
            )

    def test_stale_target_generation_cancels_old_invite_and_releases_target(self):
        from wakfu_server.friendly_duels import invite_challenge

        self.challenge()
        self.store.end_session(self.account_b, self.generation_b)
        self.generation_b = self.store.begin_session(self.account_b)
        self.store.select_character(
            self.account_b, self.generation_b, self.char_b["id"]
        )
        self.session_b = Session(
            self.account_b, self.char_b["id"], self.generation_b, 1134, 0
        )
        response = self.answer(
            True, lambda *_: self.fail("stale invite must not start")
        )
        self.assertFalse(response["accepted"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT status FROM friendly_duel_invitations").fetchone()[
                    "status"
                ],
                "cancelled",
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_fights").fetchone()["n"], 0
            )

        account_c = self.store.register("duel-owner-c-stale", "local-password")["id"]
        char_c = self.store.create_character(account_c, "Duel Charlie Stale")
        generation_c = self.store.begin_session(account_c)
        self.store.select_character(account_c, generation_c, char_c["id"])
        session_c = Session(account_c, char_c["id"], generation_c, 1134, 0)
        body = struct.pack(">qii hBB", self.char_b["id"], 0, 0, 0, 0, 1)
        self.set_policy(ttl=10, quarantine=10)
        result = invite_challenge(self.store, session_c, self.session_b, body)
        self.assertIsNotNone(result["invitation_id"])

    def test_policy_validation_and_same_pair_quarantine_are_configurable(self):
        for invalid in (
            {"invitation_ttl_seconds": True, "reply_quarantine_seconds": 60},
            {"invitation_ttl_seconds": 301, "reply_quarantine_seconds": 301},
            {"invitation_ttl_seconds": 10, "reply_quarantine_seconds": 9},
            {"invitation_ttl_seconds": 10, "reply_quarantine_seconds": 60, "extra": 1},
        ):
            self.set_policy(value=invalid)
            with self.assertRaisesRegex(ValueError, "policy"):
                self.challenge()
        self.set_policy(ttl=10, quarantine=20)
        self.challenge()
        self.answer(False)
        with self.assertRaisesRegex(ValueError, "same-pair"):
            self.challenge()
        self.store.clock = lambda: 1_700_000_020
        retry = self.challenge()
        self.assertEqual(retry["expires_at"].timestamp(), 1_700_000_030)

    def test_same_direction_quarantine_does_not_block_immediate_reverse_challenge(self):
        from wakfu_server.friendly_duels import invite_challenge

        original = self.challenge()
        refused = self.answer(False)
        self.assertEqual(refused["packet"], (12708, b"\x01"))
        with self.assertRaisesRegex(ValueError, "same-pair"):
            self.challenge()

        reverse_body = struct.pack(">qii hBB", self.char_a["id"], -10, -8, -1, 0, 1)
        reverse = invite_challenge(
            self.store, self.session_b, self.session_a, reverse_body
        )
        self.assertNotEqual(reverse["invitation_id"], original["invitation_id"])
        self.assertEqual(reverse["target_character_id"], self.char_a["id"])
        with self.store.connection() as db:
            statuses = [
                row["status"]
                for row in db.execute(
                    "SELECT status FROM friendly_duel_invitations ORDER BY id"
                ).fetchall()
            ]
            self.assertEqual(statuses, ["rejected", "pending"])

    def _create_accepted_fight(self):
        self.challenge()

        def prepare(db, fight_id, _invitation, _source, _target):
            self.assertEqual(db.info.transaction_status.name, "INTRANS")
            return {"fight_id": fight_id}, lambda: None

        return self.answer(True, prepare)

    def test_acceptance_creates_durable_opposing_player_teams_once(self):
        result = self._create_accepted_fight()
        self.assertTrue(result["accepted"])
        self.assertNotIn("rollback", result)
        with self.store.connection() as db:
            fight = db.execute(
                "SELECT status,fight_kind FROM combat_fights WHERE id=%s",
                (result["fight_id"],),
            ).fetchone()
            members = tuple(
                db.execute(
                    "SELECT character_id,account_id,team,session_generation "
                    "FROM combat_fight_participants WHERE fight_id=%s ORDER BY team",
                    (result["fight_id"],),
                )
            )
        self.assertEqual((fight["status"], fight["fight_kind"]), ("placement", "duel"))
        self.assertEqual([row["team"] for row in members], [0, 1])
        self.assertEqual(
            [row["character_id"] for row in members],
            [self.char_a["id"], self.char_b["id"]],
        )

    def test_pve_reward_and_drop_authorities_reject_a_duel_fight(self):
        from wakfu_server.combat_rewards import Policy, award_shared_member
        from wakfu_server.combat_drops import resolve as resolve_drops

        result = self._create_accepted_fight()
        fight_id = result["fight_id"]
        actors = [
            Actor(
                self.char_a["id"],
                0,
                (0, 0, 0),
                self.char_a["hp"],
                6,
                3,
                10,
                1,
                self.account_a,
                True,
                max_hp=self.char_a["max_hp"],
            ),
            Actor(
                self.char_b["id"],
                1,
                (2, 0, 0),
                self.char_b["hp"],
                6,
                3,
                9,
                1,
                self.account_b,
                True,
                max_hp=self.char_b["max_hp"],
            ),
        ]
        fight = Fight(
            fight_id,
            actors,
            {(0, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        fight.phase = "finished"
        fight.winner = 0
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s",
                (fight_id,),
            )

        with self.store.connection() as db:
            db.execute("SELECT 1")
            with self.assertRaisesRegex(ValueError, "finished owned durable"):
                award_shared_member(
                    self.store,
                    db,
                    self.account_a,
                    self.generation_a,
                    self.char_a["id"],
                    fight,
                    Policy(xp=500, kamas=25),
                )

        # Even a stale or injected PvE reward receipt cannot authorize drops
        # for a durable fight whose immutable kind is `duel`.
        with self.assertRaisesRegex(ValueError, "finished PvE victory"):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO fight_rewards(generation,fight_id,character_id,account_id,"
                    "xp,kamas,created_at,start_xp,end_xp,start_level,end_level) "
                    "VALUES(%s,%s,%s,%s,0,0,%s,0,0,1,1)",
                    (
                        self.generation_a,
                        fight_id,
                        self.char_a["id"],
                        self.account_a,
                        self.store.now(),
                    ),
                )
                resolve_drops(
                    self.store,
                    db,
                    account_id=self.account_a,
                    generation=self.generation_a,
                    character_id=self.char_a["id"],
                    fight_id=fight_id,
                    monsters=[{"actor_id": -7001, "reference": 4196}],
                    prospecting_bonus=0,
                    can_loot=True,
                    fight_context={},
                )

        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM fight_rewards WHERE fight_id=%s", (fight_id,)
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM fight_drop_awards WHERE fight_id=%s", (fight_id,)
                ).fetchone()
            )

    def test_acceptance_registers_both_leases_inside_the_locked_transaction(self):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        self.challenge()
        adapter = CombatSessionAdapter(self.store)
        actors = [
            Actor(
                self.char_a["id"], 0, (0, 0, 0), 60, 6, 3, 10, 1, self.account_a, True
            ),
            Actor(
                self.char_b["id"], 1, (2, 0, 0), 60, 6, 3, 9, 1, self.account_b, True
            ),
        ]

        def prepare(db, fight_id, _invitation, _source, _target):
            candidate = Fight(
                fight_id,
                actors,
                {(0, 0, 0), (2, 0, 0)},
                {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
            )
            shared = adapter.register_duel(
                candidate,
                (self.session_a, self.session_b),
                initial_packets={
                    self.account_a: ((12847, b"a"),),
                    self.account_b: ((12847, b"b"),),
                },
                db=db,
            )
            return shared, lambda: adapter.registry.unregister_unpublished(fight_id)

        result = self.answer(True, prepare)
        self.assertTrue(result["accepted"])
        self.assertIs(
            adapter.lookup_character(self.char_a["id"]),
            adapter.lookup_character(self.char_b["id"]),
        )
        self.assertEqual(
            adapter.registry.drain(result["fight_id"], self.session_b)[0].packets,
            ((12847, b"b"),),
        )

    def test_native_duel_placement_is_built_from_both_owned_snapshots(self):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.friendly_duel_runtime import prepare_and_register
        from wakfu_server.combat_terrain import map_geometry

        first_cell, second_cell = map_geometry(1134)["edges"][0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                (*first_cell, self.char_a["id"]),
            )
            db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                (*second_cell, self.char_b["id"]),
            )
        self.char_a = self.store.character(self.account_a, self.char_a["id"])
        self.char_b = self.store.character(self.account_b, self.char_b["id"])
        self.session_a = Session(
            self.account_a, self.char_a["id"], self.generation_a, 1134, 0
        )
        self.session_b = Session(
            self.account_b, self.char_b["id"], self.generation_b, 1134, 0
        )

        self.challenge()
        adapter = CombatSessionAdapter(self.store)

        def prepare(db, fight_id, invitation, source, target):
            prepared = prepare_and_register(
                self.store,
                adapter,
                db,
                fight_id,
                invitation,
                source,
                target,
                auto_locked=False,
            )
            return prepared, prepared["rollback"]

        result = self.answer(True, prepare)
        prepared = result["prepared"]
        fight = prepared["fight"]
        shared = prepared["shared"]
        self.assertEqual(set(fight.actors), {self.char_a["id"], self.char_b["id"]})
        self.assertEqual(
            {actor.team for actor in fight.actors.values() if actor.controlled}, {0, 1}
        )
        self.assertEqual(fight.native_effect_uid_next, 1)
        self.assertTrue(
            all(actor.effect_stats is not None for actor in fight.actors.values())
        )
        self.assertEqual(shared.join_context["monsters"], {})
        self.assertTrue(all(len(box) == 1 for box in shared.outboxes.values()))
        for session in prepared["sessions"]:
            batch = adapter.registry.drain(fight.id, session)[0]
            self.assertEqual(
                [opcode for opcode, _ in batch.packets], [13652, 12847, 13684, 13026]
            )
        # The owned placement codec emits direction 0 for each fresh player.
        # The canonical actors must retain that exact value so either owner's
        # first ordinary action can evaluate the opponent's native facing.
        from wakfu_server.combat_ordinary_authority import native_facing

        first, second = (fight.actors[identity] for identity in sorted(fight.actors))
        self.assertEqual((first.direction, second.direction), (0, 0))
        self.assertIn(native_facing(first, second), ("FRONT", "BACK", "SIDE"))
        self.assertIn(native_facing(second, first), ("FRONT", "BACK", "SIDE"))
        for actor, session in zip((first, second), prepared["sessions"]):
            payload, _effects = adapter.actor_payload(fight, actor, session)
            self.assertEqual(payload[27], actor.direction)

        # The first owner's ready packet previews a deep-copied Fight while
        # placement remains open. Its RuntimeMessages must point to that same
        # committed copy so checkpoint serialization accepts the pair.
        from wakfu_server.fight_checkpoint_store import snapshot

        for session in prepared["sessions"]:

            def ready(candidate, runtime):
                return adapter.ready_transition(
                    session,
                    candidate,
                    runtime,
                    True,
                    shared.join_context["monsters"],
                    fight_start=False,
                )

            adapter.registry.execute(
                fight.id,
                session,
                session.character_id,
                ready,
                require_turn=False,
            )
            canonical = adapter.registry.lookup(fight.id)
            self.assertIs(canonical.runtime.fight, canonical.fight)
            snapshot(canonical.fight, runtime=canonical.runtime)
        self.assertEqual(adapter.registry.lookup(fight.id).fight.phase, "active")

    def test_duel_settlement_heals_both_without_rewards_or_location_change(self):
        from wakfu_server.friendly_duels import settle

        result = self._create_accepted_fight()
        fight_id = result["fight_id"]
        for account, char in (
            (self.account_a, self.char_a),
            (self.account_b, self.char_b),
        ):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET hp=5,hp_damage=max_hp-5 WHERE id=%s AND account_id=%s",
                    (char["id"], account),
                )
                db.execute(
                    "UPDATE account_wallets SET kamas=31 WHERE account_id=%s",
                    (account,),
                )
        positions_before = {
            char["id"]: tuple(
                self.store.character(account, char["id"])[key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            )
            for account, char in (
                (self.account_a, self.char_a),
                (self.account_b, self.char_b),
            )
        }
        actors = [
            Actor(
                self.char_a["id"],
                0,
                (0, 0, 0),
                1,
                6,
                3,
                10,
                1,
                self.account_a,
                True,
                max_hp=self.char_a["max_hp"],
            ),
            Actor(
                self.char_b["id"],
                1,
                (2, 0, 0),
                1,
                6,
                3,
                9,
                1,
                self.account_b,
                True,
                max_hp=self.char_b["max_hp"],
            ),
        ]
        fight = Fight(
            fight_id,
            actors,
            {(0, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        fight.phase, fight.winner = "finished", 0
        with self.assertRaisesRegex(ValueError, "losing owner"):
            settle(
                self.store,
                self.account_a,
                self.generation_a,
                self.char_a["id"],
                fight,
                reason="disconnect",
                disconnected_character_id=self.char_a["id"],
            )
        settled = settle(
            self.store,
            self.account_a,
            self.generation_a,
            self.char_a["id"],
            fight,
            reason="disconnect",
            disconnected_character_id=self.char_b["id"],
        )
        self.assertEqual(settled["outcome"]["winner_character_id"], self.char_a["id"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits "
                    "WHERE fight_id=%s AND character_id=%s",
                    (fight_id, self.char_a["id"]),
                ).fetchone()["return_acknowledged_at"],
                None,
                "persisted health restoration is not proof the client received its report",
            )
        replacement_generation = self.store.begin_session(self.account_a)
        self.store.select_character(
            self.account_a, replacement_generation, self.char_a["id"]
        )
        from wakfu_server.fight_store import takeover_participant

        self.assertTrue(
            takeover_participant(
                self.store,
                self.account_a,
                replacement_generation,
                self.char_a["id"],
                fight_id,
                previous_generation=self.generation_a,
            ),
            "a disconnected owner must be able to replay a settled duel report before 12925",
        )
        from wakfu_server.friendly_duels import return_packets

        returned = return_packets(
            self.store,
            self.account_a,
            replacement_generation,
            self.char_a["id"],
            fight,
            struct.pack(">iB", fight_id, 0),
        )
        self.assertEqual(
            [opcode for opcode, _ in returned["packets"]],
            [13046, 12436, 13021, 13873],
        )
        self.assertEqual(returned["character"]["hp"], returned["character"]["max_hp"])
        for account, char in (
            (self.account_a, self.char_a),
            (self.account_b, self.char_b),
        ):
            saved = self.store.character(account, char["id"])
            self.assertEqual(saved["hp"], saved["max_hp"])
            self.assertEqual(saved["hp_damage"], 0)
            self.assertFalse(saved["health_dead"])
            self.assertEqual(
                tuple(saved[key] for key in ("map_id", "instance_id", "x", "y", "z")),
                positions_before[char["id"]],
            )
            self.assertEqual(saved["kamas"], 31)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"], 0
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM friendly_duel_outcomes"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()["n"],
                2,
            )
            acknowledged = db.execute(
                "SELECT return_acknowledged_at FROM fight_health_exits "
                "WHERE fight_id=%s AND character_id=%s",
                (fight_id, self.char_a["id"]),
            ).fetchone()["return_acknowledged_at"]
            self.assertIsNotNone(acknowledged)
            self.assertIsNone(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits "
                    "WHERE fight_id=%s AND character_id=%s",
                    (fight_id, self.char_b["id"]),
                ).fetchone()["return_acknowledged_at"]
            )
        # Replaying settlement after later world damage cannot heal again.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=17,hp_damage=max_hp-17 WHERE id=%s",
                (self.char_a["id"],),
            )
        replay = settle(
            self.store, self.account_a, replacement_generation, self.char_a["id"], fight
        )
        self.assertTrue(replay["replayed"])
        self.assertEqual(
            self.store.character(self.account_a, self.char_a["id"])["hp"], 17
        )
        next_generation = self.store.begin_session(self.account_a)
        self.store.select_character(self.account_a, next_generation, self.char_a["id"])
        with self.assertRaisesRegex(ValueError, "already acknowledged return"):
            takeover_participant(
                self.store,
                self.account_a,
                next_generation,
                self.char_a["id"],
                fight_id,
                previous_generation=replacement_generation,
            )

    def test_settlement_failure_rolls_back_hp_return_and_outcome(self):
        from wakfu_server.friendly_duels import settle

        result = self._create_accepted_fight()
        fight_id = result["fight_id"]
        actors = [
            Actor(
                self.char_a["id"], 0, (0, 0, 0), 1, 6, 3, 10, 1, self.account_a, True
            ),
            Actor(self.char_b["id"], 1, (2, 0, 0), 1, 6, 3, 9, 1, self.account_b, True),
        ]
        fight = Fight(
            fight_id,
            actors,
            {(0, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        fight.phase, fight.winner = "finished", 0
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=9,hp_damage=max_hp-9,x=x+10 WHERE id IN (%s,%s)",
                (self.char_a["id"], self.char_b["id"]),
            )
            db.execute(
                "CREATE FUNCTION reject_duel_outcome() RETURNS trigger LANGUAGE plpgsql AS $$"
                "BEGIN RAISE EXCEPTION 'injected duel receipt failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_duel_outcome BEFORE INSERT ON friendly_duel_outcomes "
                "FOR EACH ROW EXECUTE FUNCTION reject_duel_outcome()"
            )
        before = {
            char["id"]: self.store.character(account, char["id"])
            for account, char in (
                (self.account_a, self.char_a),
                (self.account_b, self.char_b),
            )
        }
        with self.assertRaisesRegex(Exception, "injected duel receipt failure"):
            settle(
                self.store, self.account_a, self.generation_a, self.char_a["id"], fight
            )
        with self.store.connection() as db:
            db.execute("DROP TRIGGER reject_duel_outcome ON friendly_duel_outcomes")
            db.execute("DROP FUNCTION reject_duel_outcome()")
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()["status"],
                "placement",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM friendly_duel_outcomes"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits WHERE fight_id=%s",
                    (fight_id,),
                ).fetchone()["n"],
                0,
            )
        for account, char in (
            (self.account_a, self.char_a),
            (self.account_b, self.char_b),
        ):
            after = self.store.character(account, char["id"])
            self.assertEqual(after["hp"], before[char["id"]]["hp"])
            self.assertEqual(after["hp_damage"], before[char["id"]]["hp_damage"])
            self.assertEqual(after["x"], before[char["id"]]["x"])
