"""Exercise area lesson through actual native player-spell dispatch and QI."""
import random
import struct
import unittest
from copy import deepcopy

import test_combat_spell_transaction as fixtures
from wakfu_server.achievements import rii_area_contract
from wakfu_server.achievements.lesson_area import formation
from wakfu_server.combat_actor_snapshot import build_npc_snapshot
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
    current_registry,
)
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_state import Fight, Actor
from wakfu_server.rii_lesson_spell_catalog import catalog
from wakfu_server.spells import encode_deck


class AreaNativeCastTests(unittest.TestCase):
    def test_four_native_area_casts_move_qi_and_finish(self):
        (
            character,
            monster,
            original,
        ) = fixtures.SpellTransactionTests().native_server_fixture(
            3, 15, native_qi=True, target_ref=5466, target_level=1, target_distance=2
        )
        caster = deepcopy(original.actors[7])
        prototype = original.actors[-7]
        layout = formation(
            original.walkable,
            (),
            anchor=tuple(caster.position),
            phase=0,
            effects=catalog()["effects"],
        )
        self.assertIsNotNone(layout)
        _, cells = layout
        monsters, targets, snapshots = {}, [], {}
        for index, cell in enumerate(cells):
            actor = Actor(
                -7 - index,
                1,
                cell,
                prototype.hp,
                prototype.ap,
                prototype.mp,
                prototype.initiative,
                1,
                max_hp=prototype.max_hp,
            )
            actor.native_obstacle_id = index + 1
            targets.append(actor)
            monsters[actor.id] = dict(monster, id=actor.id)
            snapshots[actor.id] = build_npc_snapshot(
                monsters[actor.id],
                actor,
                wp_current=0,
                wp_maximum=0,
                running_effects=(),
            )
        caster.native_obstacle_id = 0
        fight = Fight(
            78,
            [caster, *targets],
            original.walkable,
            {0: {caster.position}, 1: {actor.position for actor in targets}},
            original.edges,
        )
        fight.native_qi_snapshot = deepcopy(original.native_qi_snapshot)
        fight.native_qi_surface_provenance = deepcopy(
            original.native_qi_surface_provenance
        )
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        registry = prepare_fresh_actor_slots(
            fight,
            physical_radii={
                caster.id: caster.physical_radius,
                **{actor.id: snapshots[actor.id].physical_radius for actor in targets},
            },
        )
        install_fresh_actor_slots(fight, registry)
        fight.ready(3)
        # Reinstall NPC metadata for each distinct actor identity.
        for target in targets:
            snapshots[target.id].install(target)
        fight.native_effect_uid_next = 1
        fight.native_obstacle_cells = frozenset()
        fight.rii_area_lesson_contract = {
            "owner": 7,
            "targets": [a.id for a in targets],
            "hits": 0,
            "actions": [],
        }
        rii_area_contract.initialize(fight, [], action_id=1)
        effects = catalog()["effects"]
        spells = (7970, 7970, 7969, 7971)
        for index, spell in enumerate(spells, 1):
            current = {tuple(fight.actors[target.id].position) for target in targets}
            from wakfu_server.combat_effect_targets import area_offsets
            from wakfu_server.achievements.lesson_area import EFFECT_SEQUENCE

            offsets = set(area_offsets(effects[str(EFFECT_SEQUENCE[index - 1])]))
            centers = [
                cell
                for cell in fight.walkable
                if 2
                <= (
                    abs(cell[0] - caster.position[0])
                    + abs(cell[1] - caster.position[1])
                )
                <= 16
                and all(
                    (x - cell[0], y - cell[1]) in offsets and z == cell[2]
                    for x, y, z in current
                )
            ]
            self.assertTrue(centers, f"Missing native target center at stage {index}")
            center = min(
                centers,
                key=lambda c: abs(c[0] - caster.position[0])
                + abs(c[1] - caster.position[1]),
            )
            result = prepare_server_spell(
                struct.pack(">qqiih", 7, spell, *center),
                character,
                monsters,
                fight,
                3,
                encode_deck([]),
                action_id=index + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(1),
            )
            fight = result.fight
            self.assertEqual(fight.rii_area_lesson_contract["hits"], index)
            self.assertEqual(
                [fight.actors[t.id].hp for t in targets], [100 - index * 25] * 4
            )
            if index < 4:
                current_registry(fight)
                self.assertFalse(any(op == 13624 for op, _ in result.packets))
        self.assertEqual(fight.phase, "finished")


if __name__ == "__main__":
    unittest.main()
