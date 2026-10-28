"""Exact switch branches with real durable company and live membership adapters.

Packet encoders are bounded spies: this qualifies server ordering and authority,
not the native client's visual completion.
"""
import ast
import os
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import heroes, hero_wire
from wakfu_server.captured_roster import CapturedCreature, OwnedCapturedRoster
from wakfu_server.captured_roster_store import save as save_captured_roster
from wakfu_server.movement import Movement
from wakfu_server.position_buffer import Positions
from wakfu_server.world import World


class HeroCompanySwitchPipelineTests(PostgresCase):
    def test_osa_steamer_eni_switch_and_reconnect_keep_company_and_ack_authority(self):
        account = self.store.register("switch-chain", "test-password")["id"]
        osa, steamer, eni = [
            self.store.create_character(account, name, breed=breed)
            for name, breed in (
                ("Chain Osa", 2),
                ("Chain Steamer", 16),
                ("Chain Eni", 7),
            )
        ]
        captures = OwnedCapturedRoster(
            osa["id"],
            (
                CapturedCreature(0, 41, "Chain Gobball"),
                CapturedCreature(1, 4, "Chain Tofu"),
            )
            + (None,) * 8,
            (True,) * 10,
            1,
        )
        with self.store.connection() as db:
            save_captured_roster(db, osa, captures)
        generation = self.store.begin_session(account)
        selected = self.store.select_character(account, generation, osa["id"])
        for hero in (steamer, eni):
            heroes.add(self.store, account, generation, osa["id"], hero["id"])
        positions = Positions(
            self.store, lease_active=self.store.current_character_session
        )
        world = World(
            lambda actor: b"spawn", lambda actor: b"remove", lambda *args: None
        )
        peer = object()
        positions.attach(account, generation, selected)
        world.join(generation, peer, selected)
        packets, events = [], []

        def join_world(lease, connection, actor, *, hydrate_heroes):
            self.assertFalse(hydrate_heroes)
            events.append(("join", actor["id"]))
            world.join(lease, connection, actor)

        namespace = dict(
            loaded=True,
            hero_switch_pending=None,
            character=selected,
            account_id=account,
            generation=generation,
            connection=peer,
            service="world",
            fight=None,
            combat_session=None,
            ranch_session=None,
            bag_session=None,
            chest_opening=None,
            npc_dialogue_session=None,
            active_private_session=lambda: None,
            is_dungeon_run=lambda _instance: False,
            PLANTINGS=SimpleNamespace(cancel=lambda *args: None),
            HARVESTS=SimpleNamespace(cancel=lambda *args, **kwargs: None),
            cancel_flora=lambda: None,
            cancel_crafting=lambda: None,
            STORE=self.store,
            POSITIONS=positions,
            WORLD=world,
            Movement=Movement,
            flush_positions=positions.flush,
            OWNED_HERO_TEMPLATE=b"bounded-template",
            wire=SimpleNamespace(adapt=lambda *args: b"guild"),
            fixture=lambda opcode: b"fixture",
            send=lambda connection, service, opcode, body: packets.append(
                (opcode, body)
            ),
            record=lambda **values: events.append(("record", values)),
            join_world=join_world,
            rich_inventory_packet=lambda actor: (13220, b"inventory"),
            publish_custom_task_cards=lambda: None,
            deliver_custom_task_rewards=lambda: None,
        )
        source = Path(
            os.environ.get(
                "WAKFU_HERO_SWITCH_DISPATCH_SOURCE",
                Path(__file__).resolve().parents[1] / "local_game_server.py",
            )
        )
        tree = ast.parse(source.read_text())
        branches = {
            opcode: next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and ast.unparse(node.test) == f"opcode == {opcode} and loaded"
            )
            for opcode in (12006, 12054)
        }

        def dispatch(opcode, identity):
            namespace.update(opcode=opcode, body=struct.pack(">q", identity))
            loop = ast.For(
                target=ast.Name("_once", ast.Store()),
                iter=ast.Tuple([ast.Constant(0)], ast.Load()),
                body=[branches[opcode]],
                orelse=[],
            )
            module = ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[]))
            exec(compile(module, str(source), "exec"), namespace)

        def refresh(template, actor):
            return 13046, b"components" + struct.pack(">q", actor["id"])

        with patch.object(hero_wire, "refresh", side_effect=refresh), patch.object(
            hero_wire, "statistics", side_effect=lambda actor: (13046, b"stats")
        ), patch(
            "wakfu_server.inventory_move.synchronization", return_value=(13221, b"sync")
        ):
            for previous, target in ((osa, steamer), (steamer, eni)):
                packets.clear()
                dispatch(12006, target["id"])
                self.assertEqual(
                    packets, [(13440, struct.pack(">Bq", 0, target["id"]))]
                )
                self.assertEqual(namespace["hero_switch_pending"], target["id"])
                self.assertNotIn(previous["id"], world.players)
                self.assertNotIn(target["id"], world.players)
                self.assertTrue(
                    self.store.current_character_session(
                        account, generation, target["id"]
                    )
                )
                self.assertIn((account, generation, target["id"]), positions.entries)
                dispatch(12054, previous["id"])
                self.assertNotIn(target["id"], world.players)
                self.assertEqual(namespace["hero_switch_pending"], target["id"])
                packets.clear()
                dispatch(12054, target["id"])
                self.assertEqual(
                    [opcode for opcode, body in packets],
                    [13046, 13046, 15548, 13220, 13221],
                )
                self.assertEqual(
                    packets[0][1], b"components" + struct.pack(">q", target["id"])
                )
                self.assertIsNone(namespace["hero_switch_pending"])
                self.assertEqual(set(world.players), {target["id"]})
                self.assertEqual(world.players[target["id"]][:2], (generation, peer))
                before = list(packets)
                dispatch(12054, target["id"])
                self.assertEqual(packets, before)

        reconnect = self.store.begin_session(account)
        resumed = self.store.select_character(account, reconnect, steamer["id"])
        self.assertEqual(resumed["id"], steamer["id"])
        self.assertFalse(
            self.store.current_character_session(account, generation, eni["id"])
        )
        self.assertTrue(
            self.store.current_character_session(account, reconnect, steamer["id"])
        )
        with self.store.connection() as db:
            roster = heroes.load_roster(db, self.store, account, steamer["id"])
            self.assertEqual(
                {osa["id"], eni["id"]}, {hero["id"] for hero in roster["heroes"]}
            )
            members = db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=(SELECT party_id FROM player_party_members WHERE character_id=%s)",
                (steamer["id"],),
            ).fetchall()
            self.assertEqual([steamer["id"]], [row["character_id"] for row in members])
            self.assertEqual(
                self.store.character(account, osa["id"], db)["captured_roster"],
                captures.to_record(),
            )
