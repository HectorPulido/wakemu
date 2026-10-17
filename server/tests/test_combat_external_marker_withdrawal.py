"""Former owners receive native external registration after certified departure."""
import unittest
from types import SimpleNamespace

from test_combat_withdrawn_ordinary_authority import shared_fixture
from wakfu_server.combat_external_markers import ExternalFightMarkers
from wakfu_server.combat_multiplayer_wire import decode_external
from wakfu_server.combat_monster_world import spawn_group
from wakfu_server.combat_pve_departure import retired_pve_actor_ids
from wakfu_server.combat_wire import arena
from wakfu_server import monsters


def withdrawn_shared(instance_id=0):
    first, second, monster, fight, _deck = shared_fixture(native_qi=True)
    # Spell fixtures expose a partial combat dictionary. Public appearances
    # require the exact owned native world instance, including all fields.
    monster = monsters.owned_instance(
        monster["ref"],
        fight.actors[-7].effective_level,
        -7,
        map_id=1134,
        instance_id=instance_id,
        x=fight.actors[-7].position[0],
        y=fight.actors[-7].position[1],
        z=fight.actors[-7].position[2],
        team=fight.actors[-7].team,
    )
    participants = {
        3: SimpleNamespace(character_id=7, account_id=3, generation="former"),
        4: SimpleNamespace(character_id=8, account_id=4, generation="active"),
    }
    return SimpleNamespace(
        fight=fight,
        map_id=1134,
        instance_id=instance_id,
        is_duel=False,
        participants=participants,
        group_lease=((1134, instance_id, 77), "leased", fight.id, 1),
        join_context={
            "arena": arena(1134, instance_id, fight.walkable, fight.placement),
            "terrain_effect_id": 378,
            "leaders": {0: 7, 1: -7},
            "monsters": {-7: monster},
            "world_marker_cells": ((monster["x"], monster["y"]),),
            "world_marker_origin": (monster["x"], monster["y"], monster["z"]),
            "fight_started_at": 99.5,
        },
    )


