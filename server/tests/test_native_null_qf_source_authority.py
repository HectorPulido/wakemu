"""PV source authority is independent of target-side state-manager presence."""
from types import SimpleNamespace
import unittest


class NativeNullQfSourceAuthorityTests(unittest.TestCase):
    def fixture(self):
        from test_combat_state_handler import NativeStateHandlerTests
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            SOURCE,
            point_glyph_row,
            validate_point_prototype,
        )

        NativeStateHandlerTests.setUpClass()
        fixture = NativeStateHandlerTests()
        fixture.setUp()
        fight = fixture.fight
        definition = native_effect_areas()["910"]
        validate_point_prototype(definition, level=0)
        source = dict(
            uid=901,
            reference=910,
            cell=(2, 3, 0),
            level=0,
            policy="wakemu.unit.declared-point.v1",
            source=SOURCE,
            authority="explicit-unit-constructor",
        )
        fight.walkable.add(source["cell"])
        row = point_glyph_row(source, definition)
        fight.native_effect_areas = {901: row}
        return fixture, fight, row

    def test_real_null_qf_source_applies_state_and649_but_cannot_receive_state(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_spell_grant import (
            NativeSpellGrantHandler,
            granted_spells,
            remove_spell_grant,
        )
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_state_managers import (
            registered_source_pv,
            state_manager,
            prune_retired_state_managers,
        )
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_native_container import (
            capture_owned_state_container,
            owned_state_container,
        )

        fixture, fight, row = self.fixture()
        self.assertIsNotNone(registered_source_pv(fight, 901))
        self.assertIsNone(state_manager(fight, 901))
        self.assertNotIn("state_ledger", row)
        change = fight.apply_state(
            901,
            7,
            3442,
            20,
            uid=321,
            catalog=fixture.catalog,
            applying_effect_has_delay=False,
        )
        self.assertEqual(change.applied.caster_id, 901)
        with self.assertRaisesRegex(ValueError, "Invalid state source"):
            fight.apply_state(7, 901, 3442, 20, uid=322, catalog=fixture.catalog)
        packets = []
        handler = NativeSpellGrantHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 400,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
        )
        effect = dict(effect_class=649, parameters=[3, 0, -1, 0, 8460, 0, 1, 0])
        invocation = EffectInvocation(401983, 1, 901, 7, (0, 0, 0), state_uid=321)
        self.assertTrue(handler(effect, [], invocation))
        self.assertEqual(granted_spells(fight, 7)[8460]["uid"], 8460)
        self.assertEqual(fight.owned_stat_effects[400]["caster_id"], 901)
        capture_owned_state_container(fight, 321)
        remove_owned_hour_area(fight, 901)
        self.assertNotIn(901, fight.native_effect_areas)
        self.assertIsNotNone(registered_source_pv(fight, 901))
        self.assertIsNone(state_manager(fight, 901))
        self.assertNotIn("state_ledger", row)
        fight.actors[7].state_ledger.remove(321)
        prune_retired_state_managers(fight)
        self.assertEqual(owned_state_container(fight, 321).caster_id, 901)
        self.assertIsNotNone(registered_source_pv(fight, 901))
        remove_spell_grant(handler, 400)
        prune_retired_state_managers(fight)
        self.assertIsNone(registered_source_pv(fight, 901))
        before_packets = list(packets)
        with self.assertRaises(ValueError):
            handler(effect, [], invocation)
        self.assertEqual(packets, before_packets)

    def test_actor_and_actual_faw_sources_remain_supported_unknown_and_malformed_reject(
        self,
    ):
        from test_monster_fake_fighter_hp_integration import (
            FakeFighterHpIntegrationTests,
        )
        from wakfu_server.combat_state_managers import registered_source_pv

        _fixture, fight, row = self.fixture()
        self.assertIs(registered_source_pv(fight, 7), fight.actors[7])
        foreign = SimpleNamespace(actors={}, native_effect_areas={})
        self.assertIsNone(registered_source_pv(foreign, 901))
        for identity in (None, True, 0, 99999, 1 << 64):
            with self.subTest(identity=identity):
                self.assertIsNone(registered_source_pv(fight, identity))
        row["native_running_effect_manager"] = True
        with self.assertRaises(ValueError):
            registered_source_pv(fight, 901)
        (
            actual,
            _creator,
            _allocated,
            _packets,
        ) = FakeFighterHpIntegrationTests().create()
        self.assertIsNotNone(registered_source_pv(actual, 901))
