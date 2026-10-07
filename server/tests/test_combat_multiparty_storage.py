import struct
import threading
from unittest.mock import patch
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

from postgres_case import PostgresCase
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.fight_store import (
    create,
    join_participant,
    settle_shared,
    takeover_participant,
)
from wakfu_server.combat_session_adapter import CombatSessionAdapter


class SharedFightStorageTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.left_account, self.left_char, self.left_gen = self._player("Shared Left")
        self.right_account, self.right_char, self.right_gen = self._player(
            "Shared Right"
        )
        self.fight_id = create(
            self.store, self.left_account, self.left_gen, self.left_char
        )
        with self.store.connection() as db:
            self.assertTrue(
                join_participant(
                    self.store,
                    db,
                    self.right_account,
                    self.right_gen,
                    self.right_char,
                    self.fight_id,
                    target_character_id=self.left_char,
                    team=0,
                )
            )
        self.fight = Fight(
            self.fight_id,
            [
                Actor(
                    self.left_char,
                    0,
                    (0, 0, 0),
                    50,
                    6,
                    3,
                    100,
                    1,
                    self.left_account,
                    True,
                ),
                Actor(
                    self.right_char,
                    0,
                    (1, 0, 0),
                    45,
                    6,
                    3,
                    90,
                    1,
                    self.right_account,
                    True,
                ),
                Actor(-200, 1, (3, 0, 0), 12, 4, 2, 10, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        self.checkpoints = Checkpoints(self.store)

    def _player(self, name):
        account = self.store.register(name.lower().replace(" ", "-"), "test-password")[
            "id"
        ]
        character = self.store.create_character(account, name)["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character)
        return account, character, generation

    def test_join_is_transactional_same_team_placement_only_and_idempotent(self):
        with self.store.connection() as db:
            self.assertFalse(
                join_participant(
                    self.store,
                    db,
                    self.right_account,
                    self.right_gen,
                    self.right_char,
                    self.fight_id,
                    target_character_id=self.left_char,
                    team=0,
                )
            )
        with self.store.connection() as db:
            rows = tuple(
                db.execute(
                    "SELECT character_id,account_id,team,session_generation "
                    "FROM combat_fight_participants WHERE fight_id=%s ORDER BY character_id",
                    (self.fight_id,),
                )
            )
        self.assertEqual(
            [(r["character_id"], r["account_id"], r["team"]) for r in rows],
            [
                (self.left_char, self.left_account, 0),
                (self.right_char, self.right_account, 0),
            ],
        )
        self.assertEqual(
            {r["session_generation"] for r in rows}, {self.left_gen, self.right_gen}
        )

        with self.assertRaises(ValueError):
            with self.store.connection() as db:
                join_participant(
                    self.store,
                    db,
                    self.right_account,
                    self.right_gen,
                    self.right_char,
                    self.fight_id,
                    target_character_id=self.left_char,
                    team=1,
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (self.fight_id,)
            )
        third_account, third_char, third_gen = self._player("Shared Third")
        with self.assertRaisesRegex(ValueError, "open for participant admission"):
            with self.store.connection() as db:
                join_participant(
                    self.store,
                    db,
                    third_account,
                    third_gen,
                    third_char,
                    self.fight_id,
                    target_character_id=self.left_char,
                    team=0,
                )

    def test_one_shared_checkpoint_has_membership_authorization_and_global_cas(self):
        self.assertEqual(
            self.checkpoints.save(self.left_account, self.left_gen, self.fight), 1
        )
        self.assertEqual(
            self.checkpoints.read(self.right_account, self.fight_id)["revision"], 1
        )
        self.fight.actors[self.right_char].hp -= 7
        self.assertEqual(
            self.checkpoints.save(
                self.right_account, self.right_gen, self.fight, expected_revision=1
            ),
            2,
        )
        left_view = self.checkpoints.read(self.left_account, self.fight_id)
        self.assertEqual(left_view["revision"], 2)
        self.assertEqual(
            left_view["snapshot"]["actors"][str(self.right_char)]["hp"], 38
        )
        outsider_account, _, _ = self._player("Shared Outsider")
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.checkpoints.read(outsider_account, self.fight_id)
        with self.assertRaises(ValueError):
            self.checkpoints.save(
                self.left_account, self.left_gen, self.fight, expected_revision=1
            )

        stale = self.store.begin_session(self.right_account)
        self.store.select_character(self.right_account, stale, self.right_char)
        with self.assertRaisesRegex(ValueError, "stale"):
            self.checkpoints.save(
                self.right_account, self.right_gen, self.fight, expected_revision=2
            )
        self.assertTrue(
            takeover_participant(
                self.store,
                self.right_account,
                stale,
                self.right_char,
                self.fight_id,
                previous_generation=self.right_gen,
            )
        )
        self.assertEqual(
            self.checkpoints.save(
                self.right_account, stale, self.fight, expected_revision=2
            ),
            3,
        )

    def _finish(self):
        self.fight.phase = "finished"
        self.fight.winner = 0

    def _award_all(self, db, members, fight, *, fail_after_first=False):
        from wakfu_server.combat_rewards import Policy, award_shared_member

        results = []
        for index, member in enumerate(members):
            results.append(
                award_shared_member(
                    self.store,
                    db,
                    member["account_id"],
                    member["session_generation"],
                    member["character_id"],
                    fight,
                    Policy(xp=101 + index, kamas=7 + index),
                )
            )
            if fail_after_first and index == 0:
                raise ValueError("injected second-owner settlement failure")
        return results

    def test_settlement_rolls_back_all_members_then_commits_and_replays_once(self):
        self._finish()
        before = {
            self.left_char: self.store.character(self.left_account, self.left_char)[
                "xp"
            ],
            self.right_char: self.store.character(self.right_account, self.right_char)[
                "xp"
            ],
        }
        with self.assertRaisesRegex(ValueError, "second-owner"):
            settle_shared(
                self.store,
                self.left_account,
                self.left_gen,
                self.left_char,
                self.fight,
                lambda db, members, fight: self._award_all(
                    db, members, fight, fail_after_first=True
                ),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "placement",
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"], 0
            )
        self.assertEqual(
            self.store.character(self.left_account, self.left_char)["xp"],
            before[self.left_char],
        )

        # Replace the second owner's socket generation. The final live owner is
        # still allowed to settle the frozen durable roster exactly once.
        replacement = self.store.begin_session(self.right_account)
        self.store.select_character(self.right_account, replacement, self.right_char)
        results = settle_shared(
            self.store,
            self.left_account,
            self.left_gen,
            self.left_char,
            self.fight,
            self._award_all,
        )
        self.assertEqual([item["awarded"] for item in results], [True, True])
        self.assertEqual(
            [
                self.store.character(self.left_account, self.left_char)["xp"]
                - before[self.left_char],
                self.store.character(self.right_account, self.right_char)["xp"]
                - before[self.right_char],
            ],
            [101, 102],
        )
        replay = settle_shared(
            self.store,
            self.left_account,
            self.left_gen,
            self.left_char,
            self.fight,
            self._award_all,
        )
        self.assertEqual([item["awarded"] for item in replay], [False, False])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"], 2
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "finished",
            )

    def test_concurrent_finalizers_serialize_and_apply_each_owner_once(self):
        self._finish()
        barrier = threading.Barrier(2)

        def finalize(account, generation, character):
            barrier.wait(timeout=5)
            return settle_shared(
                self.store,
                account,
                generation,
                character,
                self.fight,
                self._award_all,
            )

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(
                workers.map(
                    lambda args: finalize(*args),
                    (
                        (self.left_account, self.left_gen, self.left_char),
                        (self.right_account, self.right_gen, self.right_char),
                    ),
                )
            )
        awarded = sorted(item["awarded"] for batch in results for item in batch)
        self.assertEqual(awarded, [False, False, True, True])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                2,
            )

    def test_finalizer_must_take_over_durable_generation_before_settlement(self):
        self._finish()
        replacement = self.store.begin_session(self.left_account)
        self.store.select_character(self.left_account, replacement, self.left_char)
        with self.assertRaisesRegex(ValueError, "durable fight lease"):
            settle_shared(
                self.store,
                self.left_account,
                replacement,
                self.left_char,
                self.fight,
                self._award_all,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "placement",
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"],
                0,
            )

        self.assertTrue(
            takeover_participant(
                self.store,
                self.left_account,
                replacement,
                self.left_char,
                self.fight_id,
                previous_generation=self.left_gen,
            )
        )
        awards = settle_shared(
            self.store,
            self.left_account,
            replacement,
            self.left_char,
            self.fight,
            self._award_all,
        )
        self.assertEqual([award["awarded"] for award in awards], [True, True])

    def test_shared_lifecycle_awards_and_builds_private_reports_for_every_owner(self):
        from wakfu_server.combat_lifecycle import prepare_finish_shared
        from wakfu_server.combat_rewards import Policy
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        self._finish()
        runtime = RuntimeMessages(self.fight)
        metadata = {
            self.left_char: dict(
                kind="player",
                account_id=self.left_account,
                name="Shared Left",
                breed=2,
                is_male=True,
            ),
            self.right_char: dict(
                kind="player",
                account_id=self.right_account,
                name="Shared Right",
                breed=2,
                is_male=False,
            ),
            -200: dict(kind="monster", ref=5525),
        }

        def policy(db, member, character):
            return Policy(xp=101, kamas=7)

        def loot(db, member, reward):
            return {
                "loots": [dict(reference=2026, quantity=1)],
                "packets": [(13713, str(member["character_id"]).encode())],
            }

        runtime.awaiting_ack = {"turn": 17}
        runtime.pending = [(12916, b"pending")]

        def fail_on_second_owner(db, member, reward):
            if member["character_id"] == self.right_char:
                raise ValueError("injected second-owner loot failure")
            return loot(db, member, reward)

        with self.assertRaisesRegex(ValueError, "second-owner loot"):
            prepare_finish_shared(
                self.store,
                self.left_account,
                self.left_gen,
                self.left_char,
                runtime,
                metadata,
                duration_ms=100,
                fight_instance_id=self.fight_id,
                policy_resolver=policy,
                loot_resolver=fail_on_second_owner,
            )
        self.assertEqual(runtime.awaiting_ack, {"turn": 17})
        self.assertEqual(runtime.pending, [(12916, b"pending")])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "placement",
            )

        # Packet framing is part of settlement validity. An opcode that cannot
        # fit the transport header must fail before the rewards transaction
        # commits, rather than failing later in the socket writer.
        with patch(
            "wakfu_server.combat_lifecycle.combat_results.finish_messages",
            return_value=[(0x10000, b"invalid opcode")],
        ):
            with self.assertRaisesRegex(ValueError, "invalid native packet"):
                prepare_finish_shared(
                    self.store,
                    self.left_account,
                    self.left_gen,
                    self.left_char,
                    runtime,
                    metadata,
                    duration_ms=100,
                    fight_instance_id=self.fight_id,
                    policy_resolver=policy,
                    expected_accounts={self.left_account, self.right_account},
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "placement",
            )

        result = prepare_finish_shared(
            self.store,
            self.left_account,
            self.left_gen,
            self.left_char,
            runtime,
            metadata,
            duration_ms=100,
            fight_instance_id=self.fight_id,
            policy_resolver=policy,
            loot_resolver=loot,
        )
        self.assertEqual(set(result), {self.left_account, self.right_account})
        self.assertTrue(
            all(
                any(opcode == 12755 for opcode, payload in packets)
                for packets in result.values()
            )
        )
        self.assertNotEqual(
            next(
                payload
                for opcode, payload in result[self.left_account]
                if opcode == 12755
            ),
            next(
                payload
                for opcode, payload in result[self.right_account]
                if opcode == 12755
            ),
        )
        self.assertEqual(
            [
                self.store.character(self.left_account, self.left_char)["xp"],
                self.store.character(self.right_account, self.right_char)["xp"],
            ],
            [101, 101],
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_rewards WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "finished",
            )

    def test_adapter_settled_takeover_replays_owner_batch_and_fences_return(self):
        adapter = CombatSessionAdapter(self.store)
        left = adapter.session(
            self.left_account,
            self.left_gen,
            self.store.character(self.left_account, self.left_char),
        )
        right_actor = self.fight.actors.pop(self.right_char)
        adapter.registry.register(self.fight, left, runtime={"shared": self.fight})
        right_character = self.store.character(self.right_account, self.right_char)
        right = adapter.session(self.right_account, self.right_gen, right_character)
        adapter.join(
            right,
            struct.pack(">qB", self.left_char, 0),
            right_actor,
            actor_payload=lambda *args: (b"actor", b"effects"),
            bootstrap_packets=lambda *args: ((12847, b"joined"),),
        )
        shared_fight = adapter.registry.lookup(self.fight_id).fight
        self.fight = shared_fight
        self._finish()
        settle_shared(
            self.store,
            self.left_account,
            self.left_gen,
            self.left_char,
            self.fight,
            lambda db, members, fight: None,
        )
        adapter.settle_finished(
            left,
            self.fight_id,
            lambda shared: {
                self.left_account: ((12755, b"left-result"),),
                self.right_account: ((12755, b"right-result"),),
            },
        )
        adapter.disconnect(right)
        replacement_generation = self.store.begin_session(self.right_account)
        self.store.select_character(
            self.right_account, replacement_generation, self.right_char
        )
        replacement = adapter.session(
            self.right_account, replacement_generation, right_character
        )
        adapter.takeover_settled(replacement, self.fight_id)
        replay = adapter.drain(replacement, self.fight_id)
        self.assertEqual(
            [batch.packets for batch in replay], [((12755, b"right-result"),)]
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s AND character_id=%s",
                (self.fight_id, self.right_char),
            ).fetchone()
        self.assertEqual(row["session_generation"], replacement_generation)
        self.assertFalse(adapter.mark_returned(replacement, self.fight_id))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            adapter.takeover_settled(replacement, self.fight_id)

    def test_unreturned_finished_participant_can_take_over_but_acknowledged_cannot(
        self,
    ):
        self._finish()
        settle_shared(
            self.store,
            self.left_account,
            self.left_gen,
            self.left_char,
            self.fight,
            lambda db, members, fight: (),
        )
        replacement = self.store.begin_session(self.right_account)
        self.store.select_character(self.right_account, replacement, self.right_char)
        self.assertTrue(
            takeover_participant(
                self.store,
                self.right_account,
                replacement,
                self.right_char,
                self.fight_id,
                previous_generation=self.right_gen,
            )
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO fight_health_exits(generation,fight_id,character_id,reason,created_at,return_acknowledged_at) "
                "VALUES(%s,%s,%s,'return',%s,%s)",
                (
                    replacement,
                    self.fight_id,
                    self.right_char,
                    self.store.now(),
                    self.store.now(),
                ),
            )
        newer = self.store.begin_session(self.right_account)
        self.store.select_character(self.right_account, newer, self.right_char)
        with self.assertRaisesRegex(ValueError, "already acknowledged return"):
            takeover_participant(
                self.store,
                self.right_account,
                newer,
                self.right_char,
                self.fight_id,
                previous_generation=replacement,
            )

    def test_session_adapter_persists_join_before_publishing_shared_batches(self):
        adapter = CombatSessionAdapter(self.store)
        left = adapter.session(
            self.left_account,
            self.left_gen,
            {"id": self.left_char, "map_id": 1134, "instance_id": 0},
        )
        right = adapter.session(
            self.right_account,
            self.right_gen,
            {"id": self.right_char, "map_id": 1134, "instance_id": 0},
        )
        starter_fight = Fight(
            self.fight_id,
            [
                deepcopy(self.fight.actors[self.left_char]),
                deepcopy(self.fight.actors[-200]),
            ],
            self.fight.walkable,
            self.fight.placement,
        )
        shared = adapter.register(left, starter_fight)
        actor = adapter.player_actor(right, team=0)
        joined = adapter.join(
            right,
            struct.pack(">qB", self.left_char, 0),
            actor,
            bootstrap_packets=lambda *_: [(12847, b"native-placement")],
        )
        self.assertIs(joined, shared)
        with self.store.connection() as db:
            rows = tuple(
                db.execute(
                    "SELECT character_id,account_id,session_generation "
                    "FROM combat_fight_participants WHERE fight_id=%s "
                    "ORDER BY character_id",
                    (self.fight_id,),
                )
            )
        self.assertEqual(
            [
                (row["character_id"], row["account_id"], row["session_generation"])
                for row in rows
            ],
            [
                (self.left_char, self.left_account, self.left_gen),
                (self.right_char, self.right_account, self.right_gen),
            ],
        )
        adapter.publish(left, self.fight_id, [(12502, b"shared-turn")])
        left_batches = adapter.drain(left, self.fight_id)
        right_batches = adapter.drain(right, self.fight_id)
        self.assertEqual(
            [packet[0] for packet in left_batches[0].packets], [13091, 13026]
        )
        self.assertEqual(right_batches[0].packets, ((12847, b"native-placement"),))
        self.assertEqual(left_batches[1].packets, ((12502, b"shared-turn"),))
        self.assertEqual(right_batches[1].packets, ((12502, b"shared-turn"),))
        self.assertEqual(left_batches[1].sequence, right_batches[1].sequence)
        self.assertEqual(left_batches[1].sequence, 2)
