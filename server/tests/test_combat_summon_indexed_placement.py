import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_qi_surfaces import NativeQISurfaces
from wakfu_server.combat_summon_placement import native_summon_placement


class NativeSummonIndexedPlacementTests(unittest.TestCase):
    def fixture(self):
        # Actual map1134 column and SHA from the published R2 native export;
        # actual2825 trace observed mask256 and selected height-4 here.
        provenance = dict(
            map_id=1134,
            source_sha256="d3211998b492de5fdaf2d3e99f39ffd30af545eed5a8c5df8480ca561e84cb3b",
            output_sha256="a" * 64,
            manifest_sha256="b" * 64,
        )
        surfaces = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=1134,
                source_sha256=provenance["source_sha256"],
                chunks=[
                    dict(
                        x=-18,
                        y=-36,
                        width=18,
                        height=18,
                        columns=[[-7, -21, [[-4, -1]]]],
                    )
                ],
            ),
            map_id=1134,
            source_sha256=provenance["source_sha256"],
        )
        slots = [None] * 127
        slots[2] = dict(
            identity=["actor", 9],
            position=[-7, -21],
            radius=0,
            indexed=True,
            movement_blocking=True,
        )
        fight = SimpleNamespace(
            walkable=set(),
            native_qi_surface_provenance=dict(provenance),
            native_qi_snapshot=dict(x=-7, y=-21, width=1, height=1, cell_masks=[256]),
            native_qi_slots=slots,
        )
        actor = SimpleNamespace(
            id=9, position=(-7, -21, -4), native_obstacle_id=2, physical_radius=0
        )
        return fight, actor, provenance, surfaces

    def providers(self, provenance, surfaces):
        stack = ExitStack()
        prefix = "wakfu_server.combat_qi_surface_catalog."
        stack.enter_context(
            patch(prefix + "native_qi_surface_provenance", return_value=provenance)
        )
        stack.enter_context(patch(prefix + "native_qi_surfaces", return_value=surfaces))
        return stack

    def test_actual_2825_indexed_nonwalkable_surface(self):
        fight, actor, provenance, surfaces = self.fixture()
        with self.providers(provenance, surfaces):
            self.assertTrue(native_summon_placement(fight, actor))
        self.assertNotIn(actor.position, fight.walkable)

    def test_absent_authority_preserves_arbitrary_position_rejection(self):
        fight, actor, _, _ = self.fixture()
        del fight.native_qi_surface_provenance
        self.assertFalse(native_summon_placement(fight, actor))

    def test_wrong_or_missing_indexed_height_rejected(self):
        for position, mask in [
            ((-7, -21, 0), 256),
            ((-7, -21, -32768), 256),
            ((-7, -21, -4), 257),
            ((-8, -21, -4), 256),
        ]:
            with self.subTest(position=position, mask=mask):
                fight, actor, provenance, surfaces = self.fixture()
                actor.position = position
                fight.native_qi_snapshot["cell_masks"] = [mask]
                with self.providers(provenance, surfaces):
                    self.assertFalse(native_summon_placement(fight, actor))

    def test_forged_map_provenance_rejected(self):
        fight, actor, provenance, surfaces = self.fixture()
        fight.native_qi_surface_provenance["output_sha256"] = "c" * 64
        with self.providers(provenance, surfaces):
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                native_summon_placement(fight, actor)

    def test_slot_identity_radius_and_position_must_match(self):
        for key, value in [("identity", ["actor", 90]), ("radius", 1)]:
            with self.subTest(key=key):
                fight, actor, provenance, surfaces = self.fixture()
                fight.native_qi_slots[2][key] = value
                with self.providers(provenance, surfaces):
                    self.assertFalse(native_summon_placement(fight, actor))

    def test_outside_registered_slot_is_invalid_authority(self):
        fight, actor, provenance, surfaces = self.fixture()
        fight.native_qi_slots[2]["position"] = [-6, -21]
        with self.providers(provenance, surfaces):
            with self.assertRaisesRegex(ValueError, "outside QI"):
                native_summon_placement(fight, actor)

    def test_ordinary_walkable_route_requires_no_new_provider(self):
        fight, actor, _, _ = self.fixture()
        fight.walkable.add(actor.position)
        del fight.native_qi_surface_provenance
        self.assertTrue(native_summon_placement(fight, actor))

    def test_registration_accepts_proven_surface_keeps_identity_gate(self):
        from test_combat_summon import SummonTests, Ordinary
        from wakfu_server.combat_summon import RegisteredSummonAuthority

        fight, actor, registration = SummonTests().fixture()
        source, _, provenance, surfaces = self.fixture()
        actor.position = (-7, -21, -4)
        source.native_qi_slots[2]["identity"] = ["actor", actor.id]
        for name in (
            "native_qi_snapshot",
            "native_qi_slots",
            "native_qi_surface_provenance",
        ):
            setattr(fight, name, getattr(source, name))
        authority = RegisteredSummonAuthority(Ordinary())
        with self.providers(provenance, surfaces):
            authority.register(
                fight, actor, registration, new_order=[7, 901, -7], new_turn_index=0
            )
            self.assertIs(fight.actors[901], actor)
            with self.assertRaisesRegex(ValueError, "Invalid owned summon"):
                authority.register(
                    fight, actor, registration, new_order=[7, 901, -7], new_turn_index=0
                )