class FormerOwnerExternalMarkerTests(unittest.TestCase):
    def test_certified_departure_reopens_external_registration_and_retains_history(
        self,
    ):
        for instance_id in (0, 3):
            with self.subTest(instance_id=instance_id):
                shared = withdrawn_shared(instance_id)
                fight = shared.fight
                self.assertEqual(retired_pve_actor_ids(fight), {7})
                actor = fight.actors[7]
                sessions = dict(shared.participants)
                markers = ExternalFightMarkers()
                created = markers.update(shared, now_ms=100000, now_monotonic=100.0)
                self.assertEqual(created[0], 13753)
                packets = markers.world_snapshots(
                    1134, instance_id, exclude_character_id=7, known_phases={}
                )
                self.assertEqual([opcode for opcode, _ in packets], [12608, 13753])
                # The leased NPC is registered before cuY references its leader.
                self.assertEqual(
                    packets[0][1],
                    spawn_group(
                        tuple(shared.join_context["monsters"].values()), group_id=77
                    ),
                )
                self.assertEqual(packets[1], created)
                decoded = decode_external(packets[1][1])
                self.assertEqual(decoded["fight_id"], fight.id)
                self.assertEqual(decoded["myr"], [8, -7])
                self.assertNotIn(7, {identity for identity, _ in decoded["teams"]})
                self.assertIn((8, 0), decoded["teams"])
                self.assertIn((-7, 1), decoded["teams"])
                self.assertEqual(shared.join_context["leaders"], {0: 7, 1: -7})
                self.assertEqual(
                    markers.world_snapshots(1134, instance_id, exclude_character_id=8),
                    (),
                )
                self.assertEqual(
                    markers.snapshots(1134, instance_id, exclude_character_id=8), ()
                )
                self.assertEqual(
                    markers.world_snapshots(
                        1134, instance_id + 1, exclude_character_id=7
                    ),
                    (),
                )
                self.assertEqual(
                    markers.world_snapshots(1135, instance_id, exclude_character_id=7),
                    (),
                )
                self.assertIs(fight.actors[7], actor)
                self.assertEqual(shared.participants, sessions)
                self.assertEqual(retired_pve_actor_ids(fight), {7})

    def test_withdrawn_flag_without_certified_departure_does_not_reopen_marker(self):
        shared = withdrawn_shared()
        shared.fight.native_pve_departures = {}
        self.assertTrue(shared.fight.actors[7].pve_withdrawn)
        markers = ExternalFightMarkers()
        self.assertIsNotNone(markers.update(shared, now_ms=100000, now_monotonic=100.0))
        self.assertEqual(markers.world_snapshots(1134, 0, exclude_character_id=7), ())

    def test_malformed_departure_cannot_publish_an_uncertified_marker(self):
        shared = withdrawn_shared()
        shared.fight.native_pve_departures[7]["source"] = "foreign"
        markers = ExternalFightMarkers()
        self.assertIsNone(markers.update(shared, now_ms=100000, now_monotonic=100.0))
        self.assertEqual(markers.world_snapshots(1134, 0, exclude_character_id=7), ())

    def test_retired_starter_without_current_owned_team_leader_cannot_publish(self):
        shared = withdrawn_shared()
        del shared.participants[4]
        markers = ExternalFightMarkers()
        self.assertIsNone(markers.update(shared, now_ms=100000, now_monotonic=100.0))
        self.assertEqual(markers.world_snapshots(1134, 0, exclude_character_id=7), ())
        self.assertIn(8, shared.fight.actors)  # An actor alone is not an owner session.

    def test_stale_outside_context_removes_certified_retiree_once_without_recreation(
        self,
    ):
        from copy import deepcopy
        import struct
        from wakfu_server.combat_external_markers import MarkerPublications
        from wakfu_server.combat_multiplayer_wire import external, decode_removed

        shared = withdrawn_shared()
        markers = ExternalFightMarkers()
        created = markers.update(shared, now_ms=100000, now_monotonic=100.0)
        current = decode_external(created[1])
        stale = dict(current, teams=tuple(current["teams"]) + ((7, 0),))
        cursor = MarkerPublications()
        scope = (9, "outside-lease", 42, 1134, 0)

        def write(packets):
            cursor.after_write(
                b"".join(
                    struct.pack(">IH", len(body) + 6, opcode) + body
                    for opcode, body in packets
                ),
                scope,
            )

        write(((13753, external(stale)[1]),))
        # A real world entity replacement is a separate publication. The
        # tracking envelope must not reattach this certified withdrawn actor.
        world_entity = b"opaque-current-world-entity"
        world_packet = (
            12608,
            b"\x00\x01" + struct.pack(">BqH", 0, 7, len(world_entity)) + world_entity,
        )
        write((world_packet,))
        historical_actor = shared.fight.actors[7]
        participants = dict(shared.participants)
        departures = deepcopy(shared.fight.native_pve_departures)

        def reconcile():
            return markers.world_snapshots(
                1134,
                0,
                exclude_character_id=42,
                known_phases=cursor.snapshot(scope),
                known_rosters=cursor.roster_snapshot(scope),
                unbound_members=cursor.unbound_snapshot(scope),
            )

        packets = reconcile()
        self.assertEqual([opcode for opcode, _ in packets], [12347])
        self.assertEqual(
            decode_removed(packets[0][1]),
            dict(fight_id=shared.fight.id, action_id=0, action_context=-1, actor_id=7),
        )
        self.assertIn(7, cursor.roster_snapshot(scope)[shared.fight.id])
        self.assertEqual(reconcile(), packets)  # No successful write yet.
        write(packets)
        self.assertNotIn(7, cursor.roster_snapshot(scope)[shared.fight.id])
        self.assertNotIn(7, cursor.unbound_snapshot(scope)[shared.fight.id])
        self.assertEqual(reconcile(), ())
        write((world_packet,))
        self.assertEqual(reconcile(), ())  # Retired member is never rebound.
        self.assertIs(shared.fight.actors[7], historical_actor)
        self.assertEqual(shared.participants, participants)
        self.assertEqual(shared.fight.native_pve_departures, departures)
        self.assertEqual(retired_pve_actor_ids(shared.fight), {7})
        self.assertNotIn(7, {identity for identity, _ in current["teams"]})
