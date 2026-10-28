"""Joining owners resolve every claimed NPC before owned fight construction."""
import ast
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from protocol_codec import Reader


class JoinedWorldActorTests(unittest.TestCase):
    def test_cold_joiners_receive_all_npc_births_before_bootstrap_with_owned_hero(self):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_wire import decode_bootstrap
        from wakfu_server.monsters import owned_instance

        players = [(67, 10), (40, 22), (71, 23), (46, 23)]
        actors = [
            Actor(identity, 0, (index, 0, 0), 100, 6, 3, 100, 8, account, True)
            for index, (identity, account) in enumerate(players)
        ]
        monsters = {
            -800
            - index: owned_instance(
                4, 8, -800 - index, map_id=527, x=index + 4, y=0, z=0
            )
            for index in range(8)
        }
        actors += [
            Actor(
                row["id"],
                1,
                (row["x"], 0, 0),
                row["hp"],
                row["ap"],
                row["mp"],
                row["initiative"],
                row["level"],
            )
            for row in monsters.values()
        ]
        cells = {actor.position for actor in actors}
        fight = Fight(
            437,
            actors,
            cells,
            {
                0: {actor.position for actor in actors if actor.controlled},
                1: {actor.position for actor in actors if not actor.controlled},
            },
        )
        characters = {
            identity: {"id": identity, "account_id": account}
            for identity, account in players
        }

        def player_appearance(character):
            return 12608, struct.pack(">BBBqH", 0, 1, 0, character["id"], 0)

        shared = SimpleNamespace(
            map_id=527,
            instance_id=0,
            join_context={
                "monsters": monsters,
                "group_key": (527, 0, 999),
                "arena": {
                    "map_id": 527,
                    "instance_id": 0,
                    "x": 0,
                    "y": 0,
                    "width": 12,
                    "height": 1,
                    "min_z": 0,
                    "max_z": 0,
                    "cell_masks": [0] * 12,
                    "team_values": [],
                },
                "terrain_effect_id": 46,
                "terrain_instance_id": -437,
                "leaders": {0: 67, 1: -800},
                "duration_ms": 60000,
                "actor_payload": lambda *_args: (b"fixture-stats", bytes(2)),
                "hero_appearance": player_appearance,
            },
        )
        adapter = CombatSessionAdapter(
            SimpleNamespace(
                character=lambda _account, identity: characters[identity],
            )
        )
        source_path = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server/combat/combat_session_adapter.py"
        )
        tree = ast.parse(source_path.read_text())
        callback = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "owned_bootstrap"
        )
        namespace = {
            "__name__": "wakfu_server.combat_session_adapter",
            "__package__": "wakfu_server",
            "self": adapter,
            "pending": {"admission": {"actors": (fight.actors[46],)}},
            "bootstrap_packets": adapter.placement_bootstrap,
        }
        exec(
            compile(
                ast.Module(body=[callback], type_ignores=[]), str(source_path), "exec"
            ),
            namespace,
        )

        for selected, account, warm in (
            (67, 10, True),
            (40, 22, False),
            (71, 23, False),
        ):
            with self.subTest(selected=selected, warm=warm):
                session = SimpleNamespace(character_id=selected, account_id=account)
                packets = namespace["owned_bootstrap"](fight, shared, session)
                known = {identity for identity, _account in players}
                if warm:
                    known.update(monsters)
                npc_births = []
                for opcode, body in packets:
                    if opcode == 12608:
                        reader = Reader(body)
                        self.assertEqual(reader.number("B"), 0)
                        for _ in range(reader.number("B")):
                            actor_type, identity = reader.number("B"), reader.number(
                                "q"
                            )
                            blob = reader.take(reader.number("H"))
                            known.add(identity)
                            if actor_type == 1:
                                self.assertIn(identity, monsters)
                                self.assertEqual(blob[0], 11)
                                npc_births.append(identity)
                        reader.finish()
                    elif opcode == 12847:
                        value = decode_bootstrap(body)
                        roster = {row["actor_id"] for row in value["participants"]}
                        self.assertEqual(roster, set(fight.actors))
                        self.assertEqual(
                            roster - known,
                            set(),
                            "Native buK cannot resolve unregistered NPCs",
                        )
                        self.assertEqual(set(npc_births), set(monsters))
                        self.assertEqual(len(npc_births), 8)
                        self.assertEqual(
                            {
                                row["actor_id"]
                                for row in value["participants"]
                                if row["myB"] == 0
                            },
                            {67, 40, 71, 46},
                        )
                        break
                else:
                    self.fail("Joining owner did not receive its owned bootstrap")
