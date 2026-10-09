from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import SimpleNamespace
import threading
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import dungeon_instances, player_parties
from wakfu_server.maps.dungeon_progression import (
    bind_encounter,
    initialize_run,
    progression_result,
    settle_encounter,
)


class DungeonProgressionTests(unittest.TestCase):
    def test_victory_advances_one_room(self):
        self.assertEqual(
            dict(victory=True, completed=False, current_room=2),
            progression_result(1, 3, 0, 0),
        )

    def test_defeat_does_not_advance(self):
        self.assertEqual(
            dict(victory=False, completed=False, current_room=2),
            progression_result(2, 3, 0, 1),
        )

    def test_last_victory_completes_without_nonexistent_room(self):
        self.assertEqual(
            dict(victory=True, completed=True, current_room=3),
            progression_result(3, 3, 1, 1),
        )

    def test_missing_result_or_invalid_room_rejected(self):
        for args in [(1, 3, 0, None), (0, 3, 0, 0), (4, 3, 0, 0), (1, 3, 0, True)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                progression_result(*args)


@dataclass(frozen=True)
class _Plan:
    roster_ready: bool = True
    document_sha256: str = "a" * 64
    rooms: tuple = ()


class DungeonProgressionPostgresTests(PostgresCase):
    """Exercise durable progression only in PostgresCase's disposable schema."""

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy()
        self.members, self.party_id = self.party(2)
        self.instance_id = self.create(self.members[0])["instance_id"]
        monster = SimpleNamespace(
            ref_id=1,
            count=1,
            native_min_level=1,
            native_max_level=5,
            role="monster",
        )
        rooms = tuple(
            SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
        )
        self.plan = _Plan(rooms=rooms)
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, self.plan)

    def install_context_policy(self):
        route = dungeon_instances.route("jalato_normal")
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_context_policy_versions(route_key,policy_version,"
                "template_id,definition_id,max_level,min_level,difficulty_level,"
                "is_difficulty_available,can_increase_difficulty,"
                "is_competitive_cancelled,allowed_ids,provenance) "
                "VALUES(%s,1,%s,%s,0,0,2,false,true,false,%s,%s)",
                (
                    route.key,
                    route.template_id,
                    route.definition_id,
                    [777777],
                    "synthetic progression test policy",
                ),
            )
            db.execute(
                "INSERT INTO dungeon_context_active_policies(route_key,policy_version) VALUES(%s,1)",
                (route.key,),
            )

    def player(self):
        account = self.store.register("dp" + uuid.uuid4().hex[:10], "test-password")[
            "id"
        ]
        suffix = "".join(
            chr(ord("a") + int(value, 16)) for value in uuid.uuid4().hex[:9]
        )
        character = self.store.create_character(account, "Dpg" + suffix)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-245,y=-90,z=2 WHERE id=%s",
                (character["id"],),
            )
        return {"account": account, "generation": generation, "character": character}

    def party(self, count):
        members = [self.player() for _ in range(count)]
        party_id = None
        for member in members[1:]:
            token = player_parties.invite(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                member["character"]["id"],
            )
            party_id = player_parties.answer(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                token,
                True,
            )
        return members, party_id

    def create(self, leader):
        return dungeon_instances.create_or_reuse(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            "jalato_normal",
            authorize_entry=lambda _character, _route: True,
        )

    def make_fight(self, character, *, participant_team=0):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,%s)",
                (
                    fight_id,
                    character["character"]["id"],
                    character["account"],
                    participant_team,
                ),
            )
        return fight_id

    def bind(
        self,
        fight_id,
        *,
        character=None,
        instance_id=None,
        party_id=None,
        player_team=0,
    ):
        character = character or self.members[0]
        with self.store.connection() as db:
            return bind_encounter(
                db,
                self.instance_id if instance_id is None else instance_id,
                self.party_id if party_id is None else party_id,
                character["character"]["id"],
                fight_id,
                player_team=player_team,
            )

    def finish(self, fight_id, winner=0, *, store=None):
        store = store or self.store
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            return settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=winner)
            )

    def run_state(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT current_room,status,revision FROM dungeon_room_runs WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()

    def test_victory_replay_is_idempotent_after_later_room_progress(self):
        first = self.make_fight(self.members[0])
        self.bind(first)
        self.assertFalse(self.finish(first)["replay"])
        self.assertEqual(2, self.run_state()["current_room"])

        second = self.make_fight(self.members[0])
        self.bind(second)
        self.assertFalse(self.finish(second)["replay"])
        self.assertTrue(self.finish(first)["replay"])
        with self.assertRaisesRegex(ValueError, "Conflicting replayed"):
            self.finish(first, winner=1)
        self.assertEqual(
            (2, 3), (self.run_state()["current_room"], self.run_state()["revision"])
        )

    def test_defeat_keeps_room_and_allows_retry_with_new_fight(self):
        defeated = self.make_fight(self.members[0])
        self.bind(defeated)
        result = self.finish(defeated, winner=1)
        self.assertFalse(result["victory"])
        self.assertEqual(
            (1, 2), (self.run_state()["current_room"], self.run_state()["revision"])
        )
        retry = self.make_fight(self.members[0])
        self.bind(retry)
        self.assertEqual(1, self.run_state()["current_room"])
        self.assertTrue(self.finish(retry)["victory"])
        self.assertEqual(2, self.run_state()["current_room"])

    def test_wrong_instance_party_team_and_nonmember_are_rejected(self):
        fight = self.make_fight(self.members[0])
        with self.assertRaises(ValueError):
            self.bind(fight, instance_id=self.instance_id + 500)
        with self.assertRaises(ValueError):
            self.bind(fight, party_id=self.party_id + 500)
        with self.assertRaises(ValueError):
            self.bind(fight, player_team=1)

        outsider = self.player()
        outsider_fight = self.make_fight(outsider)
        with self.assertRaises(ValueError):
            self.bind(outsider_fight, character=outsider)
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_room_encounters WHERE fight_id=ANY(%s)",
                    ([fight, outsider_fight],),
                ).fetchone()["n"],
            )

    def test_concurrent_duplicate_finish_advances_once(self):
        fight = self.make_fight(self.members[0])
        self.bind(fight)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
            )
        barrier = threading.Barrier(2)

        def settle():
            store = self.reopen()
            barrier.wait(timeout=5)
            with store.connection() as db:
                return settle_encounter(
                    db, SimpleNamespace(id=fight, phase="finished", winner=0)
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                future.result(timeout=10)
                for future in [pool.submit(settle) for _ in range(2)]
            ]
        self.assertEqual([False, True], sorted(result["replay"] for result in results))
        self.assertEqual(
            (2, 2), (self.run_state()["current_room"], self.run_state()["revision"])
        )

    def test_transaction_rollback_restores_room_and_encounter(self):
        fight = self.make_fight(self.members[0])
        self.bind(fight)
        with self.assertRaisesRegex(RuntimeError, "force rollback"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight,)
                )
                settle_encounter(
                    db, SimpleNamespace(id=fight, phase="finished", winner=0)
                )
                raise RuntimeError("force rollback")
        self.assertEqual(
            (1, 1), (self.run_state()["current_room"], self.run_state()["revision"])
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT status,result_revision FROM dungeon_room_encounters WHERE fight_id=%s",
                (fight,),
            ).fetchone()
        self.assertEqual(("active", None), (row["status"], row["result_revision"]))
        self.assertFalse(self.finish(fight)["replay"])
        self.assertEqual(2, self.run_state()["current_room"])
