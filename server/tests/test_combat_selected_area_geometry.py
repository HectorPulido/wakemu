"""Native selected Qq entities participate in eOv geometry without fighter Qf."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_state_managers import selected_native_area_entity
from wakfu_server.combat_effect_area_queries import actor_on_specific_area


class SelectedAreaGeometryTests(unittest.TestCase):
    def test_eOv_area_membership_expands_using_signed_actor_radius(self):
        actor = SimpleNamespace(id=7, position=(2, 3, 0), physical_radius=1, team=1)
        area = dict(
            uid=71,
            reference=1836,
            cell=(3, 4, 0),
            owner_id=-7,
            native_hour_contract=True,
            native_area_contract="faZ",
        )
        fight = SimpleNamespace(
            actors={7: actor},
            native_effect_areas={71: area},
            native_retired_area_managers={},
        )

        # Qq.a(PV,x,y,z) first checks the center, then the complete square
        # expansion from -radius through +radius on both axes.
        self.assertTrue(actor_on_specific_area(fight, actor_id=7, reference=1836))
        area["cell"] = (4, 5, 0)
        self.assertFalse(actor_on_specific_area(fight, actor_id=7, reference=1836))

        actor.physical_radius = -1
        area["cell"] = (2, 3, 0)
        self.assertTrue(actor_on_specific_area(fight, actor_id=7, reference=1836))
        area["cell"] = (3, 3, 0)
        self.assertFalse(actor_on_specific_area(fight, actor_id=7, reference=1836))

    def test_selected_area_geometry_respects_actual_npc_owner_and_team(self):
        for target_owner, affiliation, own, team in (
            (-7, 1, True, True),
            (-8, 1, False, True),
            (-9, 2, False, False),
        ):
            with self.subTest(owner=target_owner):
                selected = dict(
                    uid=70, reference=1855, owner_id=-7, native_area_contract="faY"
                )
                other = dict(
                    uid=71,
                    reference=1836,
                    owner_id=target_owner,
                    native_area_contract="faY",
                )
                fight = SimpleNamespace(
                    actors={
                        -7: SimpleNamespace(id=-7, team=1),
                        -8: SimpleNamespace(id=-8, team=1),
                        -9: SimpleNamespace(id=-9, team=2),
                    },
                    native_effect_areas={70: selected, 71: other},
                    native_retired_area_managers={},
                )
                pv = SimpleNamespace(position=(2, 3, 0), native_fight_affiliation=1)
                with patch(
                    "wakfu_server.combat_state_managers.registered_area_pv",
                    return_value=pv,
                ), patch(
                    "wakfu_server.combat_effect_area_geometry.contains_area_cell",
                    side_effect=lambda row, position: row["uid"] == 71
                    and position == (2, 3, 0),
                ):
                    entity = selected_native_area_entity(fight, 70)
                    self.assertEqual(entity.physical_radius, 0)
                    self.assertFalse(hasattr(entity, "state_ledger"))
                    self.assertFalse(hasattr(entity, "hp"))
                    for ownership, expected in (
                        ("all", True),
                        ("own", own),
                        ("team", team),
                    ):
                        self.assertEqual(
                            actor_on_specific_area(
                                fight, actor_id=70, reference=1836, ownership=ownership
                            ),
                            expected,
                        )
                    del fight.native_effect_areas[71]
                    self.assertFalse(
                        actor_on_specific_area(fight, actor_id=70, reference=1836)
                    )

    def test_verified_doll_and_npc_summon_controller_owns_the_area(self):
        for controller, selected in ((7, 88), (-7, 89), (-7, -7), (7, 7)):
            with self.subTest(controller=controller, selected=selected):
                actor = SimpleNamespace(
                    id=selected, position=(2, 3, 0), physical_radius=0, team=1
                )
                row = dict(
                    uid=70,
                    reference=1836,
                    owner_id=controller,
                    native_area_contract="faY",
                )
                fight = SimpleNamespace(
                    actors={selected: actor},
                    native_effect_areas={70: row},
                    native_retired_area_managers={},
                )
                with patch(
                    "wakfu_server.combat_effect_area_geometry.contains_area_cell",
                    return_value=True,
                ):
                    self.assertTrue(
                        actor_on_specific_area(
                            fight,
                            actor_id=selected,
                            reference=1836,
                            ownership="own",
                            selected_controller_id=controller,
                        )
                    )
                    self.assertFalse(
                        actor_on_specific_area(
                            fight,
                            actor_id=selected,
                            reference=1836,
                            ownership="own",
                            selected_controller_id=controller + 100,
                        )
                    )
                    if selected == controller:
                        self.assertTrue(
                            actor_on_specific_area(
                                fight,
                                actor_id=selected,
                                reference=1836,
                                ownership="own",
                            )
                        )

    def test_verified_recursive_roots_cover_npc_summon_created_areas(self):
        from wakfu_server.combat_state_managers import verified_native_owner_root

        actors = {
            uid: SimpleNamespace(id=uid, position=(2, 3, 0), physical_radius=0, team=1)
            for uid in (-7, -8, 88, 89)
        }
        controllers = {-7: -7, -8: -8, 88: -7, 89: -8}
        selected = dict(uid=70, reference=1855, owner_id=88, native_area_contract="faY")
        candidate = dict(
            uid=71, reference=1836, owner_id=88, native_area_contract="faY"
        )
        fight = SimpleNamespace(
            actors=actors,
            native_effect_areas={70: selected, 71: candidate},
            native_retired_area_managers={},
        )
        authority = lambda actor: SimpleNamespace(
            native_controller_id=controllers[actor.id]
        )
        root = lambda uid: verified_native_owner_root(fight, uid, authority)
        pv = SimpleNamespace(position=(2, 3, 0), native_fight_affiliation=1)
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv", return_value=pv
        ), patch(
            "wakfu_server.combat_effect_area_geometry.contains_area_cell",
            return_value=True,
        ):
            self.assertEqual(root(70), -7)
            for selected_id in (70, 88, -7):
                self.assertTrue(
                    actor_on_specific_area(
                        fight,
                        actor_id=selected_id,
                        reference=1836,
                        ownership="own",
                        owner_root_query=root,
                    )
                )
            candidate["owner_id"] = 89
            self.assertFalse(
                actor_on_specific_area(
                    fight,
                    actor_id=70,
                    reference=1836,
                    ownership="own",
                    owner_root_query=root,
                )
            )
            controllers[88] = 89
            controllers[89] = 88
            with self.assertRaisesRegex(ValueError, "recursive native owner"):
                root(88)
            controllers[88] = None
            with self.assertRaisesRegex(ValueError, "Missing verified"):
                root(88)
        with self.assertRaisesRegex(ValueError, "Unknown native owner PV"):
            root(999)

    def test_unknown_selected_area_rejects_and_null_is_false(self):
        fight = SimpleNamespace(
            actors={}, native_effect_areas={}, native_retired_area_managers={}
        )
        self.assertFalse(actor_on_specific_area(fight, actor_id=None, reference=1836))
        with self.assertRaisesRegex(ValueError, "Missing native selected area actor"):
            actor_on_specific_area(fight, actor_id=70, reference=1836)
