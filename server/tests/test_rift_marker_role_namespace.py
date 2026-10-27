"""Publish frozen Rift roles through both real marker import paths.

No catalog, database, metadata resolver seam or effect execution is involved.
This covers the exact role reconstruction consumer that disconnected entry.
"""
from copy import deepcopy
import importlib
from types import SimpleNamespace
import unittest

from wakfu_server.combat_encounter_roles import EncounterRoles
from wakfu_server.combat_multiplayer_wire import decode_external
from wakfu_server.rift_encounter_roles import roles_for_catalog
from wakfu_server.rift_native_gameplay_policy import POLICY


def _shared():
    catalog = {"type": "INFINITE_WAVE", "map_id": 1314, "species_refs": [3]}
    policy = {
        "native_gameplay": {
            "enabled": True,
            "policy": POLICY,
            "authority": "native_consumers_with_reconstructed_producers",
            "enabled_types": ["INFINITE_WAVE", "ULTIMATE_INFINITE_WAVE"],
            "encounter_roles": {
                "policy": "wakemu.rift.ultimate-encounter-roles.v1",
                "player_team": 1,
                "npc_team": 0,
            },
        }
    }
    roles = roles_for_catalog(catalog, policy, monster_references=[3])
    assert isinstance(roles, EncounterRoles)
    player = SimpleNamespace(id=17, team=1)
    enemy = SimpleNamespace(id=-201, team=0)
    fight = SimpleNamespace(
        id=53,
        phase="placement",
        native_table_turn=0,
        actors={player.id: player, enemy.id: enemy},
        native_encounter_roles=roles.record(),
    )
    arena = dict(
        map_id=1314,
        instance_id=17,
        x=0,
        y=0,
        width=1,
        height=1,
        min_z=0,
        max_z=0,
        cell_masks=[0],
        team_values=[],
    )
    return SimpleNamespace(
        fight=fight,
        map_id=1314,
        instance_id=288230376151711751,
        participants={1: SimpleNamespace(character_id=17, account_id=1)},
        is_duel=False,
        join_context={
            "arena": arena,
            "terrain_effect_id": 46,
            "leaders": {0: -201, 1: 17},
            "monsters": {
                -201: {"id": -201, "map_id": 1314, "instance_id": 288230376151711751}
            },
            "world_marker_cells": ((14, 9),),
            "world_marker_origin": (14, 9, 0),
        },
    )


class RiftMarkerNamespaceTests(unittest.TestCase):
    def test_public_and_legacy_marker_consumers_publish_frozen_classic_roles(self):
        packets = []
        for namespace in (
            "wakfu_server.combat_external_markers",
            "wakfu_server.combat.combat_external_markers",
        ):
            with self.subTest(namespace=namespace):
                consumer = importlib.import_module(namespace).ExternalFightMarkers
                packet = consumer._body(_shared(), started_at_ms=1000)
                self.assertEqual(packet[0], 13753)
                self.assertIsInstance(packet[1], bytes)
                decoded = decode_external(packet[1])
                self.assertEqual(decoded["fight_id"], 53)
                self.assertEqual(decoded["teams"], [(17, 1), (-201, 0)])
                packets.append(packet)
                malformed = _shared()
                malformed.fight.native_encounter_roles = deepcopy(
                    malformed.fight.native_encounter_roles
                )
                malformed.fight.native_encounter_roles["npc_team"] = 1
                with self.assertRaises(ValueError):
                    consumer._body(malformed, started_at_ms=1000)
        self.assertEqual(len(packets), 2)
        self.assertEqual(packets[0], packets[1])


if __name__ == "__main__":
    unittest.main()
