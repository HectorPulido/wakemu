"""Controlled hero Symbiot requests use the actual shared actor authority."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from wakfu_server.captured_roster import CapturedCreature, OwnedCapturedRoster
from wakfu_server.captured_roster_selection import owned_request_character
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight


class CapturedHeroDispatchTests(unittest.TestCase):
    def test_owned_hero_selection_management_and_authority_rejections(self):
        slots = (CapturedCreature(0, 41, "Jalalínea"), CapturedCreature(1, 4, "Tofu"))
        osa = dict(
            id=25,
            account_id=11,
            breed=2,
            captured_roster=OwnedCapturedRoster(
                25, slots + (None,) * 8, (True,) * 10, 0
            ).to_record(),
        )
        master = dict(id=64, account_id=11, breed=16)
        original = deepcopy((master, osa))
        store = SimpleNamespace(
            current_character_session=Mock(return_value=True),
            character=Mock(side_effect=lambda account, identity: deepcopy(osa)),
        )
        session = Session(11, 64, "current", 1134, 0)
        registry = Registry(
            lambda owner: store.current_character_session(
                owner.account_id, owner.generation, owner.character_id
            )
        )
        fight = Fight(
            423,
            [
                Actor(64, 0, (0, 0, 0), 60, 6, 3, 100, 1, 11, True),
                Actor(25, 0, (1, 0, 0), 60, 6, 3, 90, 1, 11, True),
                Actor(-200, 1, (3, 0, 0), 60, 6, 3, 1, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        shared = registry.register(fight, session, runtime={"native": "own"})
        fight.ready(11)
        fight.end_turn(11, 64, 1)
        fight.end_server_turn(-200, fight.turn_id)
        self.assertEqual(fight.current.id, 25)
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        codes = {}
        for guard in (
            "opcode in (12014, 13068) and loaded",
            "opcode == 13571 and loaded",
        ):
            expected = ast.dump(ast.parse(guard, mode="eval").body)
            branch = next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.If) and ast.dump(node.test) == expected
            )
            codes[guard] = compile(
                ast.fix_missing_locations(
                    ast.Module(
                        body=[ast.If(test=branch.test, body=branch.body, orelse=[])],
                        type_ignores=[],
                    )
                ),
                "actual-captured-dispatch",
                "exec",
            )
        logs, calls = [], []
        scope = dict(
            STORE=store,
            account_id=11,
            generation="current",
            character=master,
            loaded=True,
            combat_session=session,
            fight=fight,
            record=lambda **row: logs.append(row),
            checkpoint_fight=Mock(),
        )

        def execute(owner, identity, actor_id, operation, **kwargs):
            calls.append((actor_id, kwargs["require_turn"]))
            return registry.execute(identity, owner, actor_id, operation, **kwargs)

        scope["COMBAT_SESSIONS"] = SimpleNamespace(execute=execute)
        scope["refresh_shared_combat"] = lambda: scope.update(fight=shared.fight)
        name = "Tofu héroe".encode()
        for opcode, body in (
            (13571, struct.pack(">qb", 25, 1)),
            (13068, struct.pack(">qbB", 25, 1, len(name)) + name + b"\x01"),
            (12014, struct.pack(">bq", 0, 25)),
        ):
            scope.update(opcode=opcode, body=body)
            exec(
                codes[
                    "opcode == 13571 and loaded"
                    if opcode == 13571
                    else "opcode in (12014, 13068) and loaded"
                ],
                scope,
            )
            self.assertIn(
                logs[-1]["event"], ("symbiot_selection", "symbiot_management")
            )
            self.assertEqual(logs[-1]["actor_id"], 25)
        record = shared.fight.native_captured_roster_updates["25"]
        self.assertEqual(record["selected_slot"], 1)
        self.assertEqual(record["slots"][1]["name"], name.decode())
        self.assertIsNone(record["slots"][0])
        self.assertEqual(calls, [(25, True)] * 3)
        self.assertEqual(scope["checkpoint_fight"].call_count, 3)
        self.assertEqual((master, osa), original)
        saved = deepcopy(record)
        # The real Registry rejects replaced master leases before mutation.
        store.current_character_session.return_value = False
        scope.update(opcode=13571, body=struct.pack(">qb", 25, 0))
        exec(codes["opcode == 13571 and loaded"], scope)
        self.assertEqual(logs[-1]["event"], "symbiot_selection_rejected")
        self.assertEqual(shared.fight.native_captured_roster_updates["25"], saved)
        store.current_character_session.return_value = True
        foreign, withdrawn = deepcopy(shared.fight), deepcopy(shared.fight)
        foreign.actors[25].owner_id = 99
        withdrawn.actors[25].pve_withdrawn = True
        for bad_fight in (None, foreign, withdrawn):
            with self.assertRaises(ValueError):
                owned_request_character(
                    store, 11, "current", master, 25, fight=bad_fight
                )
        shared.fight.end_turn(11, 25, shared.fight.current.turn_count)
        with self.assertRaises(ValueError):
            owned_request_character(
                store, 11, "current", master, 25, fight=shared.fight
            )


if __name__ == "__main__":
    unittest.main()
