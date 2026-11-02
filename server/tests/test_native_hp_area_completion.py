"""Compound native HP-area callback, completion and deferred-retirement checks."""
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.combat_effect_area import native_effect_areas, remove_owned_hour_area
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_fake_fighter_resources import update_fake_fighter_hp
from wakfu_server.combat_wall_area import update_wall_hp
from test_combat_fake_fighter_area import NativeFakeFighterAreaTests


class NativeHpAreaDeathTests(unittest.TestCase):
    def fixture(self):
        fight, creator, allocated, packets = NativeFakeFighterAreaTests().create()
        creator.fake_fighter_hp_enabled = True
        creator(
            {"effect_class": 339},
            {"parameters": [566, 141]},
            EffectInvocation(101928, 141, 7, None, (2, 3, 0)),
        )
        fake = next(iter(fight.native_effect_areas.values()))
        creator(
            {"effect_class": 339},
            {"parameters": [196, 1]},
            EffectInvocation(101929, 1, 7, None, (1, 1, 0)),
        )
        wall = next(
            row for row in fight.native_effect_areas.values() if row is not fake
        )
        for row in (fake, wall):
            row.setdefault("native_qq_bhi", False)
            row.setdefault("native_qq_guard_source", "Qq.constructor")
        definitions = {
            str(row["reference"]): native_effect_areas()[str(row["reference"])]
            for row in (fake, wall)
        }
        events = NativeAreaEventRuntime(
            fight, SimpleNamespace(), definitions=definitions
        )
        return fight, fake, wall, events

    @contextmanager
    def selected(self, fight, identities):
        # The paid probe supplies the actual Qf/PL selected-PV implementation.
        self.assertTrue(all(uid in fight.native_effect_areas for uid in identities))
        yield

    def test_mixed_fake_and_wall_have_distinct_once_only_events_and_deferred_removal(
        self,
    ):
        fight, fake, wall, events = self.fixture()
        calls = []
        removed = []
        update_fake_fighter_hp(fake, events._definition(fake), 0)
        update_wall_hp(wall, wall["native_wall_constructor"], 0)

        def own_death():
            self.assertFalse(fake["native_qq_bhi"])
            self.assertIn(fake["uid"], fight.native_effect_areas)
            self.assertFalse(
                events.fake_fighter_death(fake, 7, death_delivery=own_death)
            )
            calls.append((fake["uid"], 1033))

        def area_mask(row, definition, source, event):
            self.assertFalse(row["native_qq_bhi"])
            calls.append((row["uid"], event))

        callbacks = SimpleNamespace(removed=lambda row: removed.append(row["uid"]))
        with patch(
            "wakfu_server.combat_state_managers.selected_area_pv_scope", self.selected
        ), patch.object(events, "_deliver_event", side_effect=area_mask), patch.object(
            events,
            "remove_parent",
            side_effect=lambda row: remove_owned_hour_area(
                fight, row["uid"], callbacks=callbacks
            ),
        ):
            with events.wall_retirement_scope():
                self.assertTrue(
                    events.fake_fighter_death(fake, 7, death_delivery=own_death)
                )
                self.assertTrue(events.wall_death(wall, 7))
                self.assertFalse(
                    events.fake_fighter_death(fake, 7, death_delivery=own_death)
                )
                self.assertFalse(events.wall_death(wall, 7))
                self.assertTrue(fake["native_qq_bhi"])
                self.assertTrue(wall["native_qq_bhi"])
                from wakfu_server.combat_area_damage_guard import (
                    completed_wall_without_ko_pa,
                )

                self.assertTrue(completed_wall_without_ko_pa(fight, fake["uid"]))
                self.assertTrue(completed_wall_without_ko_pa(fight, wall["uid"]))
                self.assertEqual(len(fight.native_effect_areas), 2)
            self.assertFalse(fight.native_effect_areas)
        self.assertEqual(
            calls, [(fake["uid"], 1033), (fake["uid"], 10014), (wall["uid"], 10014)]
        )
        self.assertCountEqual(removed, [fake["uid"], wall["uid"]])

    def test_living_or_absent_hp_and_unknown_killer_do_not_emit_death(self):
        fight, fake, wall, events = self.fixture()
        calls = []
        self.assertFalse(
            events.fake_fighter_death(
                fake, 7, death_delivery=lambda: calls.append(1033)
            )
        )
        with self.assertRaises(ValueError):
            events.fake_fighter_death(
                fake, 999, death_delivery=lambda: calls.append(1033)
            )
        fake.pop("native_faw_hp_constructor")
        with self.assertRaises(ValueError):
            events.fake_fighter_death(
                fake, 7, death_delivery=lambda: calls.append(1033)
            )
        self.assertFalse(calls)

    def test_callback_failure_preserves_uncompleted_pv_and_releases_reentry_guard(self):
        fight, fake, wall, events = self.fixture()
        update_fake_fighter_hp(fake, events._definition(fake), 0)

        def fail():
            raise ValueError("native callback failed")

        with patch(
            "wakfu_server.combat_state_managers.selected_area_pv_scope", self.selected
        ), patch.object(events, "remove_parent") as remove:
            with self.assertRaisesRegex(ValueError, "callback failed"):
                with events.wall_retirement_scope():
                    events.fake_fighter_death(fake, 7, death_delivery=fail)
            self.assertFalse(fake["native_qq_bhi"])
            self.assertFalse(events._dying_area_uids)
            self.assertFalse(events._dead_wall_retirements)
            remove.assert_not_called()
            self.assertIn(fake["uid"], fight.native_effect_areas)

    def test_dead_owner_does_not_replace_actual_lethal_source_or_skip_native_callback_guard(
        self,
    ):
        fight, fake, wall, events = self.fixture()
        fight.actors[7].hp = 0
        fight.actors[8] = SimpleNamespace(id=8, hp=100)
        update_fake_fighter_hp(fake, events._definition(fake), 0)
        seen = []

        def delivery():
            # Producer delivers once; existing replay owns dead-caster eligibility.
            self.assertEqual(fake["owner_id"], 7)
            self.assertEqual(fight.actors[7].hp, 0)
            seen.append(1033)

        def mask(row, definition, source, event):
            self.assertIs(source, fight.actors[8])

        with patch(
            "wakfu_server.combat_state_managers.selected_area_pv_scope", self.selected
        ), patch.object(events, "_deliver_event", side_effect=mask):
            self.assertTrue(events.fake_fighter_death(fake, 8, death_delivery=delivery))
        self.assertEqual(seen, [1033])
        self.assertTrue(fake["native_qq_bhi"])

    def test_dispel_selects_registered_and_retained_area_qf_but_rejects_unknown_pv(
        self,
    ):
        from wakfu_server.combat_dispel import NativeDispelHandler
        from wakfu_server.combat_retained_effects import RetainedEffect
        from wakfu_server.combat_state_managers import selected_area_pv_scope

        fight, fake, wall, events = self.fixture()
        removed = []
        entry = RetainedEffect(999, fake["uid"], 400, 123, manager_id=fake["uid"])
        view = SimpleNamespace(fight=fight, entries=(entry,))
        removal = SimpleNamespace(
            view=view, remove=lambda values: removed.extend(values)
        )
        handler = NativeDispelHandler(
            view_provider=lambda: view, removal_provider=lambda actual: removal
        )
        invocation = EffectInvocation(421, 1, 7, fake["uid"], tuple(fake["cell"]))
        handler._apply({"parameters": [123]}, invocation)
        self.assertEqual(removed, [999])
        removed.clear()
        with selected_area_pv_scope(fight, (fake["uid"],)):
            remove_owned_hour_area(
                fight, fake["uid"], callbacks=SimpleNamespace(removed=lambda row: None)
            )
            self.assertNotIn(fake["uid"], fight.native_effect_areas)
            handler._apply({"parameters": [123]}, invocation)
        self.assertEqual(removed, [999])
        with self.assertRaisesRegex(ValueError, "Missing native dispel target"):
            handler._apply(
                {"parameters": [123]}, EffectInvocation(421, 1, 7, 123456, (0, 0, 0))
            )


