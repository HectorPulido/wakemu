import struct
import tempfile
from postgres_case import PostgresCase
from tests import test_combat_rewards
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.player_death import defeat_messages
from wakfu_server.combat_lifecycle import return_to_world
from wakfu_server.wire import proto_fields
from wakfu_server import health_store


class PlayerDeathTests(PostgresCase):
    def test_positive_owned_player_native_death_result_and_persistent_zero_hp(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                char,
                generation,
                fight,
            ) = test_combat_rewards.setup_reward_state(self.store)
            char = health_store.initialize(
                store, account, generation, char["id"], coefficient=0
            )
            fight.actors[char["id"]].hp = 0
            fight.actors[-200].hp = 12
            fight.winner = 1
            runtime = RuntimeMessages(fight)
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
            packets = defeat_messages(
                runtime, char["id"], metadata, duration_ms=1000, fight_instance_id=8
            )
            self.assertEqual([op for op, b in packets], [12727, 13420, 12238, 12755])
            self.assertEqual(packets[0][1][12:], struct.pack(">qB", char["id"], 2))
            fields = dict(proto_fields(packets[-1][1][12:]))
            self.assertEqual(fields[32], 1)
            player = dict(proto_fields(dict(proto_fields(fields[42]))[18]))
            self.assertEqual(player[80], 1)
            self.assertEqual(player[72], 0)
            self.assertNotIn(66, player)
            returned = return_to_world(
                store,
                account,
                generation,
                char,
                runtime,
                struct.pack(">iB", fight.id, 0),
                wp=6,
            )
            self.assertEqual(returned["character"]["hp"], 0)
            hp = next(body for op, body in returned["packets"] if op == 12436)
            self.assertEqual(struct.unpack(">qii", hp), (char["id"], 0, 0))
            self.assertEqual(store.character(account, char["id"])["hp"], 0)
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )
            metadata[char["id"]]["gained_kamas"] = 1
            with self.assertRaises(ValueError):
                defeat_messages(
                    runtime, char["id"], metadata, duration_ms=1000, fight_instance_id=8
                )
