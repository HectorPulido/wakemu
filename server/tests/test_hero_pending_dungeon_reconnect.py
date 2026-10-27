"""A pending native swap and dungeon reconnect retain authoritative ownership."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import Mock, patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import heroes
from wakfu_server.position_buffer import Positions
from wakfu_server.world import World


class HeroPendingDungeonReconnectTests(PostgresCase):
    def _pending_idle_then_ack(self, character, account, generation):
        from test_static_map_sync_dispatch import (
            IdentityProfiler,
            _run_factory,
            _session_function,
        )

        character = dict(character, hp=max(1, character["max_hp"] - 1), hp_damage=1)
        world = World(
            lambda actor: b"spawn", lambda actor: b"remove", lambda *args: None
        )
        positions = Positions(self.store, lease_active=lambda *args: True)
        peer = SimpleNamespace(
            native_ai_diagnostics=SimpleNamespace(drain=Mock(return_value=([], 0)))
        )
        health = Mock(wraps=self.store.session_health)
        joined = []

        def join_world(lease, connection, actor, *, hydrate_heroes):
            self.assertFalse(hydrate_heroes)
            positions.attach(account, lease, actor)
            world.join(lease, connection, actor)
            joined.append(actor["id"])

        namespace = {
            "STOPPING": SimpleNamespace(is_set=lambda: False),
            "loaded": True,
            "fight": None,
            "combat_session": None,
            "hero_switch_pending": character["id"],
            "account_id": account,
            "generation": generation,
            "connection": peer,
            "service": "world",
            "STORE": SimpleNamespace(
                session_health=health,
                current_character_session=self.store.current_character_session,
            ),
            "WORLD": world,
            "CHECKPOINT_WRITER": SimpleNamespace(
                observe_database_health=Mock(return_value={"resumed": False})
            ),
            "PROFILER": IdentityProfiler(),
            "time": SimpleNamespace(monotonic=lambda: 20.0),
            "record": Mock(),
            "join_world": join_world,
            "active_private_session": lambda: None,
            "rich_inventory_packet": lambda actor: (13220, b"inventory"),
            "publish_custom_task_cards": Mock(),
            "deliver_custom_task_rewards": Mock(),
            "send": Mock(),
            "wire": SimpleNamespace(adapt=lambda *args: b"guild"),
            "fixture": lambda opcode: b"template",
            "OWNED_HERO_TEMPLATE": b"bounded-template",
            "character": character,
        }
        idle = deepcopy(_session_function("idle"))
        names = {
            name
            for node in ast.walk(idle)
            if isinstance(node, ast.Nonlocal)
            for name in node.names
        }
        initial = {name: None for name in names}
        initial.update(
            character=character,
            last_session_renewal=0,
            last_health_tick=0,
            last_consumable_tick=0,
            last_shop_refresh=0,
            guild_daily_boundary=(None, None),
        )
        namespace["_initial"] = initial
        factory = ast.parse("def build_idle():\n    return idle\n").body[0]
        factory.body[0:0] = [
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.Subscript(
                    value=ast.Name(id="_initial", ctx=ast.Load()),
                    slice=ast.Constant(name),
                    ctx=ast.Load(),
                ),
            )
            for name in sorted(names)
        ] + [idle]
        idle_call = _run_factory(factory, namespace)
        before_hp = character["hp"]
        self.assertNotIn(character["id"], world.players)
        with patch.object(
            world,
            "guild_projection",
            side_effect=AssertionError("pending actor publication"),
        ):
            self.assertTrue(idle_call())
        health.assert_called_once_with(account, generation, renew=True)
        self.assertEqual(character["hp"], before_hp)
        self.assertEqual(namespace["send"].call_count, 0)
        self.assertNotIn(character["id"], world.players)
        namespace["STORE"].session_health = Mock(return_value={"valid": False})
        self.assertFalse(idle_call())
        namespace["STORE"].session_health = health

        source = ast.parse(
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("local_game_server.py")
            .read_text()
        )
        branch = next(
            node
            for node in ast.walk(source)
            if isinstance(node, ast.If) and "opcode == 12054" in ast.unparse(node.test)
        )
        loop = ast.For(
            target=ast.Name(id="_once", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
            body=[branch],
            orelse=[],
        )
        module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
        namespace.update(opcode=12054, body=struct.pack(">q", character["id"]))
        with patch(
            "wakfu_server.inventory_move.synchronization", return_value=(13221, b"sync")
        ), patch(
            "wakfu_server.hero_wire.refresh", return_value=(13046, b"components")
        ), patch(
            "wakfu_server.hero_wire.statistics", return_value=(13046, b"stats")
        ):
            exec(compile(module, "local_game_server.py", "exec"), namespace)
        self.assertIsNone(namespace["hero_switch_pending"])
        self.assertEqual(joined, [character["id"]])
        self.assertEqual(world.players[character["id"]][:2], (generation, peer))
        self.assertIn((account, generation, character["id"]), positions.entries)
        world.update(generation, character, 12345, b"registered")
        self.assertEqual(
            [call.args[2] for call in namespace["send"].call_args_list],
            [13046, 13046, 15548, 13220, 13221],
        )

    def test_pending_idle_ack_reconnect_preserves_frozen_dungeon_and_guards(self):
        from wakfu_server import dungeon_recovery

        account = self.store.register("pending-reconnect", "local-password")["id"]
        main = self.store.create_character(account, "Pending Main")
        hero = self.store.create_character(account, "Pending Hero")
        inactive = self.store.create_character(account, "Pending Inactive")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        identities = [main["id"], hero["id"]]
        with self.store.connection() as db:
            party = db.execute(
                "SELECT p.* FROM player_parties p JOIN player_party_members m ON m.party_id=p.id WHERE m.character_id=%s",
                (main["id"],),
            ).fetchone()
            run = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) "
                "VALUES(%s,%s,%s,1,1,527,1,1,312) RETURNING *",
                (party["id"], party["revision"], main["id"]),
            ).fetchone()
            for index, identity in enumerate(identities):
                db.execute(
                    "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        run["instance_id"],
                        party["id"],
                        identity,
                        generation,
                        party["revision"],
                        "leader" if index == 0 else "member",
                    ),
                )
                db.execute(
                    "INSERT INTO dungeon_transition_outbox(instance_id,party_id,transition_revision,character_id,session_generation,source_map_id,source_instance_id,source_x,source_y,source_z,destination_map_id,destination_instance_id,destination_x,destination_y,destination_z) "
                    "VALUES(%s,%s,1,%s,%s,527,0,1,2,0,312,%s,4,2,0)",
                    (
                        run["instance_id"],
                        party["id"],
                        identity,
                        generation,
                        run["instance_id"],
                    ),
                )
            progress = db.execute(
                "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms,current_room) VALUES(%s,%s,%s,%s,2) RETURNING *",
                (
                    run["instance_id"],
                    party["id"],
                    "a" * 64,
                    Jsonb([{"order": 1}, {"order": 2}]),
                ),
            ).fetchone()
            db.execute(
                "UPDATE characters SET map_id=312,instance_id=%s,x=4,y=2,z=0 WHERE id=ANY(%s)",
                (run["instance_id"], identities),
            )
            members = db.execute(
                "SELECT * FROM dungeon_instance_members ORDER BY character_id"
            ).fetchall()
        reconnect = self.store.begin_session(account)
        selected = self.store.select_character(account, reconnect, hero["id"])
        # Health/equipment recalculation is unchanged by this ownership fix;
        # exclude it rather than compiling a new full combat publication.
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            resumed = dungeon_recovery.resume_member(
                self.store, account, reconnect, hero["id"], run["instance_id"]
            )
        self.assertTrue(resumed["rebound"])
        self.assertEqual(set(resumed["character_ids"]), set(identities))
        self._pending_idle_then_ack(selected, account, reconnect)
        with self.store.connection() as db:
            self.assertEqual(
                run,
                db.execute(
                    "SELECT * FROM dungeon_instances WHERE instance_id=%s",
                    (run["instance_id"],),
                ).fetchone(),
            )
            self.assertEqual(
                progress,
                db.execute(
                    "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
                    (run["instance_id"],),
                ).fetchone(),
            )
            current = db.execute(
                "SELECT * FROM dungeon_instance_members ORDER BY character_id"
            ).fetchall()
            self.assertEqual(
                current, [dict(row, session_generation=reconnect) for row in members]
            )
            self.assertEqual(
                [
                    row["status"]
                    for row in db.execute(
                        "SELECT status FROM dungeon_transition_outbox ORDER BY event_id"
                    )
                ],
                ["superseded", "superseded"],
            )
            roster = db.execute(
                "SELECT * FROM account_hero_rosters WHERE account_id=%s", (account,)
            ).fetchone()
            slots = db.execute(
                "SELECT * FROM account_hero_slots WHERE account_id=%s", (account,)
            ).fetchall()
            self.assertEqual(roster["leader_id"], hero["id"])
            self.assertEqual([row["character_id"] for row in slots], [main["id"]])
            self.assertEqual(
                db.execute(
                    "SELECT character_id FROM player_party_members WHERE party_id=%s",
                    (party["id"],),
                ).fetchone()["character_id"],
                hero["id"],
            )
        for defect in ("new_member", "creation", "combat", "partial_membership"):
            with self.subTest(defect=defect):
                target = inactive["id"] if defect == "new_member" else main["id"]
                with self.store.connection() as db:
                    if defect == "combat":
                        fight = db.execute(
                            "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                        ).fetchone()["id"]
                        db.execute(
                            "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                            (fight, hero["id"], account),
                        )
                    if defect == "partial_membership":
                        db.execute(
                            "UPDATE dungeon_instance_members SET status='returned',ended_at=CURRENT_TIMESTAMP WHERE character_id=%s",
                            (main["id"],),
                        )
                with self.assertRaises(ValueError):
                    if defect == "creation":
                        self.store.create_character(
                            account, "Blocked New", selection_generation=reconnect
                        )
                    else:
                        self.store.select_character(account, reconnect, target)
                with self.store.connection() as db:
                    self.assertEqual(
                        roster,
                        db.execute(
                            "SELECT * FROM account_hero_rosters WHERE account_id=%s",
                            (account,),
                        ).fetchone(),
                    )
                    self.assertEqual(
                        slots,
                        db.execute(
                            "SELECT * FROM account_hero_slots WHERE account_id=%s",
                            (account,),
                        ).fetchall(),
                    )
                    self.assertEqual(
                        hero["id"],
                        db.execute(
                            "SELECT character_id FROM sessions WHERE account_id=%s",
                            (account,),
                        ).fetchone()["character_id"],
                    )
                    if defect == "combat":
                        db.execute(
                            "UPDATE combat_fights SET status='finished' WHERE id=%s",
                            (fight,),
                        )
        # Reuse the same company for the shared authority helper's Rift path.
        # Preflight is validation-only; committed selection rebinds input owner.
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_instance_members SET status='returned',ended_at=CURRENT_TIMESTAMP WHERE instance_id=%s",
                (run["instance_id"],),
            )
            db.execute(
                "UPDATE dungeon_instances SET status='closed',ended_at=CURRENT_TIMESTAMP WHERE instance_id=%s",
                (run["instance_id"],),
            )
            rift = db.execute(
                "INSERT INTO rift_instances(wave_definition_id,owner_character_id,members,catalog,policy,seed,status) "
                "VALUES(1,%s,%s,%s,%s,'pending-reconnect','entered') RETURNING *",
                (hero["id"], Jsonb(identities), Jsonb({}), Jsonb({"max_members": 6})),
            ).fetchone()
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=ANY(%s)",
                (rift["instance_id"], identities),
            )
            heroes.preflight_main_selection(db, account, main["id"])
            self.assertEqual(
                rift,
                db.execute(
                    "SELECT * FROM rift_instances WHERE instance_id=%s",
                    (rift["instance_id"],),
                ).fetchone(),
            )
        self.store.select_character(account, reconnect, main["id"])
        with self.store.connection() as db:
            rebound = db.execute(
                "SELECT * FROM rift_instances WHERE instance_id=%s",
                (rift["instance_id"],),
            ).fetchone()
        self.assertEqual(
            rebound,
            dict(rift, owner_character_id=main["id"], revision=rift["revision"] + 1),
        )
