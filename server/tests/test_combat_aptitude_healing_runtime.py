"""Owned aptitude 27 through the actual allied healing spell runner."""
import os
import random
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AptitudeHealingRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server import combat_retained_runtime

        cls.active_retained_metadata = (
            combat_retained_runtime.native_retained_metadata()
        )

    def fixture(
        self,
        *,
        active_spells=(779,),
        passive_spells=(),
        injury=60,
        level=60,
        caster_breed=7,
        caster_aptitudes=((27, 2),),
        enemy_position=(-5, -7, -1),
        third_player_position=(-8, -6, -1),
        second_player_position=(-7, -7, -1),
        compact_arena=True,
        initialization_seed=0,
    ):
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server import combat_retained_runtime
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum
        from wakfu_server.spells import encode_deck
        from tests.test_aptitude_catalog_coverage import aptitude_sheet
        from wakfu_server.wire import proto_field

        positions = {
            7: (-8, -7, -1),
            8: tuple(second_player_position),
            9: tuple(third_player_position),
            -7: enemy_position,
        }
        arena = local_arena(
            1134,
            78,
            positions[7],
            positions[-7],
            compact=compact_arena,
            relocate_monsters=compact_arena,
        )
        characters = {
            7: effective_character(
                dict(
                    id=7,
                    account_id=3,
                    map_id=1134,
                    breed=caster_breed,
                    level=level,
                    hp=maximum(caster_breed, level) - injury,
                    builds={
                        0: {
                            "sheet": proto_field(24, 0xFFFFFFFF).hex(),
                            "aptitudes": aptitude_sheet(caster_aptitudes).hex(),
                        }
                    },
                    inventory_items=[],
                )
            ),
            8: effective_character(
                dict(
                    id=8,
                    account_id=4,
                    map_id=1134,
                    breed=8,
                    level=level,
                    hp=maximum(8, level) - injury,
                    builds={
                        0: {
                            "sheet": proto_field(24, 0xFFFFFFFF).hex(),
                            "aptitudes": aptitude_sheet([(27, 2)]).hex(),
                        }
                    },
                    inventory_items=[],
                )
            ),
            9: effective_character(
                dict(
                    id=9,
                    account_id=5,
                    map_id=1134,
                    breed=8,
                    level=level,
                    hp=maximum(8, level) - injury,
                    builds={},
                    inventory_items=[],
                )
            ),
        }
        actors = [
            Actor(
                identity,
                0,
                positions[identity],
                characters[identity]["hp"],
                6,
                3,
                initiative,
                level,
                characters[identity]["account_id"],
                True,
                max_hp=characters[identity]["max_hp"],
            )
            for identity, initiative in ((7, 30), (8, 20), (9, 10))
        ]
        actors.append(Actor(-7, 1, positions[-7], 1000, 6, 3, 1, 1))
        fight = Fight(
            78,
            actors,
            arena["validated_cells"],
            {0: {positions[7], positions[8], positions[9]}, 1: {positions[-7]}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        initialize_global_pv_collections(fight, (7, 8, 9, -7))
        freeze_terrain(fight)
        fight.native_obstacle_cells = frozenset()
        monster = dict(id=-7, ref=5525, map_id=1134)
        initialize_fight_snapshots(
            fight,
            characters=characters,
            monsters={-7: monster},
            wp_resources={7: (6, 6), 8: (6, 6), 9: (6, 6), -7: (0, 0)},
            running_effects={7: (), 8: (), 9: (), -7: ()},
            initial_effect_uid=1,
        )
        for owner in (3, 4, 5):
            fight.ready(owner)

        decks = {
            7: encode_deck(active_spells, passive_spells),
            8: encode_deck(),
            9: encode_deck(),
        }
        with patch.object(
            combat_retained_runtime,
            "native_retained_metadata",
            return_value=self.active_retained_metadata,
        ):
            for action_id, identity in enumerate((7, 8, 9), 1):
                fight, _ = prepare_server_initialization(
                    characters[identity],
                    {-7: monster},
                    fight,
                    characters[identity]["account_id"],
                    decks[identity],
                    action_id=action_id,
                    rng=random.Random(initialization_seed),
                    fight_start=(identity == 9),
                    player_characters=characters,
                    deck_blobs=decks,
                )
        return fight, characters, monster, decks

    def cast_heal(self, fight, characters, monster, decks, target_id, action_id):
        from wakfu_server.combat_server_spell import prepare_server_spell

        target = fight.actors[target_id]
        return prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 779, *target.position),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=action_id,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )

    def test_owned_heal_bonus_uses_real_healing_word_and_excludes_self(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_healing_handler import NativeHealingHandler
        from wakfu_server.combat_final_modifier import NativeFinalModifier
        from wakfu_server.combat_final_modifier import NativeFinalModifierHandler
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        fight, characters, monster, decks = self.fixture()
        self.assertEqual(fight.current.id, 7)
        self.assertEqual(
            [state.reference for state in fight.actors[8].state_ledger.entries].count(
                3205
            ),
            1,
        )
        self.assertEqual(
            next(
                state.level
                for state in fight.actors[8].state_ledger.entries
                if state.reference == 3205
            ),
            12,
        )

        activations = []
        executions = []
        prepared_heals = []
        modifier_adds = []
        final_contexts = []
        diagnostics = []
        original = EffectDispatcher.execute_activation
        original_execute = EffectDispatcher.execute
        original_prepare = NativeHealingHandler.prepare
        original_add = NativeFinalModifier.add
        original_final_call = NativeFinalModifierHandler.__call__

        def capture(dispatcher, invocation, **kwargs):
            if invocation.reference in range(136592, 136598):
                activations.append(
                    (invocation.reference, invocation.caster_id, invocation.target_id)
                )
            return original(dispatcher, invocation, **kwargs)

        def capture_execute(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
            if invocation.reference in range(136592, 136598):
                definition = dispatcher.effects.get(str(invocation.reference), {})
                condition = None
                context = dispatcher.condition_context(invocation)
                if invocation.reference == 136593 and context is not None:
                    from wakfu_server.combat_conditions import evaluate_condition

                    condition = {
                        "value": evaluate_condition(definition["criteria"], context),
                        "actors": {
                            name: (
                                None
                                if context.actors.get(name) is None
                                else context.actors[name].actor_id
                            )
                            for name in (
                                "caster",
                                "target",
                                "triggeringCaster",
                                "triggeringTarget",
                            )
                        },
                        "team_triggering_caster": (
                            None
                            if context.team_id_query is None
                            else context.team_id_query("triggeringCaster")
                        ),
                        "team_triggering_target": (
                            None
                            if context.team_id_query is None
                            else context.team_id_query("triggeringTarget")
                        ),
                        "effect_caster_original_controller": (
                            None
                            if context.effect_caster_original_controller_query is None
                            else context.effect_caster_original_controller_query()
                        ),
                        "effect_target_original_controller": (
                            None
                            if context.effect_target_original_controller_query is None
                            else context.effect_target_original_controller_query()
                        ),
                    }
                executions.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        invocation.level,
                        result,
                        invocation.native_explicit_target,
                        condition,
                        {
                            key: definition.get(key)
                            for key in (
                                "effect_class",
                                "criteria",
                                "parameters",
                                "children",
                                "native_target_selector",
                                "native_effect_flags",
                                "target_masks",
                                "native_timing_definition",
                            )
                        },
                    )
                )
            return result

        def capture_prepare(handler, effect, values, invocation):
            result = original_prepare(handler, effect, values, invocation)
            uid = result.native_running_uid
            prepared = handler.prepared.get(uid)
            modifier = handler.final_modifiers.get(uid)
            prepared_heals.append(
                (
                    invocation.target_id,
                    effect.get("effect_class"),
                    None if modifier is None else modifier.value,
                    None if prepared is None else prepared[1],
                    tuple(effect.get("parameters", ())),
                )
            )
            return result

        def capture_add(modifier, value):
            modifier_adds.append((modifier.family, modifier.uid, value))
            return original_add(modifier, value)

        def capture_final_call(handler, effect, values, invocation):
            context = handler.context(effect, invocation)
            if invocation.reference in range(136592, 136598):
                final_contexts.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        vars(context),
                    )
                )
            return original_final_call(handler, effect, values, invocation)

        before_self = fight.actors[7].hp
        with (
            patch.object(EffectDispatcher, "execute_activation", capture),
            patch.object(EffectDispatcher, "execute", capture_execute),
            patch.object(NativeHealingHandler, "prepare", capture_prepare),
            patch.object(NativeFinalModifier, "add", capture_add),
            patch.object(NativeFinalModifierHandler, "__call__", capture_final_call),
        ):
            self_cast = self.cast_heal(fight, characters, monster, decks, 7, 4)
        self.assertGreater(self_cast.fight.actors[7].hp, before_self)
        self.assertFalse(
            any(
                reference == 136593 and target_id == 7
                for reference, _, target_id in activations
            ),
            msg={"self_heal_activations": activations},
        )
        self.assertFalse(
            any(family == 258 and value == 12 for family, _, value in modifier_adds),
            msg={"self_heal_modifier_adds": modifier_adds},
        )

        activations.clear()
        with combat_diagnostic_scope(lambda **row: diagnostics.append(row), limit=4096):
            with (
                patch.object(EffectDispatcher, "execute_activation", capture),
                patch.object(EffectDispatcher, "execute", capture_execute),
                patch.object(NativeHealingHandler, "prepare", capture_prepare),
                patch.object(NativeFinalModifier, "add", capture_add),
                patch.object(
                    NativeFinalModifierHandler, "__call__", capture_final_call
                ),
            ):
                allied = self.cast_heal(fight, characters, monster, decks, 8, 5)
                control = self.cast_heal(allied.fight, characters, monster, decks, 9, 6)
        allied_gain = allied.fight.actors[8].hp - fight.actors[8].hp
        control_gain = control.fight.actors[9].hp - allied.fight.actors[9].hp
        self.assertTrue(
            any(
                row[0] == 136593 and row[1] == 7 and row[2] == 8 and row[5] is True
                for row in executions
            ),
            msg={"executions": executions},
        )
        self.assertTrue(
            any(family == 258 and value == 12 for family, _, value in modifier_adds),
            msg={
                "modifier_adds": modifier_adds,
                "final_contexts": final_contexts,
                "executions": executions,
                "diagnostics": diagnostics,
            },
        )
        self.assertGreater(
            allied_gain,
            control_gain,
            msg={
                "ally_gain": allied_gain,
                "control_gain": control_gain,
                "activations": activations,
                "executions": executions,
                "prepared_heals": prepared_heals,
                "modifier_adds": modifier_adds,
                "final_contexts": final_contexts,
                "diagnostics": [
                    {
                        key: row.get(key)
                        for key in (
                            "effect_reference",
                            "effect_class",
                            "status",
                            "criteria",
                            "reason",
                            "exception_type",
                            "caster_id",
                            "target_id",
                            "state_uid",
                        )
                    }
                    for row in diagnostics
                    if row.get("effect_reference") in range(136592, 136598)
                ],
                "listener_rows": {
                    uid: row
                    for uid, row in fight.native_retained_records.items()
                    if row.get("generic_effect") in range(136592, 136598)
                },
                "listener_invocations": {
                    uid: group.get("invocation")
                    for uid, group in fight.native_owned_group_effects.items()
                    if group.get("invocation", {}).get("reference")
                    in range(136592, 136598)
                },
                "ally_events": [
                    event
                    for event in allied.fight.events
                    if event.get("kind") == "healing"
                ],
                "control_events": [
                    event
                    for event in control.fight.events
                    if event.get("kind") == "healing"
                ],
                "ally_states": [
                    (state.reference, state.level)
                    for state in allied.fight.actors[8].state_ledger.entries
                ],
                "control_states": [
                    (state.reference, state.level)
                    for state in control.fight.actors[9].state_ledger.entries
                ],
            },
        )
