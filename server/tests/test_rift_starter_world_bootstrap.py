"""The real starter and joined-owner constructors admit identical Rift NPCs."""
import ast
from pathlib import Path
import struct
import unittest

from wakfu_server.combat_actor import actor_effects, actual_monster_actor_stats
from wakfu_server.combat_bootstrap import placement_messages, player_payload
from wakfu_server.combat_encounter_roles import bind_roles
from wakfu_server.combat_multiplayer_wire import decode_added
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_wire import arena, decode_bootstrap
from wakfu_server.monsters import owned_instance
from wakfu_server.rift_encounter_roles import POLICY, roles_for_catalog
from wakfu_server.rift_native_gameplay_policy import POLICY as GAMEPLAY_POLICY


class RiftStarterWorldBootstrapTests(unittest.TestCase):
    def test_actual_starter_and_five_member_peer_bootstrap_have_world_npcs_first(self):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        starter_call = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "COMBAT_SESSIONS.placement_bootstrap"
            and any(
                isinstance(target, ast.Name) and target.id == "packets"
                for target in node.targets
            )
        ]
        self.assertEqual(len(starter_call), 1)
        parents = {
            child: node
            for node in ast.walk(tree)
            for child in ast.iter_child_nodes(node)
        }
        ancestors, current = [], starter_call[0]
        while current in parents:
            current = parents[current]
            ancestors.append(current)
        self.assertTrue(
            any(
                isinstance(node, ast.If)
                and ast.unparse(node.test) == "rift_start_run is not None"
                for node in ancestors
            )
        )
        code = compile(
            ast.Module(body=starter_call, type_ignores=[]),
            "<World Rift starter>",
            "exec",
        )
        for native_roles in (False, True):
            with self.subTest(native_roles=native_roles):
                catalog = dict(type="INFINITE_WAVE", map_id=1314, species_refs=[5525])
                policy = dict(
                    native_gameplay=dict(
                        policy=GAMEPLAY_POLICY,
                        enabled=native_roles,
                        authority="native_consumers_with_reconstructed_producers",
                        enabled_types=["INFINITE_WAVE"],
                        encounter_roles=dict(policy=POLICY, player_team=1, npc_team=0),
                    )
                )
                roles = roles_for_catalog(
                    catalog, policy, monster_references=(5525,) * 7
                )
                sessions = [
                    Session(
                        account, identity, f"owner-{account}", 1314, 288230376151711749
                    )
                    for account, identity in ((11, 25), (10, 67), (23, 46))
                ]
                players = {
                    identity: dict(
                        id=identity,
                        account_id=account,
                        breed=8,
                        level=1,
                        xp=0,
                        hp=100,
                        max_hp=100,
                        map_id=1314,
                        instance_id=sessions[0].instance_id,
                        x=index,
                        y=0,
                        z=0,
                    )
                    for index, (account, identity) in enumerate(
                        ((11, 25), (11, 63), (11, 64), (10, 67), (23, 46))
                    )
                }
                sources = {
                    -200
                    - index: owned_instance(
                        5525,
                        1,
                        -200 - index,
                        map_id=1314,
                        instance_id=sessions[0].instance_id,
                        x=6 + index,
                        y=0,
                        z=0,
                    )
                    for index in range(7)
                }
                actors = [
                    Actor(
                        identity,
                        roles.player_team,
                        (index, 0, 0),
                        100,
                        6,
                        3,
                        100,
                        1,
                        11,
                        True,
                    )
                    for index, identity in enumerate((25, 63, 64))
                ]
                for source in sources.values():
                    npc = Actor(
                        source["id"],
                        roles.npc_team,
                        (source["x"], source["y"], source["z"]),
                        source["hp"],
                        source["ap"],
                        source["mp"],
                        source["initiative"],
                        1,
                    )
                    npc.native_controlled_by_ai = False
                    actors.append(npc)
                cells = {(x, 0, 0) for x in range(14)}
                placement = roles.placement_cells(
                    {(x, 0, 0) for x in range(5)},
                    {(x, 0, 0) for x in range(6, 13)},
                )
                fight = Fight(416, actors, cells, placement)
                bind_roles(
                    fight, roles, player_ids=(25, 63, 64), npc_ids=tuple(sources)
                )
                fight.rift_wave_state = dict(
                    instance_id=sessions[0].instance_id,
                    wave=1,
                    turn_budget=40,
                    world_group_id=416,
                    wave_actor_ids=list(sources),
                )
                fight.rift_monsters = sources
                terrain = arena(
                    1314,
                    1,
                    sorted(cells),
                    {roles.player_team: (0, 0, 0), roles.npc_team: (6, 0, 0)},
                )
                leaders = {roles.player_team: 25, roles.npc_team: -200}

                def payload(current, actor, _owner):
                    if actor.controlled:
                        return player_payload(
                            players[actor.id], actor, current.id, wp=6
                        )
                    source = sources[actor.id]
                    return (
                        actual_monster_actor_stats(
                            source,
                            actor,
                            current.id,
                            wp_current=source["wp"],
                            wp_maximum=source["wp"],
                            fight=current,
                        ),
                        actor_effects(),
                    )

                context = dict(
                    arena=terrain,
                    terrain_effect_id=378,
                    terrain_instance_id=-300,
                    leaders=leaders,
                    duration_ms=60000,
                    actor_payload=payload,
                    frozen_company_members=(25, 63, 64, 67, 46),
                )
                initial = placement_messages(
                    fight,
                    terrain,
                    {a.id: payload(fight, a, sessions[0]) for a in actors},
                    terrain_effect_id=378,
                    terrain_instance_id=-300,
                    leaders=leaders,
                    viewer_id=25,
                )
                registry = Registry(lambda session: session in sessions)
                shared = registry.register(fight, sessions[0], join_context=context)
                peers = []
                for session in sessions[1:]:
                    actor = Actor(
                        session.character_id,
                        roles.player_team,
                        (0, 0, 0),
                        100,
                        6,
                        3,
                        100,
                        1,
                        session.account_id,
                        True,
                    )
                    registry.join(
                        session,
                        struct.pack(">qB", 25, 0),
                        actor,
                        actor_payload=payload,
                        bootstrap_packets=CombatSessionAdapter.placement_bootstrap,
                    )
                    peers.append(
                        tuple(
                            packet
                            for batch in registry.drain(416, session)
                            for packet in batch.packets
                        )
                    )
                # Existing owners receive the other two ordinary admissions.
                admissions = [
                    decode_added(body)["actor_id"]
                    for batch in registry.drain(416, sessions[0])
                    for opcode, body in batch.packets
                    if opcode == 13091
                ]
                self.assertEqual(set(admissions), {67, 46})
                self.assertEqual(
                    {a.id for a in shared.fight.actors.values() if a.controlled},
                    {25, 63, 64, 67, 46},
                )
                scope = dict(
                    candidate=shared.fight,
                    shared_rift=shared,
                    combat_session=sessions[0],
                    COMBAT_SESSIONS=CombatSessionAdapter,
                    packets=initial,
                )
                exec(code, scope)
                starter = scope["packets"]
                bootstrap = next(body for opcode, body in starter if opcode == 12847)
                starter_ids = {
                    row["actor_id"]
                    for row in decode_bootstrap(bootstrap)["participants"]
                }
                self.assertEqual(starter_ids, {25, 63, 64, 67, 46, *sources})
                old_bootstrap = next(
                    body for opcode, body in initial if opcode == 12847
                )
                self.assertEqual(
                    {
                        row["actor_id"]
                        for row in decode_bootstrap(old_bootstrap)["participants"]
                        if row["actor_id"] > 0
                    },
                    {25, 63, 64},
                )
                peer_world = tuple(packet for packet in peers[-1] if packet[0] == 12608)
                self.assertEqual(tuple(starter[:7]), peer_world)
                for packets in (starter, *peers):
                    constructor = next(
                        i for i, (opcode, _) in enumerate(packets) if opcode == 12847
                    )
                    world = [
                        (i, struct.unpack_from(">q", body, 3)[0])
                        for i, (opcode, body) in enumerate(packets)
                        if opcode == 12608
                    ]
                    self.assertEqual(len(world), 7)
                    self.assertEqual({identity for _, identity in world}, set(sources))
                    self.assertTrue(all(i < constructor for i, _ in world))
                    native = decode_bootstrap(packets[constructor][1])
                    self.assertEqual(
                        {
                            row["actor_id"]
                            for row in native["participants"]
                            if row["actor_id"] < 0
                        },
                        set(sources),
                    )
                # The replacement is Rift-scoped; ordinary constructors still
                # use their original placement envelope without world replay.
                self.assertEqual(
                    [opcode for opcode, _ in initial], [13652, 12847, 13684, 13026]
                )


if __name__ == "__main__":
    unittest.main()
