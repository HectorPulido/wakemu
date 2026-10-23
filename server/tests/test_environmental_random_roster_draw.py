"""Deterministic exact-species draw contract, independent of live catalogs."""
import unittest
import struct
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.objectives.environmental_random_rosters import draw_slots


class EnvironmentalRandomRosterDrawTests(unittest.TestCase):
    def test_exact_pool_native_levels_stable_event_draw_without_forced_coverage(self):
        species = {101: 3, 102: 80, 103: 150, 104: 2, 105: 230, 106: 12}
        rows = draw_slots("a" * 64, 2, 2, 2, species)
        self.assertEqual(rows, draw_slots("a" * 64, 2, 2, 2, species))
        self.assertEqual(len(rows), 4)
        self.assertEqual({r["group_ordinal"] for r in rows}, {0, 1})
        self.assertLess(len({r["monster_reference"] for r in rows}), len(species))
        self.assertTrue(
            all(
                r["monster_reference"] in species
                and r["native_level"] == species[r["monster_reference"]]
                for r in rows
            )
        )
        # A herd's sole explicit special breed is retained even though its
        # native level lies outside a hypothetical player challenge bracket.
        herd = draw_slots("b" * 64, 3, 2, 5, {5189: 213})
        self.assertTrue(6 <= len(herd) <= 15)
        self.assertEqual(
            {(r["monster_reference"], r["native_level"]) for r in herd}, {(5189, 213)}
        )
        for ordinal in range(3):
            members = [r for r in herd if r["group_ordinal"] == ordinal]
            self.assertEqual(
                [r["member_ordinal"] for r in members], list(range(len(members)))
            )

    def test_non_native_or_unbounded_draw_inputs_fail_before_any_persistence(self):
        base = ("a" * 64, 2, 2, 5, {101: 3})
        for arguments in [
            (base[0], True, 2, 5, base[4]),
            ("x" * 64, *base[1:]),
            (base[0], 2, 1, 5, base[4]),
            (base[0], 2, 2, 9, base[4]),
            (base[0], 2, 2, 5, {101: True}),
            (base[0], 2, 2, 5, {101: 0}),
            (base[0], 2, 2, 5, {}),
            (base[0], 4096, 2, 5, base[4]),
        ]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                draw_slots(*arguments)

    def test_scene_excludes_every_original_interactive_extra_cell_and_published_npc(
        self,
    ):
        import wakfu_server
        from wakfu_server.native_interactive_components import envelope
        from wakfu_server.objectives.environmental_random_rosters import _scene_cells

        body = struct.pack(">hiih", 327, 1, 2, 0) + bytes(7) + struct.pack(">h", 2)
        body += (
            struct.pack(">iih", 3, 4, 0)
            + struct.pack(">iih", 5, 6, 0)
            + struct.pack(">H", 0)
        )
        interactive = dict(x=1, y=2, payload_hex=envelope({1: body}).hex())
        with patch.object(
            wakfu_server,
            "npc_world",
            SimpleNamespace(load_scene=lambda *args: [dict(x=7, y=8)]),
            create=True,
        ), patch.object(
            wakfu_server,
            "npc_placements",
            SimpleNamespace(load_scene=lambda *args: [dict(x=9, y=10)]),
            create=True,
        ), patch.object(
            wakfu_server,
            "world_static",
            SimpleNamespace(objects=lambda *args: [interactive]),
            create=True,
        ):
            self.assertEqual(
                _scene_cells(None, 327, 0), {(1, 2), (3, 4), (5, 6), (7, 8), (9, 10)}
            )
            interactive["payload_hex"] = envelope({1: body[:30]}).hex()
            with self.assertRaises(ValueError):
                _scene_cells(None, 327, 0)
