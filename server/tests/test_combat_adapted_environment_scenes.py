"""Unit admission/terrain regressions; these do not certify paid encounters."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_emiw_scene_policy import (
    emiw_roles,
    prepare_emiw_border,
    validate_emiw_border,
)
from wakfu_server.combat_encounter_roles import (
    EncounterRoles,
    ORDINARY_POLICY,
    role_assignment,
    roles_from_record,
)
from wakfu_server.combat_security_scene_policy import prepare_security_glyphs
from wakfu_server.combat_adapted_light_scene import prepare_adapted_light
from wakfu_server.combat_environment_participant_footprints import (
    participant_footprints,
    verified_participant_cells,
)


class AdaptedEnvironmentSceneTests(unittest.TestCase):
    def arena(self):
        cells = {(x, y, 0) for x in range(11) for y in range(11)}
        edges = {
            (a, (a[0] + dx, a[1] + dy, 0))
            for a in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (a[0] + dx, a[1] + dy, 0) in cells
        }
        border = {c for c in cells if c[0] in (0, 10) or c[1] in (0, 10)}
        return dict(
            map_id=923,
            instance_id=0,
            validated_cells=cells,
            valid_edges=edges,
            native_border_cells=border,
            native_border_policy="wakemu.compact-cardinal-perimeter-v1",
            x=0,
            y=0,
            width=11,
            height=11,
            cell_masks=[
                128 if (x, y, 0) in border else 0 for y in range(11) for x in range(11)
            ],
        )

    def character(self):
        return dict(id=1, map_id=923, instance_id=0, x=1, y=1, z=0)

    def members(self, refs):
        return [
            dict(
                id=-index - 1,
                ref=ref,
                map_id=923,
                instance_id=0,
                x=9,
                y=9 - index,
                z=0,
                hp=30000 if ref == 3518 else 4250,
                max_hp=30000 if ref == 3518 else 4250,
            )
            for index, ref in enumerate(refs)
        ]

    def catalog(self):
        return dict(
            default_actor_radius=0,
            npc_profiles={
                str(ref): dict(
                    physical_radius=0,
                    at_base_level={"1": {"maximum": 30000}},
                    curves={"1": [30000, 0.0]},
                )
                for ref in (3514, 3516, 3517, 3518, 3530, 3531)
            },
        )

    def test_emiw_fallback_is_scoped_and_published_roles_take_precedence(self):
        with patch(
            "wakfu_server.combat_encounter_roles._active_policy", return_value=None
        ):
            roles = role_assignment(923, [2560, 2563, 2559])
            self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
            self.assertEqual(roles_from_record(roles.record()), roles)
            for refs in ([2563, 2563], [2563, 4251], [2559], [3518]):
                self.assertEqual(role_assignment(923, refs).policy, ORDINARY_POLICY)
        published = EncounterRoles("published.v1", "reviewed", 923, (2563,), 0, 1)
        with patch(
            "wakfu_server.combat_encounter_roles._active_policy",
            return_value="published.v1",
        ), patch(
            "wakfu_server.combat_encounter_roles._version", return_value=published
        ):
            self.assertEqual(role_assignment(923, [2563]), published)

    def test_emiw_uses_existing_P_and_rejects_changed_scope_or_membership(self):
        arena = self.arena()
        arena["native_encounter_roles"] = emiw_roles(923, [2563]).record()
        before = deepcopy(arena)
        result = prepare_emiw_border(arena)
        self.assertEqual(arena, before)
        self.assertEqual(result["terrain_effect_id"], 553)
        self.assertEqual(result["cell_masks"], before["cell_masks"])
        receipt = result["native_emiw_border"]
        self.assertEqual(
            validate_emiw_border(
                receipt,
                map_id=923,
                role_record=arena["native_encounter_roles"],
                cells=arena["native_border_cells"],
            ),
            553,
        )
        with self.assertRaises(ValueError):
            validate_emiw_border(
                receipt,
                map_id=924,
                role_record=arena["native_encounter_roles"],
                cells=arena["native_border_cells"],
            )
        changed = deepcopy(arena)
        changed["cell_masks"][0] = 0
        with self.assertRaises(ValueError):
            prepare_emiw_border(changed)
        ordinary = self.arena()
        self.assertIs(prepare_emiw_border(ordinary), ordinary)

    def test_security_crosses_are_deterministic_disjoint_and_real_reachable_floor(self):
        for refs, expected, count in (
            ((3514,), 847, 1),
            ((3516, 3517, 3516), 850, 3),
            ((3518, 3516, 3516, 3516), 850, 3),
        ):
            with self.subTest(refs=refs):
                arena, members = self.arena(), self.members(refs)
                before = deepcopy(arena)
                result = prepare_security_glyphs(
                    self.character(), members, arena, catalog=self.catalog()
                )
                repeat = prepare_security_glyphs(
                    self.character(), members, arena, catalog=self.catalog()
                )
                self.assertEqual(arena, before)
                self.assertEqual(
                    result["native_initial_glyphs"], repeat["native_initial_glyphs"]
                )
                self.assertEqual(len(result["native_initial_glyphs"]), count)
                occupied, used = {
                    (1, 1, 0),
                    *((m["x"], m["y"], m["z"]) for m in members),
                }, set()
                for glyph in result["native_initial_glyphs"]:
                    self.assertEqual(glyph["reference"], expected)
                    x, y, z = glyph["cell"]
                    shape = {
                        (x, y, z),
                        (x + 1, y, z),
                        (x - 1, y, z),
                        (x, y + 1, z),
                        (x, y - 1, z),
                    }
                    self.assertTrue(shape <= arena["validated_cells"])
                    self.assertFalse(
                        shape & (used | occupied | arena["native_border_cells"])
                    )
                    used.update(shape)

    def test_security_does_not_fabricate_helpers_or_admit_other_phases(self):
        for refs in ((3518,), (3514, 3515), (3518, 3516), (3516,), (3514, 4251)):
            arena = self.arena()
            self.assertIs(
                prepare_security_glyphs(
                    self.character(), self.members(refs), arena, catalog=self.catalog()
                ),
                arena,
            )
        wrong_hp = self.members((3518, 3516, 3516, 3516))
        wrong_hp[0]["max_hp"] = 40000
        with self.assertRaises(ValueError):
            prepare_security_glyphs(
                self.character(), wrong_hp, self.arena(), catalog=self.catalog()
            )
        authored = dict(self.arena(), native_initial_glyphs=[{"reference": 849}])
        self.assertIs(
            prepare_security_glyphs(
                self.character(),
                self.members((3514,)),
                authored,
                catalog=self.catalog(),
            ),
            authored,
        )

    def test_pre_snapshot_footprints_reject_radius_role_and_position_substitution(self):
        catalog = self.catalog()
        catalog["npc_profiles"]["3514"]["physical_radius"] = 1
        members, arena = self.members((3514,)), self.arena()
        facts = participant_footprints(self.character(), members, catalog=catalog)
        roles = EncounterRoles(
            ORDINARY_POLICY,
            "ordinary-existing-constructor-role-policy",
            923,
            (3514,),
            0,
            1,
        )
        actors = {
            1: SimpleNamespace(
                id=1, controlled=True, team=0, position=(1, 1, 0), physical_radius=None
            ),
            -1: SimpleNamespace(
                id=-1,
                controlled=False,
                team=1,
                position=(9, 9, 0),
                physical_radius=None,
            ),
        }
        fight = SimpleNamespace(actors=actors, native_encounter_roles=roles.record())
        arena["native_environment_participant_footprints"] = facts
        cells = verified_participant_cells(fight, arena, catalog=catalog)
        self.assertIn((10, 10), cells)
        self.assertEqual(len(cells), 10)
        for mutate in (
            lambda r: r["actors"][1].update(physical_radius=0),
            lambda r: r["actors"][1].update(position=[8, 9, 0]),
            lambda r: r["actors"][1].update(reference=3516),
        ):
            changed = deepcopy(facts)
            mutate(changed)
            arena["native_environment_participant_footprints"] = changed
            with self.assertRaises(ValueError):
                verified_participant_cells(fight, arena, catalog=catalog)

    def test_initial_light_is_explicit_adaptation_with_real3355_and_full_circle(self):
        policy = dict(
            schema="native-npc-activation-v1",
            enabled_monsters={
                str(ref): dict(initial_state_triples=[61, 1, 0, 3355, 1, 0])
                for ref in (3530, 3531)
            },
        )
        arena, members = self.arena(), self.members((3530, 3531))
        before = deepcopy((arena, members, policy))
        result = prepare_adapted_light(
            self.character(),
            members,
            arena,
            catalog=self.catalog(),
            activation_policy=policy,
        )
        self.assertEqual((arena, members, policy), before)
        (glyph,) = result["native_initial_glyphs"]
        self.assertEqual(glyph["reference"], 842)
        self.assertNotIn("activation", glyph)
        self.assertIn("server-designed", result["native_initial_glyph_policy"])
        x, y, z = glyph["cell"]
        circle = {
            (x + dx, y + dy, z)
            for dx in range(-3, 4)
            for dy in range(-3, 4)
            if abs(dx) + abs(dy) <= 3
        }
        self.assertEqual(len(circle), 25)
        self.assertTrue(circle <= arena["validated_cells"])
        self.assertFalse(circle & arena["native_border_cells"])
        del policy["enabled_monsters"]["3530"]
        with self.assertRaises(ValueError):
            prepare_adapted_light(
                self.character(),
                members,
                arena,
                catalog=self.catalog(),
                activation_policy=policy,
            )
        authored = dict(arena, native_initial_glyphs=[dict(reference=841)])
        self.assertIs(
            prepare_adapted_light(
                self.character(),
                members,
                authored,
                catalog=self.catalog(),
                activation_policy=policy,
            ),
            authored,
        )
        foreign_role = dict(
            arena, native_encounter_roles={"policy": "published.custom"}
        )
        self.assertIs(
            prepare_adapted_light(
                self.character(),
                members,
                foreign_role,
                catalog=self.catalog(),
                activation_policy=policy,
            ),
            foreign_role,
        )


if __name__ == "__main__":
    unittest.main()
