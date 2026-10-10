"""Real PostgreSQL admission of same-account heroes into one combat."""
import base64
import json
import os
from pathlib import Path
import unittest

from postgres_case import PostgresCase
from wakfu_server import fight_store
from wakfu_server.characters import heroes
from wakfu_server.combat.combat_heroes import admit_owned_heroes, player_actor
from wakfu_server.combat.combat_shared import Session
from wakfu_server.combat.combat_state import Actor, Fight


class CombatHeroesPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("combat-heroes", "heroes-password")["id"]
        self.main = self.store.create_character(self.account, "Combat Main")
        self.hero_a = self.store.create_character(self.account, "Combat Hero A")
        self.hero_b = self.store.create_character(self.account, "Combat Hero B")
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=0,y=0,z=0 "
                "WHERE id=ANY(%s)",
                ([self.main["id"], self.hero_a["id"], self.hero_b["id"]],),
            )
        self.main = self.store.character(self.account, self.main["id"])
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_b["id"],
        )
        self.session = Session(
            self.account,
            self.main["id"],
            self.generation,
            self.main["map_id"],
            self.main["instance_id"],
        )
        self.fight_id = fight_store.create(
            self.store, self.account, self.generation, self.main["id"], team=0
        )
        self.fight = self._fight()

    def _fight(self, extra_team_zero=0):
        allies = [player_actor(self.store.character(self.account, self.main["id"]), 0)]
        for index in range(extra_team_zero):
            allies.append(Actor(-300 - index, 0, (index + 1, 0, 0), 20, 6, 3, 50, 1))
        enemy_position = (5, 0, 0)
        actors = allies + [Actor(-200, 1, enemy_position, 20, 4, 2, 10, 1)]
        walkable = {(x, 0, 0) for x in range(6)}
        return Fight(
            self.fight_id,
            actors,
            walkable,
            {0: {(x, 0, 0) for x in range(5)}, 1: {enemy_position}},
        )

    def _admit(self, fight=None, session=None):
        with self.store.connection() as db:
            return admit_owned_heroes(
                db, self.store, session or self.session, fight or self.fight
            )

    @staticmethod
    def _player_template():
        from protocol_codec import Reader

        capture = Path(
            os.environ.get(
                "WAKFU_CAPTURE_PATH",
                Path(__file__).resolve().parents[2]
                / ".runtime/captures/2026-10-03T03-40-46.413625Z-fe2520f4/decoded/frames.jsonl",
            )
        )
        if not capture.is_file():
            raise AssertionError("Native 12608 player template capture is unavailable")
        for line in capture.read_text().splitlines():
            frame = json.loads(line)
            if frame.get("direction") != "in" or frame.get("opcode") != 12608:
                continue
            reader = Reader(base64.b64decode(frame["body_base64"], validate=True))
            reader.take(1)
            for _ in range(reader.number("B")):
                actor_type, actor_id = reader.number("B"), reader.number("q")
                blob = reader.take(reader.number("H"))
                if actor_type == 0 and actor_id == 2409354:
                    return blob
        raise AssertionError("Native 12608 player template missing from capture")

    def test_real_roster_admits_full_owned_heroes_with_main_generation_and_state(self):
        result = self._admit()
        expected = {self.hero_a["id"], self.hero_b["id"]}
        self.assertEqual(expected, set(result["characters"]))
        self.assertEqual(expected, {actor.id for actor in result["actors"]})
        self.assertEqual(
            expected,
            {
                actor.id
                for actor in result["fight"].actors.values()
                if actor.controlled and actor.id != self.main["id"]
            },
        )
        self.assertEqual(
            self.store.character(self.account, self.hero_a["id"])["level"],
            result["characters"][self.hero_a["id"]]["level"],
        )
        self.assertEqual(
            self.store.character(self.account, self.hero_b["id"])["breed"],
            result["characters"][self.hero_b["id"]]["breed"],
        )
        for actor in result["actors"]:
            self.assertEqual(self.account, actor.owner_id)
            self.assertEqual(0, actor.team)
            self.assertEqual(
                (self.main["map_id"], self.main["instance_id"]),
                (
                    result["characters"][actor.id]["map_id"],
                    result["characters"][actor.id]["instance_id"],
                ),
            )
        with self.store.connection() as db:
            members = db.execute(
                "SELECT character_id,account_id,team,session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s ORDER BY character_id",
                (self.fight_id,),
            ).fetchall()
            regen = db.execute(
                "SELECT character_id,coefficient FROM character_regeneration "
                "WHERE character_id=ANY(%s)",
                (list(expected),),
            ).fetchall()
            sessions = db.execute(
                "SELECT character_id,generation FROM sessions WHERE account_id=%s",
                (self.account,),
            ).fetchall()
        persisted = {row["character_id"]: row for row in members}
        for identity in expected:
            self.assertEqual(self.account, persisted[identity]["account_id"])
            self.assertEqual(0, persisted[identity]["team"])
            self.assertEqual(self.generation, persisted[identity]["session_generation"])
        self.assertEqual(expected, {row["character_id"] for row in regen})
        self.assertTrue(all(row["coefficient"] == 0 for row in regen))
        self.assertEqual(
            [(self.main["id"], self.generation)],
            [(row["character_id"], row["generation"]) for row in sessions],
        )

    def test_empty_owned_roster_returns_original_fight_without_copy(self):
        # The fixture inserted active fight membership. Remove only its
        # synthetic account-slot rows directly so roster mutations remain
        # correctly forbidden while testing the no-hero admission branch.
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_hero_slots WHERE account_id=%s", (self.account,)
            )
        original = self._fight()
        admitted = self._admit(fight=original)
        self.assertIs(original, admitted["fight"])
        self.assertEqual((), admitted["actors"])
        self.assertEqual({}, admitted["characters"])

    def test_owned_heroes_survive_surrender_and_rejoin_second_fight(self):
        """Abort/return releases durable membership without losing the company."""
        import struct
        from wakfu_server import combat_abandon
        from wakfu_server.combat.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat.combat_shared import Registry

        first = self._admit()
        first_fight = first["fight"]
        runtime = RuntimeMessages(first_fight)
        registry = Registry(lambda current: current == self.session)
        shared = registry.register(first_fight, self.session, runtime=runtime)

        prepared = combat_abandon.prepare(
            self.store, self.account, self.generation, first["leader"], runtime, b""
        )
        self.assertTrue(prepared["applied"])
        returned = combat_abandon.return_to_world(
            self.store,
            self.account,
            self.generation,
            prepared["character"],
            runtime,
            struct.pack(">iB", first_fight.id, 0),
            wp=6,
        )
        self.assertTrue(returned["applied"])
        self.assertTrue(
            registry.retire_abandoned_single_owner(first_fight.id, self.session)
        )
        self.assertNotIn(first_fight.id, registry.fights)

        # After native return, removing/re-adding a hero is allowed again and
        # the next ordinary fight reloads the roster from durable slots.
        heroes.remove(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            self.hero_a["id"],
        )
        second_id = fight_store.create(
            self.store, self.account, self.generation, self.main["id"], team=0
        )
        self.fight_id = second_id
        second_fight = self._fight()
        second = self._admit(fight=second_fight)
        expected = {self.hero_a["id"], self.hero_b["id"]}
        self.assertEqual(expected, set(second["characters"]))
        self.assertEqual(expected, {actor.id for actor in second["actors"]})
        self.assertEqual(
            {self.main["id"], *expected},
            {
                identity
                for identity, actor in second["fight"].actors.items()
                if actor.controlled
            },
        )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s AND account_id=%s",
                (second_id, self.account),
            ).fetchall()
            sessions = db.execute(
                "SELECT character_id,generation FROM sessions WHERE account_id=%s",
                (self.account,),
            ).fetchall()
        self.assertEqual(
            {self.main["id"], *expected}, {row["character_id"] for row in rows}
        )
        self.assertEqual({self.generation}, {row["session_generation"] for row in rows})
        self.assertEqual(
            [(self.main["id"], self.generation)],
            [(row["character_id"], row["generation"]) for row in sessions],
        )

    def test_main_and_two_heroes_serialize_and_take_turns_under_one_native_session(
        self,
    ):
        import struct
        from wakfu_server import wire
        from wakfu_server.breed_resources import live_wp
        from wakfu_server.combat.combat_actor import actual_actor_stats, actor_effects
        from wakfu_server.combat.combat_bootstrap import placement_messages
        from wakfu_server.combat.combat_shared import Registry
        from wakfu_server.combat.combat_wire import arena, decode_bootstrap
        from wakfu_server.combat_orientation import INITIAL_PLAYER_DIRECTION

        admission = self._admit()
        candidate = admission["fight"]
        sources = {self.main["id"]: admission["leader"], **admission["characters"]}
        player_ids = {self.main["id"], self.hero_a["id"], self.hero_b["id"]}
        template = self._player_template()
        appearances = [
            (12608, wire.spawn_player(template, sources[identity]))
            for identity in (self.main["id"], self.hero_a["id"], self.hero_b["id"])
        ]
        self.assertEqual(
            player_ids,
            {
                struct.unpack_from(">q", body, 3)[0]
                for opcode, body in appearances
                if opcode == 12608
            },
        )
        payloads = {}
        for actor_id, actor in candidate.actors.items():
            if actor.controlled:
                self.assertEqual(actor.direction, INITIAL_PLAYER_DIRECTION)
                current_wp, maximum_wp = live_wp(candidate, actor_id)
                payloads[actor_id] = (
                    actual_actor_stats(
                        sources[actor_id],
                        actor,
                        candidate.id,
                        wp_current=current_wp,
                        wp_maximum=maximum_wp,
                    ),
                    actor_effects(),
                )
            else:
                payloads[actor_id] = (b"native-enemy-fixture", actor_effects())
        terrain_cells = [(x, 0, 0) for x in range(6)]
        terrain = arena(
            527, 0, terrain_cells, {0: terrain_cells[0], 1: terrain_cells[-1]}
        )
        packets = placement_messages(
            candidate,
            terrain,
            payloads,
            terrain_effect_id=46,
            terrain_instance_id=-300,
            leaders={0: self.main["id"], 1: -200},
            duration_ms=30000,
        )
        native = decode_bootstrap(packets[1][1])
        wire_player_rows = {
            row["actor_id"]: row["myE"]
            for row in native["participants"]
            if row["myB"] == 0
        }
        for actor_id in player_ids:
            self.assertEqual(
                payloads[actor_id][0][27],
                candidate.actors[actor_id].direction,
            )
            self.assertEqual(
                wire_player_rows[actor_id][27],
                candidate.actors[actor_id].direction,
            )
        self.assertEqual(
            player_ids,
            {row["actor_id"] for row in native["participants"] if row["myB"] == 0},
        )
        self.assertEqual(
            player_ids,
            {
                identity
                for identity in candidate.actors
                if candidate.actors[identity].controlled
            },
        )
        positions = {actor.id: actor.position for actor in candidate.actors.values()}
        self.assertEqual(3, len({positions[identity] for identity in player_ids}))
        registry = Registry(lambda current: current == self.session)
        shared = registry.register(candidate, self.session)
        self.assertEqual({self.main["id"]}, set(shared.participants))
        self.assertEqual(
            player_ids,
            {
                identity
                for identity in registry.by_character
                if registry.lookup_character(identity) is shared
            },
        )
        registry.ready(candidate.id, self.session, True, lambda *_: [])
        acted = set()
        for _ in range(8):
            current = registry.lookup(candidate.id).fight.current
            if current is None:
                break
            if current.controlled:
                actor_id = current.id
                registry.execute(
                    candidate.id,
                    self.session,
                    actor_id,
                    lambda state, _runtime, owner=actor_id: (
                        state.spend(self.account, owner, ap=1),
                        [],
                    )[1],
                )
                acted.add(actor_id)
                actor = registry.lookup(candidate.id).fight.current
                registry.execute(
                    candidate.id,
                    self.session,
                    actor_id,
                    lambda state, _runtime, owner=actor_id: (
                        state.end_turn(
                            self.account, owner, state.actors[owner].turn_count
                        ),
                        [],
                    )[1],
                )
            else:
                actor_id = current.id
                registry.execute_server(
                    candidate.id,
                    actor_id,
                    lambda state, _runtime, owner=actor_id: (
                        state.end_server_turn(owner, state.turn_id),
                        [],
                    )[1],
                    expected_sequence=shared.sequence,
                )
            if player_ids <= acted:
                break
        self.assertEqual(player_ids, acted)
        self.assertTrue(
            all(
                registry.lookup(candidate.id).fight.actors[identity].turn_count >= 1
                for identity in player_ids
            )
        )

    def test_team_capacity_rejects_complete_roster_without_partial_membership(self):
        crowded = self._fight(
            extra_team_zero=4
        )  # main + four allies leaves no room for two heroes
        with self.assertRaisesRegex(ValueError, "complete hero roster"):
            self._admit(fight=crowded)
        with self.store.connection() as db:
            members = db.execute(
                "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s",
                (self.fight_id,),
            ).fetchall()
        self.assertEqual({self.main["id"]}, {row["character_id"] for row in members})

    def test_stale_main_lease_rejects_without_admitting_any_hero(self):
        replacement = self.store.begin_session(self.account)
        self.store.select_character(self.account, replacement, self.main["id"])
        with self.assertRaises(ValueError):
            self._admit()
        with self.store.connection() as db:
            members = db.execute(
                "SELECT character_id,session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s",
                (self.fight_id,),
            ).fetchall()
        self.assertEqual([self.main["id"]], [row["character_id"] for row in members])

    def test_late_dead_hero_rolls_back_earlier_hero_within_admission_savepoint(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,health_dead=true WHERE id=%s",
                (self.hero_b["id"],),
            )
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "[Dd]ead"):
                admit_owned_heroes(db, self.store, self.session, self.fight)
            participants = db.execute(
                "SELECT character_id FROM combat_fight_participants "
                "WHERE fight_id=%s ORDER BY character_id",
                (self.fight_id,),
            ).fetchall()
            self.assertEqual(
                {self.main["id"]}, {row["character_id"] for row in participants}
            )


if __name__ == "__main__":
    unittest.main()
