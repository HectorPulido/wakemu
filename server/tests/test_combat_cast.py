import struct
import unittest
from types import SimpleNamespace
from dataclasses import replace
from wakfu_server.combat_state import Actor, Fight
from native_combat_fixture import initialize_fixture_qi
from wakfu_server.combat_qi_fight import move_registered_actor
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionCell,
    ConditionContext,
)
from wakfu_server.combat_conditional_costs import ConditionalCostContext
from wakfu_server.combat_cast import (
    decode_cast,
    normal_damage_profile,
    prepare_cast,
    prepare_spell_cast,
)
from wakfu_server.spells import encode_deck


def cast_context(*, states=(), deck=(), range_value=0, carried=False, properties=()):
    """Complete live caster authority for native cast selection and range."""
    caster = ConditionActor(
        state_ids=None if states is None else frozenset(states),
        deck_spell_ids=frozenset(deck),
        excluded_deck_spell_ids=frozenset(),
        is_player=True,
        is_carried=carried,
        fight_properties=frozenset(properties),
        characteristics={"RANGE": range_value},
    )
    return ConditionContext({"caster": caster})


def cast_authority(*, states=(), deck=(), ap_modifiers=None):
    context = cast_context(states=states, deck=deck)
    return lambda request, fight: native_cost_context(
        context, ap_modifiers, request, fight
    )


def native_cost_context(context, modifiers, request, fight):
    """Use the real eligibility producer over this owned synthetic population."""
    from wakfu_server.combat_casting_context import NativeOwnedCastingContext

    def metadata(state, actor):
        return SimpleNamespace(
            native_instance_id=999999,
            targeting=dict(
                is_eGj=True,
                is_amO=True,
                is_Qq=False,
                is_eHH=True,
                bEe=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
                dTE=False,
                bcN=actor.native_obstacle_id,
                baF=True,
                fqx=False,
                dpu_id=actor.id,
                dpr_id=actor.id,
            ),
        )

    metadata.properties = lambda state, actor: actor.native_fight_properties

    def condition(state, plan, effect, invocation):
        # Actual aBn cell alias and independently resolved QI target; this
        # synthetic fixture explicitly owns empty states and no summons.
        actors = dict(context.actors)
        caster = state.actors[invocation.caster_id]
        actors["caster"] = replace(
            actors["caster"],
            actor_id=caster.id,
            in_fight=True,
            summon_count=0,
            is_native_fighter=True,
            fight_affiliation=caster.team,
            is_in_play=True,
            is_dead=False,
        )
        target = state.actors.get(invocation.target_id)
        if target is not None:
            actors["target"] = replace(
                actors["caster"]
                if target.id == caster.id
                else ConditionActor(
                    state_ids=frozenset(),
                    state_levels=(),
                    state_sources=(),
                    fight_properties=target.native_fight_properties,
                    is_player=target.controlled,
                    is_carried=False,
                ),
                actor_id=target.id,
                in_fight=True,
                is_native_fighter=True,
                is_in_play=True,
                is_dead=False,
                fight_affiliation=target.team,
            )
        else:
            actors.pop("target", None)
        cell = invocation.cell
        occupied = any(actor.position == cell for actor in state.actors.values())

        def allies_range(minimum, maximum, selector, aligned, los, in_play=True):
            from wakfu_server.combat_range_conditions import RangeFighter, range_count
            from wakfu_server.combat_los import static_visible

            selected = caster if selector.lower() == "caster" else target
            center = selected.position if selected is not None else invocation.cell
            return range_count(
                tuple(
                    RangeFighter(
                        actor.position,
                        actor.physical_radius,
                        actor.team,
                        True,
                        False,
                        False,
                        114 in actor.native_fight_properties,
                    )
                    for actor in state.actors.values()
                ),
                affiliation=caster.team,
                center=center,
                minimum=minimum,
                maximum=maximum,
                aligned=aligned,
                los=los,
                relation="ally",
                in_play=in_play,
                visible=lambda a, b: static_visible(999999, a, b),
            )

        return replace(
            context,
            actors=actors,
            allies_range_query=allies_range,
            target_cell=ConditionCell(cell in state.walkable, occupied),
            target_cell_is_explicit=True,
            native_cell_target_fighter_resolved=True,
            effect_target_absent=target is None,
        )

    adapter = SimpleNamespace(
        _actor=metadata,
        actor_authority=metadata,
        condition=condition,
    )

    def query(rule, spell_id, level):
        invocation = SimpleNamespace(
            caster_id=request["actor_id"], cell=request["target"]
        )
        casting = NativeOwnedCastingContext(
            adapter, fight, request, invocation, context, rule
        )
        casting.resolve_target_fighter()
        return dict(
            result=casting.eligibility(),
            aligned=casting.alignment(),
            target_id=None if casting.target is None else casting.target.id,
        )

    return ConditionalCostContext(
        replace(context, native_casting_query=query), modifiers
    )


