"""Native13932 dispatch and atomic selected-PC recovery; no client is driven."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase


def source_tree():
    return ast.parse(
        (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
    )


class NativeRespawnDispatchTests(unittest.TestCase):
    def test_nations_and_saved_phoenix_choose_native_points_without_qa_only_policy(
        self,
    ):
        from wakfu_server import world_respawn, phoenix_points

        rows = {
            identity: dict(id=identity, map_id=map_id)
            for identity, map_id in (
                (31371, 527),
                (31372, 1134),
                (31373, 1135),
                (31374, 1136),
                (31375, 1137),
            )
        }
        with patch.object(world_respawn, "points", return_value=rows), patch.object(
            phoenix_points, "points", return_value=rows
        ), patch.object(
            world_respawn,
            "point_destination",
            side_effect=lambda identity: rows[identity],
        ):
            for nation, expected in (
                (0, 31371),
                (30, 31372),
                (31, 31374),
                (32, 31375),
                (33, 31373),
                (34, 31371),
            ):
                with self.subTest(nation=nation):
                    target, policy = world_respawn.destination(
                        dict(nation_id=nation, saved_phoenix_id=0)
                    )
                    self.assertEqual(target["id"], expected)
            target, policy = world_respawn.destination(
                dict(nation_id=30, saved_phoenix_id=31371)
            )
            self.assertEqual((target["id"], policy), (31371, "saved_phoenix"))

    def test_actual_empty_13932_reaches_owned_respawn_handler(self):
        branch = next(
            (
                node
                for node in ast.walk(source_tree())
                if isinstance(node, ast.If)
                and ast.unparse(node.test) == "opcode == 13932 and loaded"
            ),
            None,
        )
        self.assertIsNotNone(branch, "Native13932 has no World handler")
        called = []
        namespace = dict(
            body=b"",
            request_world_respawn=called.append,
            DatabaseError=RuntimeError,
            PoolTimeout=TimeoutError,
            record=lambda **kwargs: None,
        )
        module = ast.fix_missing_locations(
            ast.Module(body=deepcopy(branch.body), type_ignores=[])
        )
        exec(compile(module, "<native13932 production branch>", "exec"), namespace)
        self.assertEqual(called, [b""])


class WorldRespawnPostgresTests(PostgresCase):
    def namespace(self, account, generation, actor, positions, world):
        from psycopg import Error as DatabaseError
        from psycopg_pool import PoolTimeout
        from wakfu_server.movement import Movement

        names = {
            "request_world_respawn",
            "prepare_world_respawn_delivery",
            "deliver_rift_transition",
        }
        helpers = [
            deepcopy(node)
            for node in ast.walk(source_tree())
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        self.assertEqual(len(helpers), 3)
        for helper in helpers:
            for node in ast.walk(helper):
                if isinstance(node, ast.Nonlocal):
                    node.__class__ = ast.Global
        packets, bootstraps = [], []

        def bootstrap(character):
            # Publication ordering/once-only is tested through this callback;
            # complete native bootstrap bytes remain the existing server codec.
            bootstraps.append(character["id"])
            return [(13974, b"existing-owned-bootstrap-callback")]

        namespace = dict(
            STORE=self.store,
            POSITIONS=positions,
            WORLD=world,
            account_id=account,
            generation=generation,
            character=dict(actor),
            position={key: actor[key] for key in ("x", "y", "z")},
            movement_state=None,
            world_respawn_retry_at=0.0,
            fight=None,
            combat_session=None,
            pending_combat_return=None,
            pending_terminal_world_recovery=None,
            publication_recovery_shared=None,
            hero_switch_pending=None,
            spectator_session=None,
            active_private_session=lambda: None,
            COMBAT_SESSIONS=SimpleNamespace(lookup_character=lambda identity: None),
            consume_rift_entry_combat_retirement=lambda: None,
            loaded=True,
            connection=object(),
            service="world",
            Movement=Movement,
            DatabaseError=DatabaseError,
            PoolTimeout=PoolTimeout,
            time=SimpleNamespace(monotonic=lambda: 100),
            record=lambda **kwargs: None,
            cancel_crafting=lambda: None,
            owned_native_bootstrap=bootstrap,
            send=lambda connection, service, opcode, body: packets.append(
                (opcode, body)
            ),
            send_batch=lambda connection, service, values: packets.extend(values),
            join_world=lambda generation, connection, character: world.join(
                generation, connection, character
            ),
            mark_static_sync_pending=lambda: None,
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=helpers, type_ignores=[])),
                "<production respawn and map delivery helpers>",
                "exec",
            ),
            namespace,
        )
        return namespace, packets, bootstraps

    def test_native_respawn_atomic_company_delivery_guards_and_later_selection(self):
        from wakfu_server import health_policy, heroes, fight_store
        from wakfu_server import rift_transition_delivery as delivery
        from wakfu_server.phoenix_points import points, point_destination, activate
        from wakfu_server.world_respawn import request
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.world import World
        from wakfu_server.position_redis import Journal, RedisPositions
        from test_position_redis import MemoryRedis

        self.store.clock = lambda: 1000
        for suffix, saved in (("Neutral", False), ("Saved", True)):
            with self.subTest(saved=saved):
                account = self.store.register("native-respawn-" + suffix, "password")[
                    "id"
                ]
                main = self.store.create_character(account, "Phoenix Main " + suffix)
                dead_hero = self.store.create_character(
                    account, "Phoenix Dead " + suffix
                )
                live_hero = self.store.create_character(
                    account, "Phoenix Live " + suffix
                )
                generation = self.store.begin_session(account, ttl=10000)
                self.store.select_character(account, generation, main["id"])
                for hero in (dead_hero, live_hero):
                    heroes.add(self.store, account, generation, main["id"], hero["id"])
                ids = [main["id"], dead_hero["id"], live_hero["id"]]
                key = account, generation, main["id"]
                self.addCleanup(delivery._PENDING.pop, key, None)
                if saved:
                    identity = next(
                        identity
                        for identity, point in points().items()
                        if point["map_id"] == 1134
                    )
                    bound = point_destination(identity)
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                            (
                                bound["map_id"],
                                bound["x"],
                                bound["y"],
                                bound["z"],
                                main["id"],
                            ),
                        )
                    import struct

                    activate(
                        self.store,
                        account,
                        generation,
                        main["id"],
                        struct.pack(">qHH", identity, 0, 0),
                    )
                    expected = bound
                else:
                    expected = point_destination(31371)
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET map_id=527,instance_id=0,x=0,y=32,z=0 WHERE id=ANY(%s)",
                        (ids,),
                    )
                    for identity in ids:
                        character = self.store.character(account, identity, db)
                        maximum = effective_character(character)["max_hp"]
                        health_policy.reconfigure(db, character, maximum)
                        character = self.store.character(account, identity, db)
                        dead = identity != live_hero["id"]
                        health_policy.apply_damage(
                            db, character, maximum + 7 if dead else 13, dead
                        )
                journal = Journal(MemoryRedis(), namespace="respawn-test-" + suffix)
                positions = RedisPositions(
                    self.store,
                    lease_active=self.store.current_character_session,
                    journal=journal,
                )
                source = self.store.character(account, main["id"])
                positions.attach(account, generation, source)
                world = World(lambda actor: b"", lambda actor: b"", lambda *args: None)
                world.join(generation, object(), source)
                namespace, packets, bootstraps = self.namespace(
                    account, generation, source, positions, world
                )

                def snapshot():
                    with self.store.connection() as db:
                        return dict(
                            characters=db.execute(
                                "SELECT id,map_id,instance_id,x,y,z,hp,max_hp,hp_damage,health_dead FROM characters WHERE id=ANY(%s) ORDER BY id",
                                (ids,),
                            ).fetchall(),
                            party=db.execute(
                                "SELECT p.id,p.leader_id,p.revision,m.character_id FROM player_parties p "
                                "JOIN player_party_members m ON m.party_id=p.id WHERE p.id IN(SELECT party_id "
                                "FROM player_party_members WHERE character_id=%s) ORDER BY m.character_id",
                                (main["id"],),
                            ).fetchall(),
                            slots=db.execute(
                                "SELECT * FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                                (account,),
                            ).fetchall(),
                            roster=db.execute(
                                "SELECT * FROM account_hero_rosters WHERE account_id=%s",
                                (account,),
                            ).fetchall(),
                            regeneration=db.execute(
                                "SELECT * FROM character_regeneration WHERE character_id=ANY(%s) ORDER BY character_id",
                                (ids,),
                            ).fetchall(),
                            items=db.execute(
                                "SELECT * FROM inventory_items WHERE character_id=ANY(%s) ORDER BY uid",
                                (ids,),
                            ).fetchall(),
                        )

                before = snapshot()
                with patch.object(
                    self.store,
                    "transition_map_in_transaction",
                    side_effect=ValueError("transition rejected"),
                ):
                    with self.assertRaisesRegex(ValueError, "transition rejected"):
                        namespace["request_world_respawn"](b"")
                self.assertEqual(snapshot(), before)
                self.assertIsNone(delivery.pending(*key))
                for body, live, combat in (
                    (b"\0", lambda: True, False),
                    (b"", lambda: False, False),
                    (b"", lambda: True, True),
                ):
                    with self.assertRaises(ValueError):
                        request(
                            self.store,
                            positions,
                            *key,
                            body,
                            source=source,
                            validate_live=live,
                            in_fight=combat
                        )
                with self.assertRaises(ValueError):
                    request(
                        self.store,
                        positions,
                        account + 10000,
                        generation,
                        main["id"],
                        b"",
                        source=source,
                        validate_live=lambda: True,
                    )
                fight_id = fight_store.create(
                    self.store, account, generation, main["id"], team=0
                )
                with self.assertRaisesRegex(ValueError, "combate pendiente"):
                    namespace["request_world_respawn"](b"")
                self.assertTrue(
                    fight_store.abort(
                        self.store,
                        account,
                        main["id"],
                        fight_id,
                        expected_generation=generation,
                    )
                )
                self.assertEqual(snapshot(), before)
                # A real account barrier must defer delivery after commit;
                # it must not force a checkpoint, native ACK or bootstrap.
                result = request(
                    self.store,
                    positions,
                    *key,
                    b"",
                    source=source,
                    validate_live=lambda: world.live_identity(character_id=main["id"])[
                        0
                    ]
                    == generation
                )
                self.assertFalse(result["replayed"])
                acquired, release = threading.Event(), threading.Event()

                def hold_position():
                    with positions.account_barrier(account):
                        acquired.set()
                        release.wait(10)

                worker = threading.Thread(target=hold_position)
                worker.start()
                self.assertTrue(acquired.wait(2))
                try:
                    self.assertFalse(namespace["deliver_rift_transition"]())
                    self.assertFalse(packets)
                    self.assertFalse(bootstraps)
                    self.assertIsNotNone(delivery.pending(*key))
                finally:
                    release.set()
                    worker.join(2)
                namespace["world_respawn_retry_at"] = 0
                namespace["request_world_respawn"](b"")
                self.assertEqual(bootstraps, [main["id"]])
                self.assertEqual(
                    [opcode for opcode, body in packets], [12436, 12088, 13974]
                )
                self.assertIsNone(delivery.pending(*key))
                self.assertFalse(list(journal.records()))
                after = snapshot()
                for identity, old in ((row["id"], row) for row in before["characters"]):
                    current = next(
                        row for row in after["characters"] if row["id"] == identity
                    )
                    self.assertEqual({key: current[key] for key in expected}, expected)
                    if identity == main["id"]:
                        self.assertEqual(
                            (current["hp"], current["health_dead"]), (1, False)
                        )
                    else:
                        self.assertEqual(
                            {
                                key: current[key]
                                for key in ("hp", "max_hp", "hp_damage", "health_dead")
                            },
                            {
                                key: old[key]
                                for key in ("hp", "max_hp", "hp_damage", "health_dead")
                            },
                        )
                for field in ("party", "slots", "roster", "items"):
                    self.assertEqual(after[field], before[field])
                self.assertEqual(
                    positions.entries[key]["current"]["map_id"], expected["map_id"]
                )
                self.assertEqual(
                    world.live_identity(character_id=main["id"])[1]["hp"], 1
                )
                with self.assertRaisesRegex(ValueError, "ya está vivo"):
                    namespace["request_world_respawn"](b"")
                self.assertEqual(bootstraps, [main["id"]])
                created = self.store.create_character(
                    account, "After Phoenix " + suffix, selection_generation=generation
                )
                self.store.select_character(account, generation, created["id"])
                new_generation = self.store.begin_session(account, ttl=10000)
                self.store.select_character(account, new_generation, created["id"])
                selected = self.store.character(account, created["id"])
                with self.assertRaises(ValueError):
                    namespace["request_world_respawn"](b"")
                self.assertEqual(self.store.character(account, created["id"]), selected)
