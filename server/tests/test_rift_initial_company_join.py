"""Exercise World's real initial-company join body with four actual owners.

This bounded Registry case covers admission and Ready, not SQL transport or GUI
combat. The live four-client failure is recorded separately in the QA receipts.
"""
import ast
from pathlib import Path
import struct
import unittest

from wakfu_server.combat_encounter_roles import bind_roles
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_multiplayer_wire import decode_join
from wakfu_server.rift_encounter_roles import roles_for_catalog, POLICY
from wakfu_server.rift_native_gameplay_policy import POLICY as GAMEPLAY_POLICY


class RiftInitialCompanyJoinTests(unittest.TestCase):
    def world_join_body(self, leader_id, player_team):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "COMBAT_SESSIONS"
            and node.func.attr == "join"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Call)
            and isinstance(node.args[1].func, ast.Attribute)
            and isinstance(node.args[1].func.value, ast.Name)
            and node.args[1].func.value.id == "struct"
            and node.args[1].func.attr == "pack"
        ]
        self.assertEqual(len(calls), 1)
        expression = ast.Expression(calls[0].args[1])
        return eval(
            compile(expression, "<actual World initial-company join>", "eval"),
            {
                "struct": struct,
                "character": {"id": leader_id},
                "player_team": player_team,
            },
        )

    def fixture(self, native):
        catalog = dict(type="INFINITE_WAVE", map_id=1314, species_refs=[3215])
        policy = dict(
            native_gameplay=dict(
                policy=GAMEPLAY_POLICY,
                enabled=native,
                authority="native_consumers_with_reconstructed_producers",
                enabled_types=["INFINITE_WAVE"],
                encounter_roles=dict(policy=POLICY, player_team=1, npc_team=0),
            )
        )
        roles = roles_for_catalog(catalog, policy, monster_references=(3215, 3215))
        sessions = [
            Session(account, character, "owner-%s" % account, 1314, 8)
            for account, character in ((3, 7), (4, 10), (5, 11), (6, 12), (7, 13))
        ]
        starter = Actor(7, roles.player_team, (0, 0, 0), 50, 6, 3, 100, 1, 3, True)
        enemies = [
            Actor(uid, roles.npc_team, (x, 0, 0), 50, 6, 3, 20, 1)
            for uid, x in ((-200, 6), (-201, 7))
        ]
        fight = Fight(
            733,
            [starter, *enemies],
            {(x, 0, 0) for x in range(8)},
            roles.placement_cells(
                {(x, 0, 0) for x in range(6)}, {(6, 0, 0), (7, 0, 0)}
            ),
        )
        bind_roles(fight, roles, player_ids=(7,), npc_ids=(-200, -201))
        registry = Registry(lambda session: session in sessions)
        shared = registry.register(
            fight,
            sessions[0],
            runtime=RuntimeMessages(fight, clock=lambda: 10.0),
            join_context={"frozen_company_members": (7, 10, 11, 12)},
        )
        return registry, shared, sessions, roles

    def join(self, registry, session, body, roles):
        return registry.join(
            session,
            body,
            Actor(
                session.character_id,
                roles.player_team,
                (0, 0, 0),
                50,
                6,
                3,
                90,
                1,
                session.account_id,
                True,
            ),
            actor_payload=lambda *args: (b"stats", b"effects"),
            bootstrap_packets=lambda *args: [(12847, b"owned bootstrap")],
        )

    def test_actual_world_four_owner_body_preserves_roles_and_client_autolock(self):
        for native in (False, True):
            with self.subTest(native_player_team=native):
                registry, shared, sessions, roles = self.fixture(native)
                body = self.world_join_body(7, roles.player_team)
                self.assertEqual(
                    decode_join(body), {"target_id": 7, "auto_lock": False}
                )
                for owner in sessions[1:4]:
                    self.join(registry, owner, body, roles)
                    self.assertFalse(shared.auto_locked)
                self.assertEqual(set(shared.participants), {3, 4, 5, 6})
                self.assertEqual(
                    {a.id for a in shared.fight.actors.values() if a.controlled},
                    {7, 10, 11, 12},
                )
                self.assertEqual(
                    {a.team for a in shared.fight.actors.values() if a.controlled},
                    {roles.player_team},
                )
                self.assertEqual(
                    shared.join_context["frozen_company_members"], (7, 10, 11, 12)
                )
                for owner in sessions[:4]:
                    registry.ready(
                        733,
                        owner,
                        True,
                        packets=lambda fight, runtime: [runtime._flush()],
                    )
                self.assertEqual(shared.fight.phase, "active")
                self.assertTrue(
                    all(registry.drain(733, owner) for owner in sessions[:4])
                )
                with self.assertRaisesRegex(ValueError, "no longer joinable"):
                    self.join(registry, sessions[4], body, roles)
                self.assertEqual(set(shared.participants), {3, 4, 5, 6})

                # Real coU autoLock remains effective. Team constructor changes
                # must never change the meaning of a client's trailing boolean.
                locked, locked_shared, owners, locked_roles = self.fixture(native)
                self.join(locked, owners[1], struct.pack(">qB", 7, 1), locked_roles)
                self.assertTrue(locked_shared.auto_locked)
                with self.assertRaisesRegex(ValueError, "no longer joinable"):
                    self.join(locked, owners[2], body, locked_roles)
                self.assertEqual(set(locked_shared.participants), {3, 4})


if __name__ == "__main__":
    unittest.main()
