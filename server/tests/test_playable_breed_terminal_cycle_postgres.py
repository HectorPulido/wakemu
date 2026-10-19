"""Durable PvE terminal/report/12925 return coverage for every native breed."""

import struct

from postgres_case import PostgresCase
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_rewards import Policy
from wakfu_server.fight_store import (
    create,
    join_participant,
    recoverable_finished_fight,
)


class PlayableBreedTerminalCyclePostgresTests(PostgresCase):
    def _owner(self, index, breed):
        account = self.store.register(f"breed-cycle-{index}", "test-password")["id"]
        suffix = chr(ord("A") + (index - 1) % 26)
        character = self.store.create_character(
            account, f"Breed Cycle {suffix}", breed=breed
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def test_all_native_breeds_complete_mixed_durable_terminal_and_return_cycle(self):
        from wakfu_server.breed_resources import playable_breeds
        from wakfu_server.combat_lifecycle import prepare_finish_shared, return_to_world
        from wakfu_server.wire import proto_fields

        breeds = sorted(playable_breeds())
        self.assertEqual(len(breeds), 18)
        self.assertIn(19, breeds)
        self.assertNotIn(17, breeds)
        # Keep the incident breed in a genuinely mixed party in every cohort.
        others = [breed for breed in breeds if breed not in (19, 16)]
        pairs = [(19, 16)] + list(zip(others[::2], others[1::2]))
        self.assertEqual({breed for pair in pairs for breed in pair}, set(breeds))
        observed = set()

        for cycle, pair in enumerate(pairs, start=1):
            owners = [
                self._owner(cycle * 2 + offset, breed)
                for offset, breed in enumerate(pair)
            ]
            (left_account, left_generation, left_character), (
                right_account,
                right_generation,
                right_character,
            ) = owners
            fight_id = create(
                self.store,
                left_account,
                left_generation,
                left_character["id"],
            )
            with self.store.connection() as db:
                self.assertTrue(
                    join_participant(
                        self.store,
                        db,
                        right_account,
                        right_generation,
                        right_character["id"],
                        fight_id,
                        target_character_id=left_character["id"],
                        team=0,
                    )
                )

            actors = []
            metadata = {}
            for index, (account, _generation, character) in enumerate(owners):
                actor_id = character["id"]
                actors.append(
                    Actor(
                        actor_id,
                        0,
                        (index, 0, 0),
                        character["hp"] - 5,
                        6,
                        3,
                        100 - index,
                        character["level"],
                        account,
                        True,
                        max_hp=character["max_hp"],
                    )
                )
                metadata[actor_id] = dict(
                    kind="player",
                    account_id=account,
                    name=character["name"],
                    breed=character["breed"],
                    is_male=character["sex"] == 0,
                )
            monster_id = -fight_id
            actors.append(
                Actor(monster_id, 1, (len(actors) + 1, 0, 0), 10, 4, 2, 10, 1)
            )
            metadata[monster_id] = dict(kind="monster", ref=5525)
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
            fight.phase, fight.winner = "finished", 0
            runtime = RuntimeMessages(fight)
            by_account = prepare_finish_shared(
                self.store,
                left_account,
                left_generation,
                left_character["id"],
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=fight_id,
                policy_resolver=lambda _db, _member, _character: Policy(xp=0, kamas=0),
                expected_accounts={left_account, right_account},
                owner_character_ids={
                    left_account: left_character["id"],
                    right_account: right_character["id"],
                },
            )
            self.assertEqual(set(by_account), {left_account, right_account})
            for account, generation, character in owners:
                packets = by_account[account]
                opcodes = [opcode for opcode, _body in packets]
                self.assertEqual(opcodes.count(12755), 1)
                self.assertEqual(opcodes.count(12238), 1)
                self.assertLess(opcodes.index(12755), opcodes.index(12238))
                self.assertEqual(opcodes[-1], 13420)
                report_body = next(body for opcode, body in packets if opcode == 12755)
                report = dict(proto_fields(report_body[12:]))
                team_players = [
                    dict(proto_fields(body))
                    for field, body in proto_fields(report[42])
                    if field == 18
                ]
                self.assertEqual(
                    {entry[8]: entry[32] for entry in team_players},
                    {owner[2]["id"]: owner[2]["breed"] for owner in owners},
                )
                observed.add(character["breed"])

                before = self.store.character(account, character["id"])
                actor = fight.actors[character["id"]]
                expected_wound = actor.max_hp - actor.hp
                ack_body = struct.pack(">iB", fight_id, 0)
                returned = return_to_world(
                    self.store,
                    account,
                    generation,
                    before,
                    runtime,
                    ack_body,
                    wp=6,
                )
                self.assertTrue(returned["applied"])
                self.assertEqual(returned["character"]["hp_damage"], expected_wound)
                self.assertEqual(returned["character"]["breed"], character["breed"])
                with self.store.connection() as db:
                    exit_row = db.execute(
                        "SELECT reason,return_acknowledged_at FROM fight_health_exits "
                        "WHERE fight_id=%s AND character_id=%s",
                        (fight_id, character["id"]),
                    ).fetchone()
                    self.assertEqual(exit_row["reason"], "return")
                    self.assertIsNotNone(exit_row["return_acknowledged_at"])
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM fight_rewards "
                            "WHERE fight_id=%s AND character_id=%s",
                            (fight_id, character["id"]),
                        ).fetchone()["n"],
                        1,
                    )

                # A duplicate native return body cannot overwrite later HP.
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET hp=1,hp_damage=max_hp-1 " "WHERE id=%s",
                        (character["id"],),
                    )
                duplicate = return_to_world(
                    self.store,
                    account,
                    generation,
                    returned["character"],
                    runtime,
                    ack_body,
                    wp=6,
                )
                self.assertFalse(duplicate["applied"])
                self.assertEqual(duplicate["character"]["hp"], 1)

                self.store.end_session(account, generation)
                next_generation = self.store.begin_session(account)
                self.store.select_character(account, next_generation, character["id"])
                self.assertIsNone(
                    recoverable_finished_fight(self.store, account, character["id"])
                )
                next_fight = create(
                    self.store, account, next_generation, character["id"]
                )
                self.assertGreater(next_fight, fight_id)

        self.assertEqual(observed, set(breeds))
