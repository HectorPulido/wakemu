"""Selected QI occupancy, independent of retained historical actor positions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_obstacle_condition import _native_is_obstacle, is_obstacle
from wakfu_server.combat_qi_registry import NativeQIRegistry


class NativeObstacleMembershipTests(unittest.TestCase):
    def test_current_slot_removal_reuse_overlap_area_and_custom_fallback(self):
        registry = NativeQIRegistry(
            dict(x=0, y=0, width=4, height=4, cell_masks=[0] * 16),
            [None] * 127,
            byte_topology={},
        )
        viewer = SimpleNamespace(
            id=1, team=0, position=(0, 0, 0), physical_radius=0, props=set()
        )
        old = SimpleNamespace(
            id=2, team=1, position=(2, 2, 0), physical_radius=0, props=set(), hp=0
        )
        new = SimpleNamespace(
            id=3, team=1, position=(2, 2, 0), physical_radius=0, props={5}
        )
        fight = SimpleNamespace(
            actors={1: viewer, 2: old, 3: new}, native_effect_areas={}
        )
        calls = []

        class Authority:
            def __call__(self, fight, actor):
                calls.append(actor.id)
                return SimpleNamespace(targeting={"is_eHH": True})

            def properties(self, fight, actor):
                return actor.props

        authority = Authority()

        def row(kind, uid, radius=0):
            return dict(
                identity=(kind, uid),
                indexed=False,
                movement_blocking=False,
                position=(2, 2),
                radius=radius,
            )

        with patch(
            "wakfu_server.combat_qi_fight.current_registry", return_value=registry
        ) as lookup:
            query = lambda: _native_is_obstacle(fight, old, viewer, authority)
            slot = registry.register(row("actor", old.id))
            self.assertTrue(query())  # HP zero / OFF_PLAY still registered.
            registry.remove(slot, ("actor", old.id))
            self.assertFalse(query())  # Retained historical actor is not a QK.
            self.assertEqual(registry.register(row("actor", new.id)), slot)
            calls.clear()
            self.assertFalse(query())  # Reused slot belongs to new invisible actor.
            self.assertNotIn(old.id, calls)
            other_slot = registry.register(row("actor", old.id))
            first = registry.slots[registry.ordered_U(2, 2)[0]]["identity"][1]
            self.assertEqual(
                query(), first == old.id
            )  # Actual Trove first, not any overlap.
            registry.remove(other_slot, ("actor", old.id))
            registry.remove(slot, ("actor", new.id))
            fight.native_effect_areas[90] = dict(
                native_area_contract="faW",
                native_faw_constructor={"movement_blocking": True},
            )
            registry.register(row("effect_area", 90, 1))
            self.assertTrue(query())
            old.position = (1, 1, 0)
            self.assertTrue(query())  # Inclusive registered area footprint.
            old.position = (-1, -1, 0)
            self.assertFalse(query())  # Native bounds, no terrain reconstruction.
            self.assertEqual(lookup.call_count, 7)

        from test_combat_obstacle_condition import ObstacleConditionTests

        legacy, custom = ObstacleConditionTests().fixture()
        legacy.actors[8].props = frozenset()
        legacy.actors[8].hp = 0
        self.assertTrue(
            is_obstacle(legacy, selected_id=8, viewer_id=7, actor_authority=custom)
        )

    def test_public_native_authority_adopts_current_qi(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            1, 100, native_qi=True
        )
        _, adapter = server_runtime(
            character,
            {monster["id"]: monster},
            encode_deck(),
            action_id=1,
            critical=False,
        )
        from wakfu_server.combat_qi_fight import current_registry

        with patch(
            "wakfu_server.combat_qi_fight.current_registry", wraps=current_registry
        ) as read:
            self.assertTrue(
                is_obstacle(
                    fight,
                    selected_id=character["id"],
                    viewer_id=character["id"],
                    actor_authority=adapter.actor_authority,
                )
            )
        self.assertEqual(read.call_count, 1)
