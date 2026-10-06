"""Serving helpers over isolated PostgreSQL: exits cannot poison the next Ready."""
import struct
import tempfile
import test_combat_abandon as abandon_fixture
import test_combat_rewards as reward_fixture
from postgres_case import PostgresCase
from wakfu_server import combat_abandon
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_lifecycle import prepare_finish, return_to_world
from wakfu_server.combat_rewards import Policy
from wakfu_server import health_store


def fresh_ready(character, account, identity):
    cells = {(0, 0, 0), (1, 0, 0)}
    fight = Fight(
        identity,
        [
            Actor(
                character["id"],
                0,
                (0, 0, 0),
                character["hp"],
                6,
                3,
                0,
                account,
                1,
                True,
            ),
            Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
        ],
        cells,
        {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
    )
    # This test isolates serving transitions, not a breed initialization audit.
    preview, runtime, packets = prepare_ready(
        fight,
        account,
        True,
        initialize=lambda preview, action: (preview, ()),
        stats_serializer=lambda actor: b"",
        effects_serializer=lambda: b"\0\0",
    )
    return fight, preview, runtime, packets


class ExitReentryTests(PostgresCase):
    def test_abandon_return_allows_native_transport_and_new_durable_fight(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                generation,
                character,
                fight,
                runtime,
            ) = abandon_fixture.setup_abandon_state(self.store)
            origin = dict(map_id=1134, instance_id=0, x=-10, y=-11, z=-1)
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (
                        origin["map_id"],
                        origin["instance_id"],
                        origin["x"],
                        origin["y"],
                        origin["z"],
                        character["id"],
                    ),
                )
            character = store.character(account, character["id"])

            from wakfu_server.combat_group_store import PersistentGroups
            from wakfu_server.monsters import owned_instance

            groups = PersistentGroups(store)
            group_key = groups.register(
                1134,
                0,
                501,
                [owned_instance(5525, 1, -201, map_id=1134, x=-7, y=-7, z=-1)],
            )
            group_lease, _ = groups.claim(group_key, generation, fight.id)

            abandoned = combat_abandon.prepare(
                store, account, generation, character, runtime, b""
            )
            from wakfu_server.fight_checkpoint_store import Checkpoints

            checkpoints = Checkpoints(store)
            revision = checkpoints.save(account, generation, fight, runtime=runtime)
            checkpoints.end(
                account,
                generation,
                fight.id,
                expected_revision=revision,
                status="aborted",
            )
            returned = combat_abandon.return_to_world(
                store,
                account,
                generation,
                abandoned["character"],
                runtime,
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
            self.assertTrue(returned["applied"])
            # Match the post-callback group release performed by the world handler.
            self.assertTrue(groups.finish(group_lease, defeated=False))
            self.assertEqual(len(groups.available(1134, 0)), 1)
            self.assertEqual(
                tuple(
                    returned["character"][key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                ),
                tuple(origin[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            )

            from wakfu_server.native_transports import resolve
            from wakfu_server.transport_discovery import known_all
            from wakfu_server.fight_store import create, activate

            destination_id = next(
                identity for identity in known_all()[1] if identity != 31316
            )
            route = resolve(
                returned["character"],
                struct.pack(">qq", 31316, destination_id),
                known_ids=known_all()[1],
                waive_criteria=True,
            )
            moved = store.transition_map(
                account,
                generation,
                character["id"],
                returned["character"],
                route["destination"],
            )
            self.assertEqual(moved["map_id"], route["destination"]["map_id"])

            next_fight = create(store, account, generation, character["id"])
            activate(store, account, generation, character["id"], next_fight)
            with store.connection() as db:
                states = {
                    row["id"]: row["status"]
                    for row in db.execute(
                        "SELECT id,status FROM combat_fights WHERE id=ANY(%s)",
                        ([fight.id, next_fight],),
                    )
                }
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards WHERE fight_id=%s",
                        (fight.id,),
                    ).fetchone()["count"],
                    0,
                )
            self.assertEqual(states, {fight.id: "aborted", next_fight: "active"})
            self.assertEqual(checkpoints.read(account, fight.id)["status"], "aborted")

    def test_disconnect_without_return_callback_keeps_abort_terminal_and_recoverable(
        self,
    ):
        (
            store,
            account,
            generation,
            character,
            fight,
            runtime,
        ) = abandon_fixture.setup_abandon_state(self.store)
        fight.ready(account)
        fight.actors[character["id"]].hp -= 5
        abandoned = combat_abandon.prepare(
            store, account, generation, character, runtime, b""
        )
        from wakfu_server.fight_checkpoint_store import Checkpoints

        checkpoints = Checkpoints(store)
        revision = checkpoints.save(account, generation, fight, runtime=runtime)
        checkpoints.end(
            account,
            generation,
            fight.id,
            expected_revision=revision,
            status="aborted",
        )
        self.assertEqual(abandoned["character"]["hp"], character["hp"] - 5)
        self.assertEqual(checkpoints.read(account, fight.id)["status"], "aborted")

        restarted = self.reopen()
        recovery = Checkpoints(restarted)
        from wakfu_server.fight_store import create, activate

        self.assertEqual(recovery.recover_interrupted(), 0)
        self.assertEqual(recovery.read(account, fight.id)["status"], "aborted")
        self.assertEqual(
            restarted.character(account, character["id"])["hp"], character["hp"] - 5
        )
        next_generation = restarted.begin_session(account)
        restarted.select_character(account, next_generation, character["id"])
        next_fight = create(restarted, account, next_generation, character["id"])
        activate(restarted, account, next_generation, character["id"], next_fight)
        with restarted.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (next_fight,)
                ).fetchone()["status"],
                "active",
            )

    def test_active_abort_return_and_new_ready_preserve_own_damage(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                generation,
                char,
                fight,
                runtime,
            ) = abandon_fixture.setup_abandon_state(self.store)
            fight.ready(account)
            fight.actors[char["id"]].hp -= 5
            runtime.awaiting_ack = 1
            runtime.pending = [(1, b"old pending")]
            aborted = combat_abandon.prepare(
                store, account, generation, char, runtime, b""
            )
            returned = combat_abandon.return_to_world(
                store,
                account,
                generation,
                aborted["character"],
                runtime,
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
            self.assertEqual(returned["character"]["hp"], char["hp"] - 5)
            source, next_fight, next_runtime, packets = fresh_ready(
                returned["character"], account, fight.id + 1
            )
            self.assertEqual(
                (source.phase, next_fight.phase, fight.phase),
                ("placement", "active", "finished"),
            )
            self.assertEqual(next_fight.actors[char["id"]].hp, char["hp"] - 5)
            self.assertIsNone(next_runtime.awaiting_ack)
            self.assertFalse(hasattr(next_runtime, "abandon_owner"))
            self.assertEqual([op for op, _ in packets].count(12514), 1)
            self.assertEqual(runtime.pending, [])

    def test_victory_return_and_new_ready_do_not_reuse_finished_fsm(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                char,
                generation,
                fight,
            ) = reward_fixture.setup_reward_state(self.store)
            char = health_store.initialize(
                store, account, generation, char["id"], coefficient=0
            )
            from wakfu_server.combat_runtime_messages import RuntimeMessages

            runtime = RuntimeMessages(fight)
            fight.actors[char["id"]].hp = char["hp"]
            fight.actors[char["id"]].max_hp = char["max_hp"]
            metadata = {
                char["id"]: dict(
                    kind="player",
                    account_id=account,
                    name=char["name"],
                    breed=char["breed"],
                    is_male=True,
                ),
                -200: dict(kind="monster", ref=5525),
            }
            done = prepare_finish(
                store,
                account,
                generation,
                char,
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=8,
                policy=Policy(),
            )
            result = return_to_world(
                store,
                account,
                generation,
                done["character"],
                runtime,
                struct.pack(">iB", fight.id, 0),
                wp=6,
            )
            source, next_fight, next_runtime, packets = fresh_ready(
                result["character"], account, fight.id + 1
            )
            self.assertEqual(
                (fight.phase, source.phase, next_fight.phase),
                ("finished", "placement", "active"),
            )
            self.assertEqual(
                next_fight.actors[char["id"]].hp, result["character"]["hp"]
            )
            self.assertEqual(next_fight.ready_owners, {account})
            self.assertFalse(hasattr(next_runtime, "abandon_owner"))
