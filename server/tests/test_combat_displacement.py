from copy import deepcopy
from dataclasses import replace
import random
import unittest
from unittest.mock import patch
import test_combat_effect_runtime as fixtures
from wakfu_server.combat_displacement import (
    cardinal_vector,
    displacement_additional,
    NativeDisplacementHandler,
)
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    ordinary_cast_authority,
)
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_qi_surfaces import NativeQISurfaces
from wakfu_server.combat_effect_dispatch import (
    EffectInvocation,
    run_effect_transaction,
    UnsupportedEffectExecution,
)


def synthetic_surface_authority(cells):
    """Explicit flat test map; every authorized cell has exactly one z=0 Vy."""
    cells = tuple(sorted(set(tuple(cell) for cell in cells)))
    if not cells:
        raise ValueError("Synthetic surface fixture needs explicit cells")
    xmin = min(cell[0] for cell in cells)
    ymin = min(cell[1] for cell in cells)
    xmax = max(cell[0] for cell in cells)
    ymax = max(cell[1] for cell in cells)
    width, height = xmax - xmin + 1, ymax - ymin + 1
    qi = NativeQISnapshot(
        dict(
            x=xmin,
            y=ymin,
            width=width,
            height=height,
            cell_masks=[0] * (width * height),
        )
    )
    surfaces = NativeQISurfaces(
        dict(
            schema="native-QI-Vy-columns-v1",
            map_id=999999,
            source_sha256="a" * 64,
            chunks=[
                dict(
                    x=xmin,
                    y=ymin,
                    width=width,
                    height=height,
                    columns=[[x, y, [[z, 0]]] for x, y, z in cells],
                )
            ],
        ),
        map_id=999999,
        source_sha256="a" * 64,
    )

    def selected_surface(_fight, cell):
        return surfaces.i(qi, *cell)

    return selected_surface


def install_synthetic_qi_occupancy(fight, *, physical_radii=None):
    """Install explicitly declared actor footprints for the synthetic arena."""
    from wakfu_server.combat_qi_registry import NativeQIRegistry

    cells = {tuple(cell) for cell in fight.walkable}
    cells.update(tuple(actor.position) for actor in fight.actors.values())
    xmin = min(cell[0] for cell in cells)
    ymin = min(cell[1] for cell in cells)
    xmax = max(cell[0] for cell in cells)
    ymax = max(cell[1] for cell in cells)
    width, height = xmax - xmin + 1, ymax - ymin + 1
    arena = dict(
        x=xmin, y=ymin, width=width, height=height, cell_masks=[0] * (width * height)
    )
    slots = [None] * 127
    for slot, actor in enumerate(fight.actors.values()):
        actor.native_obstacle_id = slot
        actor.physical_radius = (physical_radii or {}).get(actor.id, 0)
        if not hasattr(actor, "native_carrier_id"):
            actor.native_carrier_id = None
        if not hasattr(actor, "native_carried_actor_id"):
            actor.native_carried_actor_id = None
        slots[slot] = dict(
            identity=["actor", actor.id],
            position=list(actor.position[:2]),
            radius=actor.physical_radius,
            indexed=True,
            movement_blocking=True,
        )
    registry = NativeQIRegistry(arena, slots)
    registry.capture_fresh_cell_topology(
        [slot for slot, row in enumerate(slots) if row is not None]
    )
    fight.native_qi_snapshot = arena
    fight.native_qi_slots = registry.serialized_slots()
    fight.native_qi_touched_cells = registry.serialized_cells()
    fight.native_qi_byte_topology = registry.serialized_byte_topology()
    fight.native_qi_movement_override = False
    fight.native_qi_ignored_slots = []
    if not hasattr(fight, "native_effect_areas"):
        fight.native_effect_areas = {}


class NativeDisplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeRuntimeFactoryTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.NativeRuntimeFactoryTests()
        self.fixture.setUp()
        self.preview = deepcopy(self.fixture.fight)
        self.preview.native_effect_uid_next = 200
        self.preview.walkable = {
            (x, y, 0) for x in range(-10, 11) for y in range(-10, 11)
        }
        self.preview.actors[8].position = (0, -5, 0)
        self.preview.actors[-7].position = (4, 0, 0)
        self.authority = OrdinaryActorAuthority(
            # Match Actor(7)'s explicit level-1 fixture snapshot; spell-book
            # authority must not infer the level from the deck or actor map.
            characters={7: dict(id=7, breed=15, level=1)},
            monsters={8: dict(id=8, ref=5525), -7: dict(id=-7, ref=5525)},
            decks={7: []},
            excluded_decks={7: []},
        )
        self.effects = dict(self.fixture.effects)
        self.selected_surface = synthetic_surface_authority(self.preview.walkable)
        install_synthetic_qi_occupancy(self.preview)
        self.packets = []
        self.handler = NativeDisplacementHandler(
            self.preview,
            self.packets,
            action_id=1,
            allocate_uid=self.preview.allocate_effect_uid,
            authority=self.authority,
            selected_surface=self.selected_surface,
        )

    def execute(self, reference, *, target=-7, cell=(4, 0, 0), level=1):
        effect = self.effects[str(reference)]
        return self.handler(
            effect, None, EffectInvocation(reference, level, 7, target, cell)
        )

    def stair_fixture(self):
        self.preview.actors[7].position = (-15, -3, 0)
        self.preview.actors[-7].position = (-15, -5, -1)
        self.preview.actors[-7].native_los_height = 4
        self.preview.walkable = {(-15, -3, 0), (-15, -4, 0), (-15, -5, -1)}
        self.authority.monsters[-7]["map_id"] = 1134
        # Native short-form pull stops adjacent to caster (eXK/faz), unlike
        # the three-parameter direction5 fixture which deliberately pulls on.
        self.effects["326690"] = deepcopy(self.effects["326690"])
        self.effects["326690"]["parameters"] = self.effects["326690"]["parameters"][:4]
        self.effects["326690"]["parameter_count"] = 2
        install_synthetic_qi_occupancy(self.preview)

    def test_native_pull_climbs_verified_surface_without_flat_walk_edge(self):
        self.stair_fixture()
        self.preview.edges = frozenset()
        self.execute(326690, cell=(-15, -3, 0))
        self.assertEqual(self.preview.actors[-7].position, (-15, -4, 0))

    def test_native_height_transition_collision_preserves_position_uid_packets(self):
        self.stair_fixture()
        self.preview.actors[8].position = (-15, -4, 0)
        install_synthetic_qi_occupancy(self.preview)
        with self.assertRaisesRegex(ValueError, "collision"):
            self.execute(326690, cell=(-15, -3, 0))
        self.assertEqual(self.preview.actors[-7].position, (-15, -5, -1))
        self.assertEqual(self.preview.native_effect_uid_next, 200)
        self.assertEqual(self.packets, [])

    def test_later_collision_rolls_back_earlier_valid_height_transition(self):
        self.stair_fixture()
        effect = self.effects["326690"]
        effect["parameters"] += [5, 0]
        effect["parameter_count"] = 3
        with self.assertRaisesRegex(ValueError, "collision"):
            self.execute(326690, cell=(-15, -3, 0))
        self.assertEqual(self.preview.actors[-7].position, (-15, -5, -1))
        self.assertEqual(self.preview.native_effect_uid_next, 200)
        self.assertEqual(self.packets, [])

    def test_native_additional_exact_jar_bytes(self):
        self.assertEqual(
            displacement_additional(302, destination=(-2, 3, -1)).hex(),
            "7a1808feffffffffffffffff01100318ffffffffffffffffff01880201",
        )
        self.assertEqual(
            displacement_additional(300, path=[(2, 0, 0), (3, 0, 1)]).hex(),
            "b204100a060802100018000a06080310001801",
        )
        self.assertEqual(
            displacement_additional(
                422, source_original=(1, 2, 3), target_original=(4, 5, 6)
            ).hex(),
            "7a06080410051806ba0106080110021803",
        )

    def test_native_cardinal_sector_boundaries(self):
        # aBz.bp native tie (1,1) picks +X, not diagonal;2,1 likewise.
        self.assertEqual(cardinal_vector(1, 1), (1, 0))
        self.assertEqual(cardinal_vector(1, -1), (0, -1))
        self.assertEqual(cardinal_vector(-1, 1), (0, 1))

    def test_real_pull_catalog326690_direction5_toward_effect_cell(self):
        self.execute(326690, cell=(0, 0, 0))
        self.assertEqual(self.preview.actors[-7].position, (2, 0, 0))
        self.assertEqual(self.preview.actors[-7].mp, 3)
        self.assertEqual(self.packets[0][0], 12613)

    def test_real_push_catalog358000_away_caster(self):
        self.execute(358000)
        self.assertEqual(self.preview.actors[-7].position, (5, 0, 0))
        self.assertEqual(self.preview.actors[-7].ap, 6)

    def test_registered_area_push_uses_area_center_and_preserves_owner(self):
        from wakfu_server.combat_effect_area_targets import NativeAreaTarget

        owner = self.preview.actors[7]
        owner.position = (0, 4, 0)
        self.preview.actors[-7].position = (0, 1, 0)
        install_synthetic_qi_occupancy(self.preview)
        area = NativeAreaTarget(901, (0, 0, 0), owner.team, owner.id)
        invocation = EffectInvocation(358000, 1, area.id, -7, area.position)
        with patch("wakfu_server.combat_area_authority.area_guards") as guards, patch(
            "wakfu_server.combat_effect_area_targets.area_targets", return_value=(area,)
        ):
            self.handler(self.effects["358000"], None, invocation)
        guards.assert_called_once_with(self.preview, area.id)
        self.assertEqual(self.preview.actors[-7].position, (0, 2, 0))
        self.assertEqual(owner.position, (0, 4, 0))

    def test_registered_area_recipient_cancels_before_area_source_lookup(self):
        self.preview.native_effect_areas = {901: {}}
        invocation = EffectInvocation(358000, 1, 901, 901, (0, 0, 0))
        with patch("wakfu_server.combat_area_authority.area_guards") as guards:
            self.assertFalse(self.handler(self.effects["358000"], None, invocation))
        guards.assert_called_once_with(self.preview, 901)
        self.assertEqual(self.packets, [])

    def test_resolver_order_flags_preserve_displacement_and_unknown_rejection(self):
        effect = deepcopy(self.effects["358000"])
        for flag in (3, 5, 14, 26):
            with self.subTest(flag=flag):
                self.preview.actors[-7].position = (4, 0, 0)
                install_synthetic_qi_occupancy(self.preview)
                effect["native_effect_flags"] = [flag]
                self.handler(
                    effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0))
                )
                self.assertEqual(self.preview.actors[-7].position, (5, 0, 0))
                self.assertEqual(effect["native_effect_flags"], [flag])
        effect["native_effect_flags"] = [16]
        before = self.preview.actors[-7].position
        with self.assertRaisesRegex(ValueError, "Unhandled native displacement flags"):
            self.handler(effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0)))
        self.assertEqual(self.preview.actors[-7].position, before)

    def test_zone_preview_flag_changes_neither_geometry_nor_native_packet(self):
        results = []
        for flags in ([], [3]):
            self.setUp()
            effect = deepcopy(self.effects["358000"])
            effect["native_effect_flags"] = flags
            self.handler(effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0)))
            results.append(
                (
                    self.preview.actors[-7].position,
                    tuple(self.packets),
                    self.preview.native_effect_uid_next,
                )
            )
            self.assertEqual(effect["native_effect_flags"], flags)
        self.assertEqual(results[0], results[1])

    def test_do_not_uncarry_flag37_preserves_ordinary_displacement_result(self):
        results = []
        for enabled in (False, True):
            self.setUp()
            effect = deepcopy(self.effects["358000"])
            effect["native_effect_flags"] = [37] if enabled else []
            self.handler(effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0)))
            results.append(
                (
                    self.preview.actors[-7].position,
                    tuple(self.packets),
                    self.preview.native_effect_uid_next,
                )
            )
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], (5, 0, 0))

    def test_null_push_recipient_cancels_before_caster_guards(self):
        class UnavailableCaster:
            def __call__(self, *args):
                raise AssertionError("Native null fax check precedes actor guards")

        self.handler.authority = UnavailableCaster()
        effect = self.effects["358000"]
        before = self.preview.actors[7].position
        self.assertFalse(
            self.handler(effect, None, EffectInvocation(358000, 1, 7, None, (4, 0, 0)))
        )
        self.assertEqual(self.preview.actors[7].position, before)
        self.assertEqual(self.packets, [])
        self.assertEqual(self.preview.native_effect_uid_next, 200)

    def test_move_away_cell_carried_caster_is_native_noop(self):
        original = self.authority

        class CarriedAuthority:
            def __call__(self, fight, actor):
                metadata = original(fight, actor)
                return replace(metadata, is_carried=True) if actor.id == 7 else metadata

            def properties(self, fight, actor):
                raise AssertionError(
                    "Native carried guard precedes property/path calculation"
                )

        self.handler.authority = CarriedAuthority()
        effect = deepcopy(self.effects["358000"])
        effect["effect_class"] = 331
        effect["parameters"] = effect["parameters"][:2]
        effect["parameter_count"] = 1
        before = self.preview.actors[7].position
        self.assertFalse(
            self.handler(effect, None, EffectInvocation(358000, 1, 7, None, (4, 0, 0)))
        )
        self.assertEqual(self.preview.actors[7].position, before)
        self.assertEqual(self.packets, [])
        self.assertEqual(self.preview.native_effect_uid_next, 200)

    def test_approach_carried_caster_is_native_noop(self):
        original = self.authority

        class CarriedAuthority:
            def __call__(self, fight, actor):
                return replace(original(fight, actor), is_carried=True)

            def properties(self, *args):
                raise AssertionError("eXq.fOS rejects before property/path work")

        self.handler.authority = CarriedAuthority()
        effect = deepcopy(self.effects["358000"])
        effect.update(effect_class=305, parameters=[2.0, 0.0], parameter_count=1)
        self.assertFalse(
            self.handler(effect, None, EffectInvocation(358000, 1, 7, None, (4, 0, 0)))
        )
        self.assertEqual(self.packets, [])
        self.assertEqual(self.preview.native_effect_uid_next, 200)

    def test_stabilized_large_target_rejects_before_unsupported_footprint(self):
        original = self.authority

        class StabilizedAuthority:
            def __call__(self, fight, actor):
                return original(fight, actor)

            def properties(self, fight, actor):
                return {11} if actor.id == -7 else original.properties(fight, actor)

        self.handler.authority = StabilizedAuthority()
        self.preview.actors[-7].physical_radius = 1
        before = self.preview.actors[-7].position
        self.assertFalse(
            self.handler(
                self.effects["358000"],
                None,
                EffectInvocation(358000, 1, 7, -7, (4, 0, 0)),
            )
        )
        self.assertEqual(self.preview.actors[-7].position, before)
        self.assertEqual(self.packets, [])
        self.assertEqual(self.preview.native_effect_uid_next, 200)

    def test_swap_carried_actor_is_native_noop(self):
        original = self.authority

        class CarriedAuthority:
            def __call__(self, fight, actor):
                return replace(original(fight, actor), is_carried=actor.id == -7)

            def properties(self, fight, actor):
                return original.properties(fight, actor)

        self.handler.authority = CarriedAuthority()
        effect = deepcopy(self.effects["358000"])
        effect.update(effect_class=422, parameters=[], parameter_count=0)
        before = tuple(actor.position for actor in self.preview.actors.values())
        self.assertFalse(
            self.handler(effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0)))
        )
        self.assertEqual(
            tuple(actor.position for actor in self.preview.actors.values()), before
        )
        self.assertEqual(self.packets, [])
        self.assertEqual(self.preview.native_effect_uid_next, 200)

    def test_carried_caster_does_not_prevent_forced_target_movement(self):
        original = self.authority

        class CarriedSourceAuthority:
            def __call__(self, fight, actor):
                return replace(original(fight, actor), is_carried=actor.id == 7)

            def properties(self, fight, actor):
                return original.properties(fight, actor)

        self.handler.authority = CarriedSourceAuthority()
        before = self.preview.actors[7].position
        self.assertTrue(
            self.handler(
                self.effects["358000"],
                None,
                EffectInvocation(358000, 1, 7, -7, (4, 0, 0)),
            )
        )
        self.assertEqual(self.preview.actors[7].position, before)
        self.assertNotEqual(self.preview.actors[-7].position, (4, 0, 0))

    def test_flag37_rejects_unknown_carrying_relation_before_mutation(self):
        for carrying in (None,):
            with self.subTest(carrying=carrying):
                self.setUp()
                original = self.authority

                class CarryingAuthority:
                    def __call__(self, fight, actor):
                        metadata = original(fight, actor)
                        if actor.id == -7:
                            return replace(metadata, is_carrying=carrying)
                        return metadata

                    def properties(self, fight, actor):
                        return original.properties(fight, actor)

                self.handler.authority = CarryingAuthority()
                effect = deepcopy(self.effects["358000"])
                effect["native_effect_flags"] = [37]
                target = self.preview.actors[-7]
                before_position = target.position
                with self.assertRaisesRegex(ValueError, "empty carry relations"):
                    self.handler(
                        effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0))
                    )
                self.assertEqual(target.position, before_position)
                self.assertEqual(self.preview.native_effect_uid_next, 200)
                self.assertEqual(self.packets, [])

    def test_flag37_forced_carrier_preserves_registered_partner(self):
        from wakfu_server.combat_carrying import carry_registered, carrying_relations

        carrier = self.preview.actors[-7]
        carried = self.preview.actors[8]
        carrier.native_los_height = 0
        self.assertTrue(
            carry_registered(self.preview, carrier, carried, source_uid=199)
        )
        effect = deepcopy(self.effects["358000"])
        effect["native_effect_flags"] = [37]
        self.assertTrue(
            self.handler(effect, None, EffectInvocation(358000, 1, 7, -7, (4, 0, 0)))
        )
        self.assertEqual(carrier.position, (5, 0, 0))
        self.assertEqual(carried.position, carrier.position)
        self.assertTrue(carrying_relations(self.preview, carrier)["is_carrying"])

    def test_real_caster_teleport_and_swap_without_actor_fabrication(self):
        self.execute(349548, target=None, cell=(2, 2, 0))
        self.assertEqual(self.preview.actors[7].position, (2, 2, 0))
        self.execute(349546)
        self.assertEqual(self.preview.actors[7].position, (4, 0, 0))
        self.assertEqual(self.preview.actors[-7].position, (2, 2, 0))

    def test_swap_keeps_large_qk_footprint_without_invented_free_cell_gate(self):
        from wakfu_server.combat_qi_fight import current_registry

        self.preview.actors[8].position = (-1, 0, 0)
        install_synthetic_qi_occupancy(self.preview, physical_radii={-7: 1})
        target_slot = self.preview.actors[-7].native_obstacle_id
        other_slot = self.preview.actors[8].native_obstacle_id
        self.assertTrue(self.execute(349546))
        self.assertEqual(self.preview.actors[7].position, (4, 0, 0))
        self.assertEqual(self.preview.actors[-7].position, (0, 0, 0))
        qi = current_registry(self.preview).snapshot()
        self.assertIn(target_slot, qi.U(-1, 0))
        self.assertIn(other_slot, qi.U(-1, 0))

    def test_large_forced_target_uses_complete_physical_columns_and_own_qk(self):
        from wakfu_server.combat_sn_path import NativeSnColumns
        from wakfu_server.combat_qi_fight import current_registry

        original = self.authority

        class PhysicalMapAuthority:
            def __call__(self, fight, actor):
                return replace(original(fight, actor), native_instance_id=1134)

            def properties(self, fight, actor):
                return original.properties(fight, actor)

        self.handler.authority = PhysicalMapAuthority()
        self.preview.actors[-7].position = (4, 0, -1)
        self.preview.actors[-7].native_physical_position = (4, 0, -1)
        self.preview.actors[-7].native_los_height = 1
        install_synthetic_qi_occupancy(self.preview, physical_radii={-7: 1})
        # Load the exact native-exported map 1134 from the isolated published
        # protocol tree; no injected column provider or fabricated map identity.
        columns = NativeSnColumns.from_published(1134)
        self.assertEqual(columns.map_id, 1134)
        self.assertEqual(
            columns.source_sha256,
            "d3211998b492de5fdaf2d3e99f39ffd30af545eed5a8c5df8480ca561e84cb3b",
        )
        self.assertTrue(self.execute(358000))
        target = self.preview.actors[-7]
        self.assertEqual(target.position, (5, 0, -1))
        qi = current_registry(self.preview).snapshot()
        self.assertIn(target.native_obstacle_id, qi.U(6, 1))
        self.assertNotIn(target.native_obstacle_id, qi.U(3, 0))

    def test_swap_carrier_moves_registered_partner_without_releasing_it(self):
        from wakfu_server.combat_carrying import carry_registered, carrying_relations
        from wakfu_server.combat_qi_fight import current_registry

        carrier = self.preview.actors[7]
        carried = self.preview.actors[8]
        carrier.native_los_height = 0
        self.assertTrue(
            carry_registered(self.preview, carrier, carried, source_uid=199)
        )
        carried_slot = carried.native_obstacle_id
        self.assertTrue(self.execute(349546))
        self.assertEqual(carrier.position, (4, 0, 0))
        self.assertEqual(carried.position, carrier.position)
        self.assertTrue(carrying_relations(self.preview, carrier)["is_carrying"])
        self.assertFalse(current_registry(self.preview).slots[carried_slot]["indexed"])

    def test_teleport_carrier_keeps_registered_partner_and_qi_identity(self):
        from wakfu_server.combat_carrying import carry_registered, carrying_relations
        from wakfu_server.combat_qi_fight import current_registry

        carrier = self.preview.actors[7]
        carried = self.preview.actors[8]
        carrier.native_los_height = 0
        self.assertTrue(
            carry_registered(self.preview, carrier, carried, source_uid=199)
        )
        slot = carried.native_obstacle_id
        self.assertTrue(self.execute(349548, target=None, cell=(2, 2, 0)))
        self.assertEqual(carrier.position, (2, 2, 0))
        self.assertEqual(carried.position, carrier.position)
        self.assertTrue(carrying_relations(self.preview, carrier)["is_carrying"])
        self.assertFalse(current_registry(self.preview).slots[slot]["indexed"])

    def test_real_target_teleport_catalog351394(self):
        self.execute(351394, cell=(3, 3, 0))
        self.assertEqual(self.preview.actors[-7].position, (3, 3, 0))

    def test_target_teleport_without_native_actor_is_rejected_without_movement(self):
        target = self.preview.actors[-7]
        before = target.position
        for identity in (None, 900001):
            with self.subTest(identity=identity):
                self.assertFalse(self.execute(351394, target=identity, cell=(3, 3, 0)))
                self.assertEqual(target.position, before)
                self.assertEqual(self.packets, [])

    def test_factory_selection_binds_a_real_caster_actor(self):
        cast = ordinary_cast_authority(
            actors=self.authority,
            timing=NativeEffectTimingProvider(self.fixture.states),
            rng=random.Random(1),
            critical=False,
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=self.authority, cast=cast)
        factory = NativeEffectRuntimeFactory(
            effects=self.effects,
            state_catalog=self.fixture.states,
            characteristic_registry=self.fixture.registry,
            action_id=1,
            contexts=replace(
                adapter.contexts(), selected_surface=self.selected_surface
            ),
            displacement_authority=self.authority,
        )
        dispatcher, packets = factory(self.preview, {})
        enemy_position = self.preview.actors[-7].position
        result = dispatcher.execute(EffectInvocation(351394, 1, 7, None, (3, 3, 0)))
        self.assertTrue(result)
        self.assertEqual(self.preview.actors[7].position, (3, 3, 0))
        self.assertEqual(self.preview.actors[-7].position, enemy_position)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][0], 12613)

    def test_real_move_away_catalog262489(self):
        self.execute(262489, target=7, cell=(2, 0, 0))
        self.assertEqual(self.preview.actors[7].position, (-2, 0, 0))

    def test_properties_and_collision_reject_without_mutation(self):
        actor = self.preview.actors[-7]
        actor.native_fight_properties = {11}
        self.assertFalse(self.execute(358000))
        self.assertEqual(self.packets, [])
        actor.native_fight_properties = set()
        self.preview.walkable.remove((5, 0, 0))
        with self.assertRaisesRegex(ValueError, "collision"):
            self.execute(358000)
        self.assertEqual(actor.position, (4, 0, 0))
        self.assertEqual(self.preview.native_effect_uid_next, 200)

    def test_factory_real_caster_teleport_empty_cell(self):
        cast = ordinary_cast_authority(
            actors=self.authority,
            timing=NativeEffectTimingProvider(self.fixture.states),
            rng=random.Random(1),
            critical=False,
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=self.authority, cast=cast)
        factory = NativeEffectRuntimeFactory(
            effects=self.effects,
            state_catalog=self.fixture.states,
            characteristic_registry=self.fixture.registry,
            action_id=1,
            contexts=replace(
                adapter.contexts(), selected_surface=self.selected_surface
            ),
            displacement_authority=self.authority,
        )
        dispatcher, packets = factory(self.preview, {})
        dispatcher.execute(EffectInvocation(349548, 1, 7, None, (2, 2, 0)))
        self.assertEqual(self.preview.actors[7].position, (2, 2, 0))
        self.assertEqual(len(packets), 1)

    def test_later_unsupported_rollback_preserves_original_position_uid(self):
        effects = dict(self.effects)
        effects["900099"] = fixtures.definition(987654, [])
        cast = ordinary_cast_authority(
            actors=self.authority,
            timing=NativeEffectTimingProvider(self.fixture.states),
            rng=random.Random(1),
            critical=False,
        )
        adapter = NativeServerRuntimeAdapter(actor_authority=self.authority, cast=cast)
        factory = NativeEffectRuntimeFactory(
            effects=effects,
            state_catalog=self.fixture.states,
            characteristic_registry=self.fixture.registry,
            action_id=1,
            contexts=replace(
                adapter.contexts(), selected_surface=self.selected_surface
            ),
            displacement_authority=self.authority,
        )
        from importlib import import_module

        owner_catalog = import_module(
            ordinary_cast_authority.__module__.rsplit(".", 1)[0]
            + ".combat_delivery_owners"
        ).owner_catalog
        # This synthetic unknown handler has explicit actor delivery authority.
        # Keep production routing strict; the test isolates later handler rollback.
        routing = dict(bbA=True, bbB=False)
        with patch.dict(
            owner_catalog()["effects"], {"987654": routing}
        ), self.assertRaises(UnsupportedEffectExecution):
            run_effect_transaction(
                self.preview,
                [
                    EffectInvocation(349548, 1, 7, None, (2, 2, 0)),
                    EffectInvocation(900099, 1, 7, -7, (4, 0, 0)),
                ],
                lambda p: factory(p, {})[0],
            )
        self.assertEqual(self.preview.actors[7].position, (0, 0, 0))
        self.assertEqual(self.preview.native_effect_uid_next, 200)


if __name__ == "__main__":
    unittest.main()