class NativeNonHpAreaExclusionTests(unittest.TestCase):
    def test_original_no_hp_fake_fighter_is_not_an_hp_death_target(self):
        from wakfu_server.combat_damage_handler import _wall_target
        from wakfu_server.combat_area_damage_guard import (
            area_damage_has_no_resources,
            completed_wall_without_ko_pa,
        )

        fixture = NativeFakeFighterAreaTests()
        fight, creator, _allocated, _packets = fixture.create()
        fixture.invoke(creator)
        row = next(iter(fight.native_effect_areas.values()))
        self.assertNotIn("native_faw_hp_constructor", row)
        self.assertIsNone(_wall_target(fight, row["uid"]))
        self.assertTrue(area_damage_has_no_resources(fight, row["uid"]))
        self.assertFalse(completed_wall_without_ko_pa(fight, row["uid"]))

    def test_structural_damage_only_characteristic20_never_acquires_hp_authority(self):
        from copy import deepcopy
        from wakfu_server.combat_damage_handler import _wall_target
        from wakfu_server.combat_area_damage_guard import (
            area_damage_has_no_resources,
            completed_wall_without_ko_pa,
        )
        from wakfu_server.combat_fake_fighter import fake_fighter_constructor
        from wakfu_server.combat_fake_fighter_owner_copy import install

        fixture = NativeFakeFighterAreaTests()
        fight, creator, _allocated, _packets = fixture.create()
        fixture.invoke(creator)
        row = next(iter(fight.native_effect_areas.values()))
        # A structural constructor fixture, not a claim about original1035.
        definition = deepcopy(native_effect_areas()[str(row["reference"])])
        definition["raw_bdh"] = [-1, -1, 0, 0, 1, 1, 1, 1, 6, 2]
        row["native_faw_constructor"] = fake_fighter_constructor(
            definition, allow_hp=True
        )
        install(row, definition, {21: 17})
        self.assertEqual(row["native_faw_constructor"]["characteristic_ids"], (20,))
        self.assertFalse(any(key.startswith("native_faw_hp_") for key in row))
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value={str(row["reference"]): definition},
        ):
            self.assertIsNone(_wall_target(fight, row["uid"]))
            self.assertTrue(area_damage_has_no_resources(fight, row["uid"]))
            self.assertFalse(completed_wall_without_ko_pa(fight, row["uid"]))

    def test_structural_ko_characteristic14_prevents_completed_hp_suppression(self):
        from wakfu_server.combat_area_damage_guard import completed_wall_without_ko_pa

        fight, fake, _wall, _events = NativeHpAreaDeathTests().fixture()
        # The supported native HP constructor is independently validated in
        # the integration cases. Isolate the optional KO-resource decision.
        with patch(
            "wakfu_server.combat_fake_fighter.verified_fake_fighter",
            return_value={"characteristic_ids": (1, 14)},
        ), patch(
            "wakfu_server.combat_area_authority.area_guards",
            side_effect=AssertionError("KO PA must preserve normal handling"),
        ):
            self.assertFalse(completed_wall_without_ko_pa(fight, fake["uid"]))
