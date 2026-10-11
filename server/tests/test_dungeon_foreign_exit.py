"""Only exact pinned native foreign exterior bindings may leave an instance."""
import copy
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server import dungeon_exit
from wakfu_server.dungeon_runtime_config import canonical_hash


class ForeignDungeonExitTests(unittest.TestCase):
    def setUp(self):
        self.destination = dict(
            destination_id=3987,
            map_id=1211,
            x=8368,
            y=8352,
            z=0,
            criterion="",
            cyZ=-1,
            cyX=0,
            cyW=0,
            item_reference=0,
            native_altitude_walkable=True,
        )
        self.source = dict(id=17381, map_id=456, destinations=[self.destination])
        target = {key: self.destination[key] for key in ("map_id", "x", "y", "z")}
        self.topology = dict(
            policy="native_mixed_victory_policy",
            asset_map_id=456,
            physical_exit_objects=[
                dict(
                    source_id=17381,
                    room_order=1,
                    destination_id=3987,
                    destination=target,
                )
            ],
            native_foreign_exterior_policy=dict(
                reason="Reviewed literal foreign native exterior",
                bindings=[
                    dict(
                        source_id=17381,
                        source_sha256=canonical_hash(self.source),
                        destination_id=3987,
                        destination=target,
                    )
                ],
            ),
        )
        self.character = dict(map_id=456, instance_id=42)
        self.body = struct.pack(">qiBi", 17381, 3987, 0, 2)
        self.catalog = patch(
            "wakfu_server.maps.dungeon_exit.generic_transports.source",
            side_effect=lambda mid, identity: copy.deepcopy(self.source)
            if (mid, identity) == (456, 17381)
            else None,
        )
        self.geometry = patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(cells={(8368, 8352, 0)}),
        )
        self.catalog.start()
        self.geometry.start()
        self.addCleanup(self.catalog.stop)
        self.addCleanup(self.geometry.stop)

    def resolve(self, topology):
        return dungeon_exit.resolve(
            self.character,
            self.body,
            entry_map_id=235,
            source_allowed=lambda actor, source: True,
            topology=topology,
        )

    def test_exact_foreign_binding_resolves_and_automatic_cancel_uses_it(self):
        self.assertEqual(self.resolve(self.topology)["map_id"], 1211)
        self.assertEqual(
            dungeon_exit.automatic_destination(
                self.character, {"entry_map_id": 235}, {"topology": self.topology}
            ),
            dict(map_id=1211, x=8368, y=8352, z=0),
        )

    def test_missing_contract_or_wrong_asset_map_rejected(self):
        for topology in (None, {}, dict(self.topology, asset_map_id=457)):
            with self.subTest(topology=topology), self.assertRaises(ValueError):
                self.resolve(topology)

    def test_foreign_identity_hash_endpoint_and_policy_tampering_rejected(self):
        for kind in (
            "hash",
            "identity",
            "destination",
            "duplicate",
            "policy",
            "unpinned",
        ):
            topology = copy.deepcopy(self.topology)
            binding = topology["native_foreign_exterior_policy"]["bindings"][0]
            if kind == "hash":
                binding["source_sha256"] = "0" * 64
            if kind == "identity":
                binding["source_id"] = 17382
            if kind == "destination":
                binding["destination"]["x"] += 1
            if kind == "duplicate":
                topology["native_foreign_exterior_policy"]["bindings"].append(
                    copy.deepcopy(binding)
                )
            if kind == "policy":
                topology["policy"] = "native_teleport_victory_policy"
            if kind == "unpinned":
                topology["physical_exit_objects"] = []
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.resolve(topology)

    def test_paid_conditional_unwalkable_native_binding_rejected_even_with_current_hash(
        self,
    ):
        for field, value in (
            ("criterion", "HasItem(1)"),
            ("cyZ", 0),
            ("cyX", 1),
            ("native_altitude_walkable", False),
        ):
            old = copy.deepcopy(self.source)
            self.destination[field] = value
            topology = copy.deepcopy(self.topology)
            topology["native_foreign_exterior_policy"]["bindings"][0][
                "source_sha256"
            ] = canonical_hash(self.source)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.resolve(topology)
            self.source = old
            self.destination = self.source["destinations"][0]

    def test_actual_walk_geometry_required(self):
        with patch(
            "wakfu_server.combat_geometry.published_geometry",
            return_value=SimpleNamespace(cells=set()),
        ), self.assertRaises(ValueError):
            self.resolve(self.topology)

    def test_foreign_allowlist_never_overrides_authoritative_approach(self):
        with self.assertRaises(ValueError):
            dungeon_exit.resolve(
                self.character,
                self.body,
                entry_map_id=235,
                source_allowed=lambda actor, source: False,
                topology=self.topology,
            )


if __name__ == "__main__":
    unittest.main()
