"""Bounded shared death/timeline integration, not a client or native Ready test.

Actor deaths use the ordinary damage producer on Registry transaction previews.
Frozen Rift roles are bound before placement; no winner or corpse is assigned.
"""
from copy import deepcopy
import struct
import unittest

from wakfu_server.combat_encounter_roles import bind_roles
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.rift_encounter_roles import roles_for_catalog, POLICY
from wakfu_server.rift_native_gameplay_policy import POLICY as GAMEPLAY_POLICY
from test_combat_shared_timeline_recovery import decoded_timeline


class RiftDeathOwnerTimelineMatrixTests(unittest.TestCase):
    def fixture(self, native_roles, *, rift=False):
        catalog = dict(type="ULTIMATE_INFINITE_WAVE", map_id=1324, species_refs=[5525])
        policy = dict(
            native_gameplay=dict(
                policy=GAMEPLAY_POLICY,
                enabled=native_roles,
                authority="native_consumers_with_reconstructed_producers",
                enabled_types=["ULTIMATE_INFINITE_WAVE"],
                encounter_roles=dict(policy=POLICY, player_team=1, npc_team=0),
            )
        )
        roles = roles_for_catalog(catalog, policy, monster_references=(5525, 5525))
        sessions = [Session(3, 7, "main", 1324, 8), Session(4, 10, "peer", 1324, 8)]
        players = [
            Actor(
                uid, roles.player_team, (index, 0, 0), 50, 6, 3, 100 - index, 1, 3, True
            )
            for index, uid in enumerate((7, 8, 9))
        ]
        enemies = [
            Actor(uid, roles.npc_team, (index, 0, 0), 50, 6, 3, 500 - index, 1)
            for index, uid in ((5, -200), (6, -201))
        ]
        cells = {(x, 0, 0) for x in range(7)}
        fight = Fight(
            733,
            players + enemies,
            cells,
            roles.placement_cells(
                {(x, 0, 0) for x in range(5)}, {(5, 0, 0), (6, 0, 0)}
            ),
        )
        bind_roles(fight, roles, player_ids=(7, 8, 9), npc_ids=(-200, -201))
        registry = Registry(lambda session: session in sessions)
        shared = registry.register(
            fight, sessions[0], runtime=RuntimeMessages(fight, clock=lambda: 10.0)
        )
        registry.join(
            sessions[1],
            struct.pack(">qB", 7, roles.player_team),
            Actor(10, roles.player_team, (3, 0, 0), 50, 6, 3, 90, 1, 4, True),
            actor_payload=lambda *args: (b"stats", b"effects"),
            bootstrap_packets=lambda *args: [(12847, b"bootstrap")],
        )
        if rift:
            shared.fight.rift_wave_state = dict(
                instance_id=8, wave=1, turn_budget=40, wave_actor_ids=[-200, -201]
            )
            from wakfu_server.rift_dispatch_combat import finish_accepted_action

            def unexpected_birth(*args, **kwargs):
                raise AssertionError("A defeated party must never create a wave")

            shared.join_context = dict(
                rift_accepted_action=lambda view, fight, runtime, packets: finish_accepted_action(
                    fight, runtime, packets, initialize_actor=unexpected_birth
                )
            )
        for session in sessions:
            registry.ready(
                733, session, True, packets=lambda fight, runtime: [runtime._flush()]
            )
        self.assertEqual(shared.fight.current.id, -200)
        for session in sessions:
            registry.drain(733, session)
        return registry, shared, sessions, roles

    def test_mutually_lethal_rift_action_is_loss_and_never_stages_another_wave(self):
        for native_roles in (False, True):
            with self.subTest(native_roles=native_roles):
                registry, shared, sessions, roles = self.fixture(
                    native_roles, rift=True
                )

                def mutual(candidate, runtime):
                    with candidate.effect_resolution():
                        for identity in tuple(candidate.actors):
                            candidate.apply_effect_damage(
                                -200, identity, candidate.actors[identity].hp
                            )
                    return [runtime._flush()]

                registry.execute_server(
                    733, -200, mutual, expected_sequence=shared.sequence
                )
                self.assertEqual(
                    (shared.fight.phase, shared.fight.winner),
                    ("finished", roles.npc_team),
                )
                self.assertTrue(
                    all(actor.hp == 0 for actor in shared.fight.actors.values())
                )
                self.assertEqual(shared.fight.rift_wave_state["outcome"], "defeated")
                self.assertIsNone(shared.fight.rift_wave_state.get("pending_wave"))
                self.assertEqual(
                    sum(
                        e.get("reason") == "rift_no_surviving_players"
                        for e in shared.fight.events
                    ),
                    1,
                )
                self.assertFalse(
                    any(e["kind"] == "rift_wave_cleared" for e in shared.fight.events)
                )

    def test_owned_ko_matrix_publishes_one_consistent_successor_and_recovery(self):
        cases = (
            ("main_ko_heroes_live", (7,), (8, 9, 10)),
            ("heroes_ko_main_live", (8, 9), (7, 10)),
            ("owner_ko_peer_live", (7, 8, 9), (10,)),
            ("all_owners_ko", (7, 8, 9, 10), ()),
            ("both_teams_ko", (7, 8, 9, 10, -200, -201), ()),
        )
        for native_roles in (False, True):
            for name, victims, survivors in cases:
                with self.subTest(native_roles=native_roles, case=name):
                    registry, shared, sessions, roles = self.fixture(native_roles)
                    source = shared.fight
                    initial_sequence = shared.sequence

                    def damage(candidate, runtime):
                        before = candidate.sequence
                        with candidate.effect_resolution():
                            for identity in victims:
                                candidate.apply_effect_damage(
                                    -200, identity, candidate.actors[identity].hp
                                )
                        from wakfu_server.combat_death import death_messages

                        packets = []
                        for identity in victims:
                            if identity > 0:
                                packets.extend(death_messages(runtime, identity))
                        self.assertEqual(
                            [
                                e["actor_id"]
                                for e in candidate.events
                                if e["sequence"] > before and e["kind"] == "death"
                            ],
                            list(victims),
                        )
                        return packets + [runtime._flush()]

                    registry.execute_server(
                        733, -200, damage, expected_sequence=initial_sequence
                    )
                    self.assertIsNot(shared.fight, source)
                    self.assertTrue(all(source.actors[uid].hp == 50 for uid in victims))
                    self.assertTrue(
                        all(shared.fight.actors[uid].hp == 0 for uid in victims)
                    )
                    batches = [registry.drain(733, session) for session in sessions]
                    self.assertEqual(batches[0][0].packets, batches[1][0].packets)
                    deaths = [
                        struct.unpack(">iiiqB", body)[3:]
                        for opcode, body in batches[0][0].packets
                        if opcode == 12727
                    ]
                    self.assertEqual(deaths, [(uid, 0) for uid in victims if uid > 0])
                    with self.assertRaisesRegex(ValueError, "Stale server"):
                        registry.execute_server(
                            733, -200, damage, expected_sequence=initial_sequence
                        )
                    self.assertTrue(all(not registry.drain(733, s) for s in sessions))
                    if survivors:
                        self.assertEqual(
                            (shared.fight.phase, shared.fight.winner), ("active", None)
                        )
                        self.assertTrue(set(survivors) <= set(shared.fight.order))
                        self.assertTrue(set(victims).isdisjoint(shared.fight.order))
                        before = deepcopy(
                            (
                                shared.fight.events,
                                shared.fight.order,
                                shared.fight.turn_id,
                            )
                        )
                        # A KO primary retains account membership while heroes
                        # or another owner continue; coX changes presentation only.
                        self.assertTrue(
                            registry.recover_timeline(
                                733, sessions[0], struct.pack(">i", 733), now_ms=10000
                            )
                        )
                        recovery = [registry.drain(733, s)[0].packets for s in sessions]
                        self.assertEqual(recovery[0], recovery[1])
                        timeline = decoded_timeline(
                            next(body for op, body in recovery[0] if op == 12053)
                        )
                        self.assertEqual(timeline["current"], shared.fight.current.id)
                        self.assertTrue(set(victims).isdisjoint(timeline["order"]))
                        self.assertEqual(
                            before,
                            (
                                shared.fight.events,
                                shared.fight.order,
                                shared.fight.turn_id,
                            ),
                        )
                    else:
                        expected = None if name == "both_teams_ko" else roles.npc_team
                        self.assertEqual(
                            (shared.fight.phase, shared.fight.winner),
                            ("finished", expected),
                        )
                        self.assertFalse(
                            registry.recover_timeline(
                                733, sessions[0], struct.pack(">i", 733), now_ms=10000
                            )
                        )


if __name__ == "__main__":
    unittest.main()