class CastValidationTests(unittest.TestCase):
    def test_simple_spell_ap_modifiers_apply_before_resource_validation(self):
        from wakfu_server.combat_conditional_costs import native_catalog
        from wakfu_server.combat_conditions import UnknownCondition

        category = native_catalog()["spell_categories"]["6260"][0]
        self.actor.spell_ap_cost_modifiers = {category: -2}
        self.actor.ap = 1
        plan = prepare_spell_cast(
            self.body,
            self.character,
            self.fight,
            3,
            encode_deck([6260]),
            wp=6,
            line_of_sight=lambda *a: True,
            conditional_context=cast_authority(
                ap_modifiers=self.actor.spell_ap_cost_modifiers
            ),
        )
        self.assertEqual(plan["costs"]["ap"], 1)
        self.assertEqual(self.actor.ap, 1)
        self.actor.spell_ap_cost_modifiers = {category: 2}
        with self.assertRaises(ValueError):
            prepare_spell_cast(
                self.body,
                self.character,
                self.fight,
                3,
                encode_deck([6260]),
                wp=6,
                line_of_sight=lambda *a: True,
                conditional_context=cast_authority(
                    ap_modifiers=self.actor.spell_ap_cost_modifiers
                ),
            )
        self.actor.spell_ap_cost_modifiers = None
        with self.assertRaises(UnknownCondition):
            prepare_spell_cast(
                self.body,
                self.character,
                self.fight,
                3,
                encode_deck([6260]),
                wp=6,
                line_of_sight=lambda *a: True,
                conditional_context=cast_authority(
                    ap_modifiers=self.actor.spell_ap_cost_modifiers
                ),
            )

    def test_conditional_cost_callback_uses_live_state_and_native_modifier_snapshot(
        self,
    ):
        from wakfu_server.combat_conditions import UnknownCondition

        move_registered_actor(self.fight, self.target, (3, 0, 0))
        character = dict(self.character, breed=8, level=200)
        self.actor.effective_level = 200
        body = struct.pack(">qqiih", 7, (7 << 32) | 4785, 3, 0, 0)
        context = cast_context(states=[6117])
        args = dict(wp=6, line_of_sight=lambda *a: True)
        with self.assertRaises(UnknownCondition):
            prepare_spell_cast(
                body,
                character,
                self.fight,
                3,
                encode_deck([4785]),
                conditional_context=lambda *unused: ConditionalCostContext(
                    cast_context(states=None), {}
                ),
                **args
            )
        calls = []

        def authority(request, fight):
            calls.append((request["spell_uid"], fight.current.ap))
            # Enrich the tested state authority with complete range inputs.
            return native_cost_context(context, {}, request, fight)

        plan = prepare_spell_cast(
            body,
            character,
            self.fight,
            3,
            encode_deck([4785]),
            conditional_context=authority,
            **args
        )
        self.assertEqual(plan["costs"]["ap"], 3)
        self.assertEqual(calls, [((7 << 32) | 4785, 6)])
        self.assertEqual(self.actor.ap, 6)
        with self.assertRaises(UnknownCondition):
            prepare_spell_cast(
                body,
                character,
                self.fight,
                3,
                encode_deck([4785]),
                conditional_context=lambda request, fight: native_cost_context(
                    context, None, request, fight
                ),
                **args
            )

    def setUp(self):
        from unittest.mock import patch
        from wakfu_server.combat_native_los_ray import static_ray, topology_columns
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        self.character = dict(id=7, breed=15, level=1, map_id=999999)
        self.actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        self.target = Actor(-7, 1, (2, 0, 0), 20, 6, 3, 0, 1)
        # Native7551 requires another actual ally within two cells.
        self.ally = Actor(8, 0, (-1, 0, 0), 60, 6, 3, 0, 1, 3, True)
        self.fight = Fight(
            77,
            [self.actor, self.target, self.ally],
            {(x, 0, 0) for x in range(-1, 4)},
            {0: {self.actor.position, self.ally.position}, 1: {self.target.position}},
        )
        for actor in self.fight.actors.values():
            actor.spell_ap_cost_modifiers = {}
            actor.spell_range_modifiers = {}
            actor.native_fight_properties = frozenset()
            actor.effect_stats = {92: 0, 97: 0, 100: 0}
            actor.effect_maxima = {92: 0}
            actor.effect_frozen = frozenset()
            actor.native_los_height = native_actor_catalog()["default_actor_los_height"]
        initialize_fixture_qi(self.fight)
        self.fight.ready(3)
        static_ray.cache_clear()
        self.addCleanup(static_ray.cache_clear)
        terrain = patch(
            "wakfu_server.combat_native_los_ray.topology_columns",
            side_effect=lambda map_id: {(x, 0): ((0, 0, False),) for x in range(-1, 4)}
            if map_id == 999999
            else topology_columns(map_id),
        )
        terrain.start()
        self.addCleanup(terrain.stop)
        from wakfu_server.combat_qi_surfaces import NativeQISurfaces
        from wakfu_server.combat_qi_surface_catalog import native_qi_surfaces
        import hashlib
        import json

        # Explicit flat test surfaces share the synthetic QI/LOS domain.
        columns = [[x, 0, [[0, 0]]] for x in range(-1, 4)]
        digest = hashlib.sha256(json.dumps(columns).encode()).hexdigest()
        surfaces = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=999999,
                source_sha256=digest,
                chunks=[dict(x=-1, y=0, width=5, height=1, columns=columns)],
            ),
            map_id=999999,
            source_sha256=digest,
        )
        provider = patch(
            "wakfu_server.combat_qi_surface_catalog.native_qi_surfaces",
            side_effect=lambda map_id: surfaces
            if map_id == 999999
            else native_qi_surfaces(map_id),
        )
        provider.start()
        self.addCleanup(provider.stop)

        self.body = struct.pack(">qqiih", 7, (7 << 32) | 6260, 2, 0, 0)

    def prepare(self, **options):
        args = dict(
            complete=False,
            wp=6,
            line_of_sight=lambda *a: True,
            conditional_context=cast_authority(
                ap_modifiers=self.actor.spell_ap_cost_modifiers
            ),
            select_effect=lambda *a: True,
            mitigate=lambda damage, *a: damage,
        )
        args.update(options)
        return prepare_cast(
            self.body, self.character, self.fight, 3, encode_deck([6260]), **args
        )

    def test_own_normal_cast_and_native_profiles(self):
        p = self.prepare()
        self.assertEqual((p["damage"], p["costs"]["ap"], p["target_id"]), (3, 3, -7))
        self.assertEqual(normal_damage_profile(6261, 1)["maximum"], 1)
        self.assertGreater(normal_damage_profile(6260, 200)["damage"], 3)

    def test_common_validation_accepts_self_spells_across_classes(self):
        self.actor.effective_level = 200
        for breed, spell in [(1, 6983), (8, 4779), (15, 7551)]:
            character = dict(self.character, breed=breed, level=200)
            body = struct.pack(">qqiih", 7, (7 << 32) | spell, 0, 0, 0)
            plan = prepare_spell_cast(
                body,
                character,
                self.fight,
                3,
                encode_deck([spell]),
                wp=6,
                line_of_sight=lambda *args: True,
                conditional_context=cast_authority(ap_modifiers={}),
            )
            self.assertEqual(plan["target_id"], self.actor.id)
            self.assertEqual(plan["spell_id"], spell)
            self.assertTrue(plan["effect_ids"])
        self.assertEqual(self.actor.ap, 6)  # Validation never spends resources.

    def test_common_validation_keeps_empty_cell_target(self):
        self.actor.effective_level = 200
        character = dict(self.character, level=200)
        body = struct.pack(">qqiih", 7, (7 << 32) | 7551, 1, 0, 0)
        plan = prepare_spell_cast(
            body,
            character,
            self.fight,
            3,
            encode_deck([7551]),
            wp=6,
            line_of_sight=lambda *args: True,
            conditional_context=cast_authority(ap_modifiers={}),
        )
        self.assertIsNone(plan["target_id"])
        self.assertEqual(plan["target"], (1, 0, 0))

    def test_reject_unknown_branch_los_and_resources(self):
        for opts in [
            dict(select_effect=lambda *a: None),
        ]:
            with self.assertRaises(ValueError):
                self.prepare(**opts)
        # Native casting queries own LOS; the legacy callback is not its gate.
        self.fight.native_qi_snapshot["cell_masks"][2] |= 256
        with self.assertRaisesRegex(ValueError, "twG"):
            self.prepare()
        self.fight.native_qi_snapshot["cell_masks"][2] &= ~256
        self.actor.ap = 2
        with self.assertRaises(ValueError):
            self.prepare()

    def test_complete_cast_rejects_omitted_mp_effect(self):
        with self.assertRaises(ValueError):
            self.prepare(complete=True)

    def test_reject_uid_owner_deck_and_exact_length(self):
        self.body = struct.pack(">qqiih", 7, (8 << 32) | 6260, 2, 0, 0)
        with self.assertRaises(ValueError):
            self.prepare()
        with self.assertRaises(ValueError):
            decode_cast(self.body + b"\0")

    def test_bare_selector_native_close_branch_and_unknown_states(self):
        from wakfu_server.combat_bare_effects import bare_damage_selector

        selector = bare_damage_selector(
            critical_chance=0, running_effects=[], summons=[], bonuses={}
        )
        self.assertTrue(
            selector(
                6260,
                normal_damage_profile(6260, 1),
                self.actor,
                self.target,
                self.fight,
            )
        )
        self.assertFalse(
            selector(
                6266,
                normal_damage_profile(6266, 1),
                self.actor,
                self.target,
                self.fight,
            )
        )
        move_registered_actor(self.fight, self.target, (1, 0, 0))
        self.body = struct.pack(">qqiih", 7, (7 << 32) | 6266, 1, 0, 0)
        plan = prepare_cast(
            self.body,
            self.character,
            self.fight,
            3,
            encode_deck([6266]),
            wp=6,
            line_of_sight=lambda *a: True,
            conditional_context=cast_authority(
                ap_modifiers=self.actor.spell_ap_cost_modifiers
            ),
            select_effect=selector,
            mitigate=lambda damage, *a: damage,
        )
        self.assertEqual(
            (plan["generic_effect"], plan["damage"], plan["pending_side_effects"]),
            (339526, 5, None),
        )
        with self.assertRaises(ValueError):
            bare_damage_selector(
                critical_chance=0, running_effects=None, summons=[], bonuses={}
            )
