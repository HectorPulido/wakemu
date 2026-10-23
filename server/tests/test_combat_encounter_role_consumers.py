"""Bounded role-consumer contracts; not original Nox scene qualification."""
from types import SimpleNamespace
import struct
from unittest.mock import patch
import unittest

from wakfu_server.combat_encounter_roles import role_assignment
from wakfu_server.combat_external_markers import ExternalFightMarkers
from wakfu_server.combat_multiplayer_wire import decode_external
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight


class EncounterRoleConsumerTests(unittest.TestCase):
    def setUp(self):
        from encounter_role_fixture import role_database_fixture

        self.enterContext(role_database_fixture())

    def fight(self, *, reversed_roles, private=0):
        roles = role_assignment(1435 if reversed_roles else 1134, [5664])
        player = Actor(7, roles.player_team, (0, 0, 0), 100, 6, 3, 10, 1, 1, True)
        npc = Actor(-200, roles.npc_team, (1, 0, 0), 100, 6, 3, 5, 1)
        fight = Fight(
            77,
            [player, npc],
            {player.position, npc.position},
            {roles.player_team: {player.position}, roles.npc_team: {npc.position}},
        )
        fight.native_encounter_roles = roles.record()
        session = Session(1, 7, "owned", roles.map_id, private)
        return fight, roles, session

    def test_withdrawn_leader_join_alias_preserves_frozen_player_side_and_rejects_wrong_team(
        self,
    ):
        for reverse in (False, True):
            with self.subTest(reversed_roles=reverse):
                roles = role_assignment(1435 if reverse else 1134, [5664])
                positions = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}
                boss_position = (3, 0, 0)
                owner = Session(1, 7, "owner", roles.map_id, 0)
                ally = Session(2, 20, "ally", roles.map_id, 0)
                newcomer = Session(3, 30, "newcomer", roles.map_id, 0)
                live = {owner, ally, newcomer}
                registry = Registry(lambda session: session in live)
                fight = Fight(
                    77,
                    [
                        Actor(
                            7, roles.player_team, (0, 0, 0), 100, 6, 3, 10, 1, 1, True
                        ),
                        Actor(-200, roles.npc_team, boss_position, 100, 6, 3, 5, 1),
                    ],
                    positions | {boss_position},
                    roles.placement_cells(positions, {boss_position}),
                )
                fight.native_encounter_roles = roles.record()
                shared = registry.register(
                    fight,
                    owner,
                    join_context=dict(
                        leaders={roles.player_team: 7, roles.npc_team: -200},
                        world_marker_cells=((0, 0),),
                    ),
                )

                def join(session, team):
                    return registry.join(
                        session,
                        struct.pack(">qB", 7, 0),
                        Actor(
                            session.character_id,
                            team,
                            (0, 0, 0),
                            100,
                            6,
                            3,
                            8,
                            1,
                            session.account_id,
                            True,
                        ),
                        actor_payload=lambda *_: (b"", b""),
                        bootstrap_packets=lambda *_: [(12847, b"owned-bootstrap")],
                    )

                join(ally, roles.player_team)
                registry.withdraw_pve(
                    owner, persist=lambda _: {"character": {"id": 7, "hp": 100}}
                )
                registry.return_withdrawn_pve(77, owner, persist=lambda: {})
                self.assertTrue(shared.fight.actors[7].pve_withdrawn)
                self.assertNotIn(7, registry.by_actor)
                self.assertEqual(shared.join_aliases, {7: roles.player_team})
                with self.assertRaisesRegex(ValueError, "ownership/team"):
                    join(newcomer, roles.npc_team)
                self.assertNotIn(30, registry.by_character)
                self.assertNotIn(30, shared.fight.actors)
                self.assertIs(join(newcomer, roles.player_team), shared)
                self.assertEqual(shared.fight.actors[30].team, roles.player_team)
                self.assertEqual(shared.fight.actors[20].team, roles.player_team)

    def test_registration_alias_uses_player_role_and_retains_private_exclusion(self):
        for reverse in (False, True):
            for private in (0, 12):
                with self.subTest(reverse=reverse, private=private):
                    fight, roles, session = self.fight(
                        reversed_roles=reverse, private=private
                    )
                    registry = Registry(lambda candidate: candidate == session)
                    shared = registry.register(
                        fight,
                        session,
                        join_context=dict(
                            leaders={roles.player_team: 7, roles.npc_team: -200},
                            world_marker_cells=((0, 0),),
                        ),
                    )
                    expected = {} if private else {7: roles.player_team}
                    self.assertEqual(shared.join_aliases, expected)
                    self.assertEqual(registry.resolve_join_target(7), fight.id)
        fight, _, session = self.fight(reversed_roles=True)
        fight.native_encounter_roles["player_team"] = 0
        registry = Registry(lambda candidate: True)
        with self.assertRaises(ValueError):
            registry.register(fight, session)
        self.assertEqual(
            (registry.fights, registry.by_actor, registry.by_character), ({}, {}, {})
        )

    def test_external_marker_keeps_wire_team_order_and_validates_actual_npc_side(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                fight, roles, session = self.fight(reversed_roles=reverse)
                fight.native_table_turn = 0
                member = dict(id=-200, map_id=session.map_id, instance_id=0)
                context = dict(
                    leaders={roles.player_team: 7, roles.npc_team: -200},
                    monsters={-200: member},
                    terrain_effect_id=46,
                    world_marker_cells=((14, 9),),
                    world_marker_origin=(14, 9, 2),
                    arena=dict(
                        map_id=session.map_id,
                        instance_id=7,
                        x=1,
                        y=2,
                        width=1,
                        height=1,
                        min_z=-1,
                        max_z=0,
                        cell_masks=[0],
                        team_values=[],
                    ),
                )
                shared = SimpleNamespace(
                    fight=fight,
                    map_id=session.map_id,
                    instance_id=0,
                    is_duel=False,
                    join_context=context,
                    participants={1: session},
                    group_lease=((session.map_id, 0, 77), "owned", fight.id, 1),
                )
                body = ExternalFightMarkers._body(shared, started_at_ms=1)
                decoded = decode_external(body[1])
                self.assertEqual(
                    decoded["myr"], [context["leaders"][0], context["leaders"][1]]
                )
                self.assertEqual(
                    dict(decoded["teams"]), {7: roles.player_team, -200: roles.npc_team}
                )
                with patch(
                    "wakfu_server.combat_monster_world.spawn_group", return_value=b"npc"
                ) as spawn:
                    self.assertEqual(
                        ExternalFightMarkers._actor_snapshot(shared), (12608, b"npc")
                    )
                    spawn.assert_called_once_with((member,), group_id=77)
                fight.actors[-200].team = roles.player_team
                self.assertIsNone(ExternalFightMarkers._body(shared, started_at_ms=1))

    def test_haven_binding_uses_roles_without_weakening_world_identity_proof(self):
        from wakfu_server.guild_haven_world import project_character
        from wakfu_server.combat_haven_world_context import (
            bind_placement,
            placement_context,
        )

        class BindingDB:
            def execute(self, query, parameters):
                row = dict(guild_id=8, native_world_id=-8, name="Owned guild", blazon=0)
                return SimpleNamespace(fetchone=lambda: row)

        # Use the production projection with a bounded SQL-row fixture. This
        # consumer does not publish Nox into a Haven World or grant entry.
        character = project_character(
            BindingDB(), dict(id=7, map_id=1134, instance_id=12)
        )
        context = placement_context(
            character, [dict(id=-200, map_id=1134, instance_id=12)], fight_id=77
        )
        for reverse in (False, True):
            roles = role_assignment(1435 if reverse else 1134, [5664])
            player = SimpleNamespace(
                id=context.owner_character_id, team=roles.player_team
            )
            npc = SimpleNamespace(id=-200, team=roles.npc_team)
            fight = SimpleNamespace(
                id=context.fight_id,
                actors={player.id: player, npc.id: npc},
                native_encounter_roles=roles.record(),
            )
            self.assertIs(bind_placement(fight, context), context)
            self.assertIs(npc.native_haven_world_combat_context, context)
            self.assertFalse(hasattr(player, "native_haven_world_combat_context"))
            player.team = roles.npc_team
            with self.assertRaisesRegex(ValueError, "does not own"):
                bind_placement(fight, context)
