import unittest
from types import SimpleNamespace

from wakfu_server.combat_battleground_border import (
    POLICY,
    ensure_battleground_border,
    install_battleground_border,
)
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_effect_area_targets import area_targets
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_state_managers import registered_area_pv


class BattlegroundBorderTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(id=7, position=(0, 0, 3), physical_radius=0, team=0)
        fight = SimpleNamespace(
            actors={7: actor},
            walkable={(0, 0, 3), (1, 0, 3)},
            native_effect_areas={},
            native_retained_records={},
            native_qi_snapshot=dict(
                x=0, y=0, width=2, height=1, cell_masks=[128 | 4, 5]
            ),
            phase="active",
            current=actor,
        )
        initialize_global_pv_collections(fight, (7,))
        arena = dict(
            native_border_policy=POLICY, native_border_cells={(0, 0, 3)}, min_z=3
        )
        return fight, arena

    def test_native_null_owner_area_geometry_and_identity(self):
        fight, arena = self.fixture()
        row = install_battleground_border(fight, arena, reference=46, identity=-100)
        self.assertIsNone(row["owner_id"])
        self.assertEqual((row["level"], row["direction"]), (0, -1))
        self.assertEqual(area_targets(fight)[0].id, -100)
        self.assertEqual(area_targets(fight)[0].team, -1)
        self.assertIsNone(registered_area_pv(fight, -100).state_ledger)
        self.assertEqual(row["native_cells_xy"], ((0, 0),))

    def test_original_entry_masks_deliver_area_caster_and_container(self):
        fight, arena = self.fixture()
        install_battleground_border(fight, arena, reference=46, identity=-100)
        calls = []
        retention = SimpleNamespace(synchronize=lambda: None)
        dispatcher = SimpleNamespace(native_retention=retention, execute=calls.append)
        events = NativeAreaEventRuntime(
            fight, dispatcher, definitions=native_effect_areas()
        )
        self.assertEqual(events.turn_start(7), (True,))
        invocation = calls[0]
        self.assertEqual((invocation.reference, invocation.level), (152027, 0))
        self.assertEqual((invocation.caster_id, invocation.target_id), (-100, 7))
        self.assertIs(invocation.native_explicit_target, True)
        self.assertEqual(invocation.native_retained_container["id"], -100)
        self.assertEqual(invocation.native_retained_container["type"], 3)
        fight.actors[7].position = (1, 0, 3)
        self.assertEqual(events.turn_start(7), ())
        self.assertEqual(len(calls), 1)

    def test_unknown_policy_or_mismatched_qi_rejected_without_registration(self):
        for key, value in (
            ("native_border_policy", "unknown"),
            ("native_border_cells", {(1, 0, 3)}),
        ):
            fight, arena = self.fixture()
            arena[key] = value
            with self.assertRaises(ValueError):
                install_battleground_border(fight, arena, reference=46, identity=-100)
            self.assertEqual(fight.native_effect_areas, {})

    def test_repeated_runtime_construction_preserves_existing_clone(self):
        fight, arena = self.fixture()
        fight.native_border_constructor = dict(reference=46, identity=-100, arena=arena)
        ensure_battleground_border(fight)
        row = fight.native_effect_areas[-100]
        row["child_effect_uids"] = {"7": [12]}
        ensure_battleground_border(fight)
        self.assertIs(fight.native_effect_areas[-100], row)
        self.assertEqual(row["child_effect_uids"], {"7": [12]})

    def test_original_border_group_executes_mp_loss_and_once_marker(self):
        from dataclasses import replace
        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.spell_audit import states_catalog
        from wakfu_server.combat_effect_area_catalog import area_effect_catalog
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents

        # Reuse the isolated runtime's actual actor/stat ledger, without loading
        # or compiling the full class catalog. Only original border definitions
        # are supplied; the factory and handlers remain production code.
        fixture = NativeRuntimeFactoryTests()
        fixture.spells = area_effect_catalog()
        fixture.effects = dict(fixture.spells["effects"])
        fixture.states = states_catalog()
        fixture.registry = characteristic_registry()
        fixture.setUp()
        fight = fixture.fight
        fight.actors = {7: fight.actors[7]}
        fight.order = [7]
        actor = fight.actors[7]
        fight.turn_index = 0
        actor.effect_stats[86] = 0
        actor.effect_minima[86] = 0
        actor.effect_maxima[86] = 1000
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=2, height=2, cell_masks=[128, 0, 0, 256]
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        arena = dict(
            native_border_policy=POLICY, native_border_cells={(0, 0, 0)}, min_z=0
        )
        install_battleground_border(fight, arena, reference=46, identity=-100)
        timing = NativeEffectTimingProvider(fixture.states)

        def condition(preview, plan, effect, invocation):
            rows = native_retained_condition_effects(preview, invocation.target_id)
            return ConditionContext(
                {
                    "caster": ConditionActor(actor_id=-100, is_native_fighter=False),
                    "target": ConditionActor(
                        actor_id=invocation.target_id,
                        characteristics={
                            "WILLPOWER": preview.actors[
                                invocation.target_id
                            ].effect_stats[86]
                        },
                        retained_effect_ids=frozenset(row[0] for row in rows),
                    ),
                }
            )

        actor_authority = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15, level=1)},
            monsters={},
            decks={7: []},
            excluded_decks={7: []},
        )
        adapter = SimpleNamespace(actor_authority=actor_authority)

        def healing_events(preview, plan, replay, retention):
            return OrdinaryHealingEvents(
                adapter=adapter,
                preview=preview,
                plan=plan,
                replay=replay,
                retention=retention,
            )

        contexts = replace(
            fixture.contexts,
            condition=condition,
            stat=timing.stat,
            healing_events=healing_events,
        )
        property_actor_ids = []

        def properties(preview, target):
            property_actor_ids.append(target.id)
            return frozenset()

        class TestSummonAuthority(RegisteredSummonAuthority):
            def __init__(self):
                super().__init__(object())

            def properties(self, preview, target):
                return properties(preview, target)

        factory = NativeEffectRuntimeFactory(
            effects=fixture.effects,
            state_catalog=fixture.states,
            characteristic_registry=fixture.registry,
            action_id=1,
            contexts=contexts,
            summon_authority=TestSummonAuthority(),
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        self.assertEqual(actor.mp, 3)
        with fight.effect_resolution():
            dispatcher.native_area_events.event(10000, actor.id)
        self.assertEqual(actor.mp, 2)  # no actor caster means native willpower is zero.
        rows = native_retained_condition_effects(fight, actor.id)
        self.assertIn(152028, {row[0] for row in rows})
        self.assertIn(5227, {entry.reference for entry in actor.state_ledger.entries})
        self.assertEqual(set(property_actor_ids), {actor.id})
        with fight.effect_resolution():
            dispatcher.native_area_events.event(10000, actor.id)
        self.assertEqual(actor.mp, 2)


if __name__ == "__main__":
    unittest.main()
