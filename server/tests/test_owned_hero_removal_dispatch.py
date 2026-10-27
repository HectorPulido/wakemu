"""Owned-hero removal reaches every party peer before the fresh roster."""
import ast
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import Mock, patch

from postgres_case import PostgresCase
from protocol_codec import Reader
from wakfu_server import heroes, hero_wire, party_wire
from wakfu_server.party_dispatch import Parties
from wakfu_server.position_buffer import Positions
from wakfu_server.world import World


class OwnedHeroRemovalDispatchTests(PostgresCase):
    def test_all_peers_remove_before_roster_and_stale_or_kicked_owners_are_fenced(self):
        account = self.store.register("remove-hero-owner", "local-password")["id"]
        owner = self.store.create_character(account, "Remove Owner")
        removed = self.store.create_character(account, "Removed Hero")
        kept = self.store.create_character(account, "Retained Hero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, owner["id"])
        for actor in (removed, kept):
            heroes.add(self.store, account, generation, owner["id"], actor["id"])
        other_account = self.store.register("remove-hero-peer", "local-password")["id"]
        other = self.store.create_character(other_account, "Other Peer")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other["id"])
        with self.store.connection() as db:
            party = db.execute(
                "SELECT party_id FROM player_party_members WHERE character_id=%s",
                (owner["id"],),
            ).fetchone()["party_id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (other["id"], party),
            )
        owner = self.store.character(account, owner["id"])
        packets, records = [], []
        world = World(
            lambda actor: b"spawn",
            lambda actor: b"remove",
            lambda peer, opcode, body: packets.append((peer, opcode, body)),
        )
        world.join(generation, "owner-peer", owner)
        world.join(other_generation, "other-peer", other)
        parties = Parties(self.store, world)
        positions = Positions(self.store, lease_active=lambda *args: True)
        positions.attach(account, generation, owner)
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        refresh = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "refresh_party"
        )
        publish = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "publish_heroes"
        )
        namespace = dict(
            STORE=self.store,
            WORLD=world,
            PARTIES=parties,
            POSITIONS=positions,
            account_id=account,
            generation=generation,
            character=owner,
            connection="owner-peer",
            service="world",
            loaded=True,
            opcode=1074,
            active_private_session=lambda: None,
            OWNED_HERO_TEMPLATE=b"fixture",
            send=lambda peer, channel, opcode, body: packets.append(
                (peer, opcode, body)
            ),
            record=lambda **row: records.append(row),
            flush_positions=lambda **scope: positions.flush(**scope),
        )
        exec(
            compile(ast.Module(body=[refresh], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        factory = ast.parse(
            "def build_publish():\n    pet_hibernation_due=0.0\n    return publish_heroes\n"
        ).body[0]
        factory.body.insert(-1, deepcopy(publish))
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        namespace["publish_heroes"] = Mock(wraps=namespace["build_publish"]())
        branch = deepcopy(
            next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and ast.unparse(node.test)
                == "opcode in (1156, 1031, 1074, 1066) and loaded"
            )
        )
        branch.orelse = []
        module = ast.fix_missing_locations(
            ast.Module(
                body=[
                    ast.For(
                        target=ast.Name(id="_once", ctx=ast.Store()),
                        iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                        body=[branch],
                        orelse=[],
                    )
                ],
                type_ignores=[],
            )
        )

        def run():
            packets.clear()
            namespace["body"] = struct.pack(">qq", party, removed["id"])
            exec(compile(module, str(source), "exec"), namespace)

        def roster_ids(body):
            reader = Reader(body)
            self.assertEqual(reader.number("q"), party)
            reader.number("B")
            reader.number("h")
            reader.number("q")
            result = []
            for _ in range(reader.number("h")):
                result.append(reader.number("q"))
                reader.take(reader.number("h"))
            reader.finish()
            return set(result)

        remove = heroes.remove

        def remove_under_guard(*args, **kwargs):
            lock = parties.locks[hash(parties._key(owner["id"])) % len(parties.locks)]
            self.assertTrue(lock._is_owned())
            return remove(*args, **kwargs)

        with patch.object(
            hero_wire, "activate", return_value=(12093, b"hero")
        ), patch.object(
            hero_wire, "statistics", return_value=(13046, b"stats")
        ), patch.object(
            hero_wire, "company", return_value=(23053, b"company")
        ), patch.object(
            heroes, "remove", side_effect=remove_under_guard
        ):
            run()
            for peer in ("owner-peer", "other-peer"):
                updates = [
                    (opcode, body)
                    for target, opcode, body in packets
                    if target == peer and opcode in (1049, 1184)
                ]
                self.assertEqual([opcode for opcode, _ in updates], [1049, 1184])
                self.assertEqual(updates[0], party_wire.removed(party, [removed["id"]]))
                self.assertEqual(
                    roster_ids(updates[1][1]), {owner["id"], kept["id"], other["id"]}
                )
            with self.store.connection() as db:
                self.assertEqual(
                    [
                        row["character_id"]
                        for row in db.execute(
                            "SELECT character_id FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                            (account,),
                        )
                    ],
                    [kept["id"]],
                )
            self.assertEqual(records[-2]["event"], "hero_removed")

            # Replace a recipient after its live generation was captured.
            heroes.add(self.store, account, generation, owner["id"], removed["id"])

            def replace_recipient(*args, **kwargs):
                result = remove_under_guard(*args, **kwargs)
                renewed = self.store.begin_session(other_account)
                selected = self.store.select_character(
                    other_account, renewed, other["id"]
                )
                world.join(renewed, "replacement-peer", selected)
                return result

            with patch.object(heroes, "remove", side_effect=replace_recipient):
                run()
            self.assertFalse(
                any(
                    peer in ("other-peer", "replacement-peer") and opcode == 1049
                    for peer, opcode, body in packets
                )
            )
            self.assertTrue(
                any(
                    peer == "replacement-peer" and opcode == 1184
                    for peer, opcode, body in packets
                )
            )

            heroes.add(self.store, account, generation, owner["id"], removed["id"])
            guarded = parties._guard

            @contextmanager
            def kicked_before_guard(identity):
                with self.store.connection() as db:
                    db.execute(
                        "DELETE FROM player_party_members WHERE character_id=%s",
                        (owner["id"],),
                    )
                with guarded(identity):
                    yield

            namespace["publish_heroes"].reset_mock()
            with patch.object(
                parties, "_guard", side_effect=kicked_before_guard
            ), patch.object(heroes, "remove", wraps=remove) as guarded_remove:
                run()
                guarded_remove.assert_not_called()
            namespace["publish_heroes"].assert_not_called()
            self.assertFalse(
                any(opcode in (1049, 1184) for peer, opcode, body in packets)
            )
            self.assertEqual(
                [(peer, opcode) for peer, opcode, body in packets],
                [("owner-peer", 349)],
            )
            with self.store.connection() as db:
                self.assertEqual(
                    {
                        row["character_id"]
                        for row in db.execute(
                            "SELECT character_id FROM account_hero_slots WHERE account_id=%s",
                            (account,),
                        )
                    },
                    {removed["id"], kept["id"]},
                )
