"""Restricted native effect criteria, with explicit unknowns instead of guesses.

Evidence: wakfu-client.jar eQb tokens 198/342 -> eQd eME/eOS.
eME.a tests eHg.kY(stateId); its numeric second argument uses eHg.v,
which compares the FIRST matching state level for equality (not a threshold). eII.a resolves absent selectors to caster.
eGj.kY iterates state effects and compares fyW.guI state IDs. eOS defaults to caster,
requires a player (aGJ == 0), an active deck, and excludes eEI/eEL.pby IDs.
HasStateFromLevel: eQb223 -> eQd/eMF -> eGj.w(long,long) compares
the FIRST matching state level >= threshold (default zero), not a sum or max.
HasStateFromUser: eQb224 -> eQd/eMG -> eGj.a(long,eHg) compares
the FIRST matching state effect source Sn with caster Sn. IsCarried:
eQb257 -> eQd/eNv -> eGj.buX tests non-null carrier. IsTargetCellFree:
eQb288 -> eQd/eOV validates terrain QI.R, occupants Qq.bcP and QI.V
obstacles; optional True rejects even nonblocking occupants.
NbSummons: eQb384/ePs -> eGj.dTB/GF (active owned summons filtered).
IsBreedId: eQb256/eNu compares eGH.aXA with short-converted IDs.
IsBreed: eQb254/eNs resolves all eGE.to names; last selector wins, default caster.
IsInAlignment: eQb314/eNX compares caster/target x or y equality.
GetCharac: eQb39/eJy reads eHg.c(PC), missing native PC=-1.
Percent aliases: eQb41/eJz uses float32 current/max*100 and GS.B floor.
GetCharacMax: eQb40/eJA reads eHg.d(PC), missing actor or PC=-1.
GetStateLevel: eQb161/eQd/eLs -> eHg.df(long), eGj.df returns FIRST matching state level or-1; no sum/max.
Arithmetic: alp addition, amd subtraction, alJ multiplication, alC double division.
HasFightProperty: eMo selects caster or target, narrows ID to signed byte,
ffe.Ua resolves the enum and PV.a(ffe) reads fight properties (eGj.pGH).
IsEnemy/IsEnnemy: eNM compares registered eHg.bcM affiliations.
All context supplied here must describe the authoritative current cast.
"""
from __future__ import annotations

import ast
import math
import struct
from dataclasses import dataclass
from typing import Mapping
from functools import lru_cache
from .combat_characteristic_conditions import canonical_aliases


# Complete native eGE enum export (not a supported-class whitelist).
_NATIVE_BREED_NAMES = dict(
    zip(
        (
            "COMMON",
            "NONE",
            "FECA",
            "OSAMODAS",
            "ENUTROF",
            "SRAM",
            "XELOR",
            "ECAFLIP",
            "ENIRIPSA",
            "IOP",
            "CRA",
            "SADIDA",
            "SACRIER",
            "PANDAWA",
            "ROUBLARD",
            "ZOBAL",
            "OUGINAK",
            "STEAMER",
            "SOUL",
            "ELIOTROPE",
            "HUPPERMAGE",
        ),
        (-2, -1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19),
    )
)


class UnknownCondition(ValueError):
    """A criterion or required context has no verified evaluator."""


@dataclass(frozen=True)
class ConditionActor:
    # None means unavailable; an empty set means authoritatively empty.
    state_ids: frozenset[int] | None = None
    deck_spell_ids: frozenset[int] | None = None
    excluded_deck_spell_ids: frozenset[int] | None = None
    is_player: bool | None = None
    actor_id: int | None = None
    # Native iteration order matters: first matching effect decides source.
    state_sources: tuple[tuple[int, int | None], ...] | None = None
    state_levels: tuple[tuple[int, int], ...] | None = None
    is_carried: bool | None = None
    is_carrying: bool | None = (
        None  # eGj.frA: pGV carried actor, separate from pGW/buX.
    )
    breed_id: int | None = None
    effective_level: int | None = None
    real_level: int | None = (
        None  # Native progression drm, distinct from modulated cmZ.
    )
    world_properties: frozenset[int] | None = None  # eHg.i(eHQ), actor pGI.
    world_property_since_ms: Mapping[int, int] | None = None  # Complete eHC ledger.
    fight_properties: frozenset[int] | None = None  # PV.a(ffe), not world properties.
    fight_affiliation: int | None = (
        None  # eHg.bcM(), independent of bcN targeting team.
    )
    is_native_fighter: bool | None = None
    is_challenger: bool | None = (
        None  # Native eHh PLAYER_CHARACTER or COMPANION, not team.
    )
    is_character: bool | None = None  # eHg.a(eHh.CHARACTER), includes NPCs.
    is_off_play: bool | None = None  # eHg.baG; distinct from KO/dead/inPlay roster.
    is_native_ehg: bool | None = None  # Registered faV is eHg, plain Qq need not be.
    is_in_play: bool | None = None  # Actual eHg.baF, not positive HP.
    is_dead: bool | None = None  # Actual eGj.dsA, not baG or HP0.
    is_summoned_from_symbiot: bool | None = None  # Actual eHg.dTC creation source.
    native_sex: int | None = None  # Actual eGj.aXz signed byte, independent of breed.
    is_summon: bool | None = None  # eGj.dTE(), not merely an NPC kind.
    summon_root_id: int | None = None  # Identity of eGj.fqK ownership-chain root.
    retained_action_ids: frozenset[
        int
    ] | None = None  # Qe.d in complete native Qf, not PK.aZE.
    retained_effect_ids: frozenset[int] | None = None  # PK.aZE in complete owned Qf.
    in_fight: bool | None = None  # Authoritative eHg.dnz actor membership.
    native_instance_id: int | None = (
        None  # eGj.arM from POSITION rE.Vp, not fight/server instance ID.
    )
    physical_radius: int | None = None  # eHg.bcL signed-byte snapshot.
    # Counts must already satisfy native eGj.GF filters (owned, active,
    # not excluded by offplay/properties), not simply len(actor.summons).
    summon_count: int | None = None
    summon_counts_by_breed: Mapping[int, int] | None = None
    summon_counts_complete: bool = False
    characteristics: Mapping[str, int | None] | None = None
    characteristic_maxima: Mapping[str, int] | None = None
    direction: int | None = None  # Native eGj.bcy().dyI; None means unknown.


@dataclass(frozen=True)
class ConditionCell:
    terrain_valid: bool
    has_obstacle: bool
    # Entries contain native Qq.bcP flags for occupants at this position.
    occupant_blocks: tuple[bool, ...] = ()


@dataclass(frozen=True)
class ConditionContext:
    actors: Mapping[str, ConditionActor]
    target_cell: ConditionCell | None = None
    caster_target_distance: int | None = None
    is_in_alignment: bool | None = None
    enemy_target_kind: str = (
        "actor"  # actor/null/cell; unknown cell affiliations reject.
    )
    enemy_cell_affiliations: tuple[int, ...] | None = None
    enemy_cell_affiliations_query: object = None  # eNM fbX.fk footprints + first QI.V.
    effect_target_absent: bool | None = (
        None  # Proven eII.b result null; missing context remains unknown.
    )
    target_cell_is_explicit: bool | None = None  # aBn target may fall back through QI.
    native_cell_target_fighter_resolved: bool | None = (
        None  # Actual QI.ay lookup completed.
    )
    triggering_effect_target_id: int | None = (
        None  # eLN source eGj.Sn, -1 for proven null.
    )
    triggering_effect_caster_id: int | None = (
        None  # eKl triggeringCaster eHg.Sn; -1 for proven null.
    )
    triggering_caster_is_same: bool | None = None  # eLL: native PV object identity.
    triggering_melee_distance: int | None = (
        None  # Actual source bbb/bbc ala.c, not listener.
    )
    triggering_zone_effect: bool | None = None
    triggering_effect_flags: frozenset[
        int
    ] | None = None  # Source PK REP flags, not listener.
    triggering_effect_present: bool | None = None
    triggering_effect_reference_id: int | None = (
        None  # Source eZR.aZE definition reference.
    )
    triggering_effect_value: int | None = None  # Source eZR.getValue signed int.
    triggering_effect_action_id: int | None = None  # Source eVn.awM, NOT aZE.
    triggering_effect_variant: int | None = None  # Actual source PK.dd(1).
    triggering_effect_definition_present: bool | None = None
    triggering_effect_execution_status: int | None = None  # Source eZR.cYh byte.
    triggering_effect_blocked: bool | None = None  # Proven source cYh()==7.
    activation_query: object = None  # Actual fbX.bah current PZ, not Qe source.
    fight_current_table_turn: int | None = (
        None  # Native SU.bhN signed short, not personal turn.
    )
    triggering_container_is_state: bool | None = None
    triggering_source_is_eWu: bool | None = None
    triggering_apply_state_reference: int | None = None
    triggering_container_state_id: int | None = None  # Source fyW.guI signed short.
    triggering_container_type: int | None = None  # Source eVo.aZY, zero for known null.
    world_property_now_ms: int | None = None
    areas_base_id_query: object = None  # ePj/ePi exact Qs prototype count.
    actor_specific_area_query: object = None  # eOv selected eHg/Qq geometry.
    own_summon_actor_query: object = None  # eOG/eII arbitrary native selector.
    surrounding_own_summon_query: object = None  # eMP complete direct-owner fUQ roster.
    controlled_by_ai_query: object = None  # eNH actual eGj.fqL state.
    free_cell_query: object = None  # eNR rotated point and actual QI/Qs.
    free_surrounding_cell_query: object = None  # eMp cardinal QI.V/Q/R.
    gate_count_query: object = None  # ePn actual Qs type19 population.
    glyph_count_query: object = None  # ePo/ePi actual Qs type0 and Qq.bch owner.
    own_specific_area_query: object = None  # eOF Qz/owner criterion.
    area_identity_query: object = None  # eNm/eOQ/eOC actual Qz/aBn/null target.
    valid_gate_for_tp_query: object = None  # eMT complete Qs/captured bcM/QI.U.
    use_gate_effect_query: object = (
        None  # ePI actual runner/fyG -> fcj and static path.
    )
    use_gate_triggering_effect_query: object = (
        None  # ePJ original trigger cell/container.
    )
    original_controller_predicate_query: object = None  # eIC/eOx actual eHg dTD/Sn.
    selected_creature_available_query: object = None  # eON actual eHP.drI status.
    breed_in_symbiot_query: object = None  # eMd evaluated profile + eII.a selector.
    space_in_symbiot_query: object = None  # eLm/eHR.fxp actual ten-slot component.
    closest_specific_area_query: object = None  # eJT/eIw positive distance minimum.
    specific_area_range_query: object = None  # eLn/eJW complete Qs authority.
    coordinate_query: object = None  # eLT/eLU/eLW eHg or explicit aBn target.
    border_cell_query: object = None  # eOr eII actor/cell -> validated QI.P.
    backstabbed_query: object = None  # eNn/eIG current selected eGj Sl and opposite PV.
    facestabbed_query: object = None  # eNP/eIG same selection, native FRONT result.
    sidestabbed_query: object = None  # eOP/eIG accepts both native lateral results.
    effect_caster_original_controller_query: object = None  # eKa current Qe.bbb.dTD.
    spell_level_query: object = None  # eLo complete native owned spellbook lookup.
    active_spell_id_query: object = None  # eJn current fight PZ, not trigger.
    effect_target_original_controller_query: object = (
        None  # eKc current Qe.bbc/eHg.dTD.
    )
    current_container_level_query: object = None  # eJE current eZR, not trigger.
    area_type_range_query: object = None
    state_actor_query: object = None  # eII selector -> known actor or proven null.
    life_actor_query: object = None  # Actual eII eGj/eHg life selection.
    actor_obstacle_query: object = None
    viewer_id: int | None = None
    actor_area_type_query: object = None
    team_area_range_query: object = None
    cell_specific_area_query: object = None
    cell_area_type_query: object = None  # eID Qq.d native geometry.
    line_of_sight_query: object = None  # eMr/eII.aR/fcr exact runtime authority.
    random_number_query: object = None  # eLb transaction-owned uniform index.
    fighters_breed_range_query: object = None  # eKt/eKn complete fUQ breed roster.
    human_allies_range_query: object = None  # eKz exact aGJ 0/5 filter.
    human_enemies_range_query: object = None  # eKe exact aGJ 0/5 filter.
    allies_count_query: object = None  # eJo actual IN_PLAY same-affiliation roster.
    monsters_count_query: object = None  # eKK/fbX.e exact IN_PLAY aGJ1/2 roster.
    native_usage_context_query: object = (
        None  # fyS null/PV-specific fyP criteria context.
    )
    has_summon_breed_query: object = None  # eMI exact breed/direct dpu over fUQ.
    enemy_range_query: object = None  # Complete live eKf/eKn roster authority.
    allies_range_query: object = None  # eJp affiliation/inPlay/114 filters.
    team_id_query: object = None  # eLx/eII.a actual selector relationship.
    own_team_state_range_query: object = None  # eKS filters state caster affiliation.
    state_range_query: object = None  # eLr complete actor + Qq carrier population.
    item_quantity_query: object = None  # eKE current source actor inventory.
    null_actor_aliases: frozenset[str] = frozenset()  # Proven selected eHg null.
    state_null_fallback_absent: bool | None = None  # Qe context is not ePy.
    current_fighter_id: int | None = (
        None  # eJJ current SU identity; zero if no active turn.
    )
    fight_model_query: object = None  # eKj resolves the active fbX from native context.
    pvp_query: object = None  # eOL fcz.fVU().fcL.fVT, including DUEL.
    boolean_system_configuration_query: object = (
        None  # eJs eEL/eEI actual defaults/overrides.
    )
    active_cosmetic_id_query: object = None  # eJi eSU/eSP selected cosmetic id.
    has_active_cosmetic_query: object = None  # eLX eSP list membership.

    is_in_diagonal: bool | None = None  # eNY resolved fight/coordinate snapshot.
    native_casting_query: object = (
        None  # Owned fcj request/table producer, not effect execution.
    )


class _UncachedConditionRoot(Exception):
    def __init__(self, root):
        self.root = root


@lru_cache(maxsize=512)
def _cached_condition_root(criteria):
    from .combat_local_criteria import parse_local_criterion

    root = parse_local_criterion(criteria)
    for count, _ in enumerate(ast.walk(root), 1):
        if count > 256:
            # Exceptions are not retained by lru_cache. Return this already
            # parsed large tree through the uncached wrapper, without reparsing.
            raise _UncachedConditionRoot(root)
    return root


def _condition_root(criteria):
    from .combat_local_criteria import parse_local_criterion

    if len(criteria) > 2048:
        return parse_local_criterion(criteria)
    try:
        return _cached_condition_root(criteria)
    except _UncachedConditionRoot as error:
        return error.root


def evaluate_condition(criteria: str, context: ConditionContext) -> bool:
    """Evaluate the proven subset; raise UnknownCondition for all other input.

    Validate every branch before evaluation, including short-circuited branches,
    so unsupported expressions can never be mistaken for supported conditions.
    This is a boolean subset, not a Python eval or the full native script language.
    """
    if not criteria.strip():
        return True
    from .combat_local_criteria import LocalCriterionSyntax

    try:
        root = _condition_root(criteria.strip())
    except LocalCriterionSyntax as exc:
        raise UnknownCondition(
            f"Unsupported native criterion: {criteria}: {exc}"
        ) from exc

    aliases = canonical_aliases()

    def literal_long(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            value = node.value
        elif isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.USub, ast.UAdd)
        ):
            value = literal_long(node.operand)
            if isinstance(node.op, ast.USub):
                value = -value
        else:
            raise UnknownCondition(
                "Native triggering depth requires a constant integer"
            )
        if not -(1 << 63) <= value < (1 << 63):
            raise UnknownCondition("Native triggering depth exceeds signed long")
        return value

    def is_selector(node):
        return (
            isinstance(node, ast.Constant)
            and type(node.value) is str
            and node.value.lower() in ("caster", "target")
        )

    def is_state_actor_selector(node):
        return (
            isinstance(node, ast.Constant)
            and type(node.value) is str
            and node.value.lower()
            in (
                "caster",
                "target",
                "castercontroller",
                "triggeringcaster",
                "triggeringtarget",
            )
        )

    def check_number(node):
        if isinstance(node, ast.IfExp):
            check(node.test)
            check_number(node.body)
            check_number(node.orelse)
            return
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not math.isfinite(node.value):
                raise UnknownCondition("Nonfinite native number")
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            check_number(node.operand)
            return
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod)
        ):
            check_number(node.left)
            check_number(node.right)
            return
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.keywords
        ):
            raise UnknownCondition("Unsupported native numeric expression")
        name, args = node.func.id, node.args
        if name == "IsPvp":
            return  # Original eOL constructor ignores parsed arguments.
        if name == "GetBooleanSystemConfiguration":
            if (
                len(args) != 1
                or not isinstance(args[0], ast.Constant)
                or type(args[0].value) is not str
            ):
                raise UnknownCondition(
                    "Native Boolean configuration requires one literal string"
                )
            return
        if name == "GetFightModel":
            if args:
                raise UnknownCondition("Native GetFightModel takes no arguments")
            return
        if name == "GetActiveCosmeticId":
            if len(args) != 1:
                raise UnknownCondition(
                    "Native GetActiveCosmeticId requires one category"
                )
            check_number(args[0])
            return
        if name == "GetSpaceInSymbiot":
            # eLm does not call alS.s(parameters): parsed arguments are ignored.
            return
        if name == "NbGlyphs":
            if len(args) > 1 or (args and not is_state_actor_selector(args[0])):
                raise UnknownCondition("Unsupported native NbGlyphs selector")
            return
        if name == "NbGates":
            if len(args) != 2 or any(
                not isinstance(arg, ast.Constant) or type(arg.value) is not str
                for arg in args
            ):
                raise UnknownCondition("Native NbGates requires two literal strings")
            return
        if name == "GetDistanceToClosestSpecificArea":
            if (
                len(args) not in (3, 4)
                or not isinstance(args[0], ast.Constant)
                or type(args[0].value) is not str
                or (
                    len(args) == 4
                    and (
                        not isinstance(args[3], ast.Constant)
                        or type(args[3].value) is not str
                    )
                )
            ):
                raise UnknownCondition("Unsupported native closest-area signature")
            check_number(args[1])
            check(args[2])
            return
        if name == "GetDate":
            if len(args) not in (0, 6):
                raise UnknownCondition("Unsupported native GetDate signature")
            for arg in args:
                literal_long(arg)
            return
        if name == "GetItemQuantity":
            if not args:
                raise UnknownCondition("GetItemQuantity requires references")
            for arg in args:
                check_number(arg)
            return
        if name == "NbAreasWithBaseId":
            if len(args) not in (1, 2):
                raise UnknownCondition("Unsupported native base-area count signature")
            literal_long(args[0])
            if len(args) == 2 and not (
                isinstance(args[1], ast.Constant) and type(args[1].value) is str
            ):
                raise UnknownCondition(
                    "Native base-area owner requires string selector"
                )
            return
        if name == "GetTeamEffectAreaCountInRange":
            if (
                len(args) != 4
                or not isinstance(args[0], ast.Constant)
                or type(args[0].value) is not str
            ):
                raise UnknownCondition("Unsupported native team-area range signature")
            for arg in args[1:]:
                check_number(arg)
            return
        if name in ("GetSpecificEffectAreaCountInRange", "GetEffectAreaCountInRange"):
            if (
                len(args) not in (4, 5)
                or not isinstance(args[0], ast.Constant)
                or type(args[0].value) is not str
            ):
                raise UnknownCondition("Unsupported native area range signature")
            for arg in args[1:4]:
                check_number(arg)
            if len(args) == 5 and (
                not isinstance(args[4], ast.Constant) or type(args[4].value) is not bool
            ):
                raise UnknownCondition(
                    "Native area ownership flag requires a literal boolean"
                )
            return
        if name == "GetTotalHpInPercent":
            if (
                len(args) != 1
                or not isinstance(args[0], ast.Constant)
                or type(args[0].value) is not str
            ):
                raise UnknownCondition("Native total HP percentage requires one string")
            return
        if name == "GetRandomNumber":
            if not callable(context.random_number_query):
                raise UnknownCondition(
                    "Missing transaction-owned native random authority"
                )
            if len(args) not in (1, 2):
                raise UnknownCondition(
                    "Native random requires limit and optional exclusions"
                )
            check_number(args[0])
            if not integral(args[0]):
                raise UnknownCondition("Limit not an integer")
            if len(args) == 2:
                if not isinstance(args[1], (ast.List, ast.Tuple)):
                    raise UnknownCondition(
                        "Native random exclusions require a numeric list"
                    )
                for value in args[1].elts:
                    check_number(value)
                    if not integral(value):
                        raise UnknownCondition(
                            "Native random exclusions require integers"
                        )
            return
        if name == "GetFightersWithBreedInRange":
            if (
                len(args) != 3
                or not isinstance(args[1], ast.Constant)
                or type(args[1].value) is not str
            ):
                raise UnknownCondition(
                    "Native breed range requires radius, selector, breed"
                )
            check_number(args[0])
            check_number(args[2])
            return
        if name == "GetAlliesCount":
            if len(args) > 1 or (
                args
                and (
                    not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                )
            ):
                raise UnknownCondition(
                    "Native allies count requires optional string selector"
                )
            return
        if name == "GetMonstersInFight":
            if len(args) > 2:
                raise UnknownCondition(
                    "Native monster count takes at most two numeric arguments"
                )
            for argument in args:
                check_number(argument)
            return
        if name in (
            "GetEnnemyCountInRange",
            "GetAlliesCountInRange",
            "GetHumanAlliesCountInRange",
            "GetEnemiesHumanCountInRange",
        ):
            if not 1 <= len(args) <= (6 if name == "GetAlliesCountInRange" else 5):
                raise UnknownCondition("Unsupported native enemy range signature")
            numeric = 1 if len(args) <= 2 else 2
            for argument in args[:numeric]:
                check_number(argument)
            if len(args) > numeric and (
                not isinstance(args[numeric], ast.Constant)
                or type(args[numeric].value) is not str
            ):
                raise UnknownCondition(
                    "Native enemy range requires a string center selector"
                )
            for argument in args[numeric + 1 :]:
                check(argument)
            return
        if name in ("GetStateCountInRange", "GetOwnTeamStateCountInRange"):
            if (
                not 3 <= len(args) <= 5
                or not isinstance(args[1], ast.Constant)
                or type(args[1].value) is not str
            ):
                raise UnknownCondition("Unsupported native state range signature")
            check_number(args[0])
            literal_long(
                args[2]
            )  # eLr evaluates state ID with null constructor context.
            if len(args) > 3:
                fourth = args[3]
                if not isinstance(fourth, ast.Constant) or type(fourth.value) not in (
                    int,
                    bool,
                    str,
                ):
                    raise UnknownCondition(
                        "Native state range constructor requires a constant filter"
                    )
                if len(args) == 5 and (
                    type(fourth.value) is str
                    or not isinstance(args[4], ast.Constant)
                    or type(args[4].value) is not str
                ):
                    raise UnknownCondition("Unsupported native state caster filter")
            return
        if name == "IsTriggeredByEffectWithREP":
            if len(args) != 1:
                raise UnknownCondition("Native source REP requires one long")
            check_number(args[0])
            return
        if name in (
            "IsTriggeredByMeleeEffect",
            "IsTriggeredByZoneEffect",
            "IsTriggeredByIndirectEffect",
            "IsTriggeredByEffectWithREP",
            "GetTriggeringEffectCasterIsSameAsCaster",
        ):
            if args:
                raise UnknownCondition("Native zone trigger takes no arguments")
            return
        if name == "GetTriggeringApplyStateStateId":
            # Original eLF constructor never invokes signature validation or
            # stores its supplied argument list; evaluation ignores it.
            return
        if name in (
            "GetTriggeringContainerStateId",
            "GetTriggeringEffectValue",
            "GetTriggeringContainerType",
        ):
            if args:
                raise UnknownCondition("Native triggering state ID takes no arguments")
            return
        if name in ("GetTriggeringEffectActionId", "GetTriggeringEffectId"):
            if len(args) > 1:
                raise UnknownCondition(
                    "Native triggering depth requires a constant integer"
                )
            if args:
                literal_long(args[0])
            return

        if (
            name
            in (
                "GetDistanceBetweenCasterAndTarget",
                "GetEffectCaster",
                "GetTriggererEffectCaster",
                "GetTriggeringEffectCaster",
                "GetTriggeringEffectTarget",
                "GetEffectTarget",
                "GetEffectTargetOriginalController",
                "GetEffectCasterOriginalController",
                "GetInstanceId",
                "GetFightCurrentTableTurn",
                "GetCurrentFighterId",
                "GetCharacterDirection",
            )
            and not args
        ):
            return
        if name == "GetPhysicalRadius":
            if len(args) != 1 or not is_selector(args[0]):
                raise UnknownCondition(
                    "Native GetPhysicalRadius requires an actor selector"
                )
            return
        if name == "GetCharacterDirection":
            if (
                len(args) > 1
                or args
                and (
                    not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                )
            ):
                raise UnknownCondition(
                    "GetCharacterDirection takes zero or one native string selector"
                )
            return
        if name in ("GetX", "GetY", "GetZ"):
            if len(args) > 1 or (
                args
                and (
                    not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                )
            ):
                raise UnknownCondition(f"Native {name} takes zero or one string")
            return
        if name == "GetSpellLevel":
            if len(args) not in (1, 2) or (
                len(args) == 2
                and (
                    not isinstance(args[1], ast.Constant)
                    or type(args[1].value) is not str
                )
            ):
                raise UnknownCondition(
                    "Native GetSpellLevel requires reference and optional selector"
                )
            check_number(args[0])
            return
        if name == "GetActiveSpellId":
            if args:
                raise UnknownCondition("GetActiveSpellId takes no arguments")
            return
        if name == "GetContainerLevel":
            if args:
                raise UnknownCondition("GetContainerLevel takes no arguments")
            return
        if name == "GetRealLevel":
            if len(args) > 1 or (
                args
                and (
                    not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                )
            ):
                raise UnknownCondition("Unsupported GetRealLevel selector")
            return
        if name == "GetTeamId":
            if len(args) > 1 or (
                args
                and (
                    not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                )
            ):
                raise UnknownCondition("Unsupported GetTeamId selector")
            return
        if name == "GetLevel":
            if len(args) > 1 or (args and not is_selector(args[0])):
                raise UnknownCondition(f"Unsupported {name} selector")
            return
        if name == "GetStateLevel":
            if (
                not 1 <= len(args) <= 2
                or not isinstance(args[0], ast.Constant)
                or type(args[0].value) is not int
                or (len(args) == 2 and not is_selector(args[1]))
            ):
                raise UnknownCondition("Unsupported GetStateLevel arguments")
            return
        if name == "NbSummons":
            if len(args) > 2 or (args and not is_selector(args[0])):
                raise UnknownCondition("Unsupported NbSummons arguments")
            if len(args) == 2:
                literal_long(args[1])
            return
        if name in (
            "GetCharac",
            "GetCharacteristic",
            "GetCharacMax",
            "GetCharacteristicMax",
            "GetCharacInPct",
            "GetCharacPct",
            "GetCharacteristicPct",
        ):
            if (
                not 1 <= len(args) <= 2
                or not isinstance(args[0], ast.Constant)
                or type(args[0].value) is not str
                or args[0].value.upper() not in aliases
                or (len(args) == 2 and not is_state_actor_selector(args[1]))
            ):
                raise UnknownCondition("Unsupported native characteristic or actor")
            return
        raise UnknownCondition(f"Unsupported native numeric predicate: {name}")

    def integral(node):
        if isinstance(node, ast.Constant):
            return type(node.value) is int
        if isinstance(node, ast.UnaryOp):
            return integral(node.operand)
        if isinstance(node, ast.BinOp):
            return (
                not isinstance(node.op, (ast.Div, ast.Mod))
                and integral(node.left)
                and integral(node.right)
            )
        if isinstance(node, ast.IfExp):
            return integral(node.body) and integral(node.orelse)
        return isinstance(node, ast.Call) and node.func.id not in (
            "GetTotalHpInPercent",
            "GetCharacInPct",
            "GetCharacPct",
            "GetCharacteristicPct",
        )

    def number(node):
        if isinstance(node, ast.IfExp):
            value = number(node.body if run(node.test) else node.orelse)
            return value if integral(node) else float(value)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp):
            value = number(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left, right = number(node.left), number(node.right)
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            elif isinstance(node.op, ast.Mod):
                # eQd percent builds alI: bDl=false, e() always double drem.
                # fmod preserves Java dividend sign, unlike Python modulo.
                if right == 0:
                    raise UnknownCondition(
                        "Native remainder by zero requires nonfinite semantics"
                    )
                return math.fmod(float(left), float(right))
            else:
                if right == 0:
                    raise UnknownCondition(
                        "Native division by zero requires nonfinite semantics"
                    )
                return (
                    left / right
                )  # alC always uses double division, never integer division.
            return (
                ((result + 2**63) % 2**64) - 2**63
                if type(result) is int
                else result
            )
        name, args = node.func.id, node.args
        if name in ("IsPvp", "GetBooleanSystemConfiguration"):
            from .combat_system_conditions import evaluate_system_predicate

            try:
                value = evaluate_system_predicate(
                    context,
                    name,
                    args[0].value if name == "GetBooleanSystemConfiguration" else None,
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            return 0 if value else -1  # eIX native Boolean numeric result.
        if name == "GetFightModel":
            if not callable(context.fight_model_query):
                raise UnknownCondition("Missing authoritative native fight model")
            try:
                value = context.fight_model_query()
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not int or not -128 <= value <= 127:
                raise UnknownCondition("Invalid native fcz.eSS signed-byte model")
            return value
        if name == "GetActiveCosmeticId":
            if not callable(context.active_cosmetic_id_query):
                raise UnknownCondition("Missing native cosmetic component authority")
            category = number(args[0])
            try:
                value = context.active_cosmetic_id_query(category)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
                raise UnknownCondition("Invalid native active cosmetic id")
            return value
        if name == "GetSpaceInSymbiot":
            if not callable(context.space_in_symbiot_query):
                raise UnknownCondition("Missing native symbiot space authority")
            try:
                result = context.space_in_symbiot_query()
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not int or not -1 <= result <= 10:
                raise UnknownCondition("Invalid native symbiot space count")
            return result
        if name == "NbGlyphs":
            if not callable(context.glyph_count_query):
                raise UnknownCondition("Missing native glyph-count authority")
            try:
                result = context.glyph_count_query(args[0].value if args else None)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not int or result < 0:
                raise UnknownCondition("Invalid native glyph count")
            return result
        if name == "NbGates":
            if not callable(context.gate_count_query):
                raise UnknownCondition("Missing native gate-count authority")
            try:
                result = context.gate_count_query(args[0].value, args[1].value)
                if type(result) is not int:
                    raise ValueError("Missing native gate-count integer")
                return result
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetCurrentFighterId":
            value = context.current_fighter_id
            if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
                raise UnknownCondition("Missing authoritative current fighter identity")
            return value
        if name == "GetCharacterDirection":
            selector = (
                "target" if args and args[0].value.lower() == "target" else "caster"
            )
            if (
                selector == "target"
                and context.target_cell_is_explicit is True
                and context.native_cell_target_fighter_resolved is not True
            ):
                raise UnknownCondition(
                    "Missing native QI fighter lookup for explicit target cell"
                )
            actor = context.actors.get(selector)
            if actor is None:
                if selector == "target" and (
                    context.effect_target_absent is True
                    or selector in context.null_actor_aliases
                ):
                    return -1  # eII.a is null or receives a non-eGj cell target.
                raise UnknownCondition(
                    f"Missing native GetCharacterDirection actor: {selector}"
                )
            if actor.is_native_fighter is False:
                return -1  # eII.a only returns eGj, not other eHg/PV objects.
            value = actor.direction
            if type(value) is not int or not -1 <= value <= 9:
                raise UnknownCondition(f"Missing native eGj.bcy direction: {selector}")
            return value
        if name == "GetDate":
            if not args:
                value = context.world_property_now_ms
                if type(value) is not int:
                    raise UnknownCondition("Missing authoritative native clock")
                return value
            from .combat_inventory_date_conditions import calendar_milliseconds

            try:
                return calendar_milliseconds(tuple(literal_long(arg) for arg in args))
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetItemQuantity":
            if not callable(context.item_quantity_query):
                raise UnknownCondition("Missing native owned inventory authority")
            try:
                return context.item_quantity_query(tuple(number(arg) for arg in args))
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetRandomNumber":
            if not callable(context.random_number_query):
                raise UnknownCondition(
                    "Missing transaction-owned native random authority"
                )
            limit = number(args[0])
            exclusions = (
                tuple(number(value) for value in args[1].elts) if len(args) == 2 else ()
            )
            try:
                return context.random_number_query(limit, exclusions)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetDistanceToClosestSpecificArea":
            if not callable(context.closest_specific_area_query):
                raise UnknownCondition("Missing native closest-area authority")
            reference = number(args[1])
            if type(reference) is not int or not -(1 << 63) <= reference < (1 << 63):
                raise UnknownCondition(
                    "Native closest-area reference requires signed long"
                )
            try:
                return context.closest_specific_area_query(
                    args[0].value,
                    reference,
                    run(args[2]),
                    args[3].value if len(args) == 4 else None,
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "NbAreasWithBaseId":
            if not callable(context.areas_base_id_query):
                raise UnknownCondition("Missing native Qs base-area population")
            try:
                return context.areas_base_id_query(
                    literal_long(args[0]), args[1].value if len(args) == 2 else None
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetTeamEffectAreaCountInRange":
            if not callable(context.team_area_range_query):
                raise UnknownCondition("Missing native team-area range authority")
            values = [number(arg) for arg in args[1:]]
            if any(type(v) is not int for v in values):
                raise UnknownCondition("Native team-area range requires long values")
            try:
                return context.team_area_range_query(args[0].value, *values)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name in ("GetSpecificEffectAreaCountInRange", "GetEffectAreaCountInRange"):
            query = (
                context.specific_area_range_query
                if name == "GetSpecificEffectAreaCountInRange"
                else context.area_type_range_query
            )
            if not callable(query):
                raise UnknownCondition("Missing complete native area range authority")
            values = [number(arg) for arg in args[1:4]]
            if any(type(value) is not int for value in values):
                raise UnknownCondition("Native area range requires long values")
            try:
                return query(
                    args[0].value, *values, args[4].value if len(args) == 5 else False
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetTotalHpInPercent":
            from .combat_range_conditions import total_hp_percent

            selector = "target" if args[0].value.lower() == "target" else "caster"
            actor = context.actors.get(selector)
            if actor is None:
                if selector == "target" and context.effect_target_absent is True:
                    return -1.0
                raise UnknownCondition("Missing native total HP actor")
            try:
                return total_hp_percent(
                    actor.characteristics or {}, actor.characteristic_maxima or {}
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetFightersWithBreedInRange":
            if not callable(context.fighters_breed_range_query):
                raise UnknownCondition("Missing complete native breed range authority")
            maximum, breed = number(args[0]), number(args[2])
            if type(maximum) is not int or type(breed) is not int:
                raise UnknownCondition(
                    "Native breed range requires evaluated long values"
                )
            try:
                return context.fighters_breed_range_query(maximum, args[1].value, breed)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetAlliesCount":
            if not callable(context.allies_count_query):
                raise UnknownCondition("Missing complete native allies-count authority")
            try:
                return context.allies_count_query(args[0].value if args else "caster")
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetMonstersInFight":
            if not callable(context.monsters_count_query):
                raise UnknownCondition(
                    "Missing complete native monster-count authority"
                )
            values = [number(argument) for argument in args]
            if any(type(value) is not int for value in values):
                raise UnknownCondition(
                    "Native monster count requires evaluated long arguments"
                )
            try:
                return context.monsters_count_query(*values)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name in (
            "GetEnnemyCountInRange",
            "GetAlliesCountInRange",
            "GetHumanAlliesCountInRange",
            "GetEnemiesHumanCountInRange",
        ):
            query = (
                context.human_enemies_range_query
                if name == "GetEnemiesHumanCountInRange"
                else context.enemy_range_query
                if name == "GetEnnemyCountInRange"
                else (
                    context.human_allies_range_query
                    if name == "GetHumanAlliesCountInRange"
                    else context.allies_range_query
                )
            )
            if not callable(query):
                raise UnknownCondition("Missing complete native enemy range authority")
            minimum = 0 if len(args) < 3 else number(args[0])
            maximum = number(args[0] if len(args) < 3 else args[1])
            if type(minimum) is not int or type(maximum) is not int:
                raise UnknownCondition(
                    "Native enemy range bounds require integral values"
                )
            selector = (
                "caster" if len(args) == 1 else args[1 if len(args) == 2 else 2].value
            )
            try:
                return query(
                    minimum,
                    maximum,
                    selector,
                    run(args[3]) if len(args) > 3 else False,
                    run(args[4]) if len(args) > 4 else False,
                    *([run(args[5])] if len(args) > 5 else []),
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name in ("GetStateCountInRange", "GetOwnTeamStateCountInRange"):
            query = (
                context.own_team_state_range_query
                if name == "GetOwnTeamStateCountInRange"
                else context.state_range_query
            )
            if not callable(query):
                raise UnknownCondition("Missing complete native state range authority")
            maximum = number(args[0])
            if type(maximum) is not int:
                raise UnknownCondition("Native state range requires a long maximum")
            level = -1
            in_play = True
            owner = ""
            if len(args) > 3:
                value = args[3].value
                if type(value) is bool:
                    in_play = value
                elif type(value) is int:
                    level = value
                else:
                    owner = value
            if len(args) == 5:
                owner = args[4].value
            try:
                return query(
                    maximum, args[1].value, args[2].value, level, in_play, owner
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "HasSummonWithBreed":
            if not callable(context.has_summon_breed_query):
                raise UnknownCondition("Missing complete native summon breed authority")
            breed = number(node.args[0])
            try:
                result = context.has_summon_breed_query(breed)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not bool:
                raise UnknownCondition("Invalid native summon breed result")
            return result
        if name == "GetTriggeringEffectCasterIsSameAsCaster":
            if type(context.triggering_caster_is_same) is not bool:
                raise UnknownCondition(
                    "Missing native triggering caster object identity"
                )
            return context.triggering_caster_is_same
        if name == "IsTriggeredByEffectWithREP":
            if context.triggering_effect_present is False:
                return False
            if (
                context.triggering_effect_present is not True
                or context.triggering_effect_flags is None
            ):
                raise UnknownCondition("Missing native source definition REP flags")
            value = number(node.args[0])
            value = (value + (1 << 31)) % (1 << 32) - (1 << 31)  # eOY long->int.
            if value not in (1, 2, 3, 4, 5, 6, *range(8, 38)):
                raise UnknownCondition("Unaudited native REP enum index")
            return value in context.triggering_effect_flags
        if name == "IsTriggeredByMeleeEffect":
            from .combat_trigger_melee import melee_trigger

            return melee_trigger(context)
        if name == "IsTriggeredByIndirectEffect":
            from .combat_trigger_indirect import indirect_trigger

            return indirect_trigger(context)
        if name == "IsTriggeredByZoneEffect":
            if context.triggering_effect_present is False:
                return False
            if (
                context.triggering_effect_present is not True
                or type(context.triggering_zone_effect) is not bool
            ):
                raise UnknownCondition("Missing native source zone definition")
            return context.triggering_zone_effect
        if name in (
            "GetTriggeringContainerStateId",
            "GetTriggeringContainerType",
            "GetTriggeringEffectActionId",
            "GetTriggeringEffectValue",
            "GetTriggeringEffectId",
        ):
            if (
                name in ("GetTriggeringEffectActionId", "GetTriggeringEffectId")
                and args
                and literal_long(args[0]) <= 0
            ):
                return -1  # eLK does not resolve a source for nonpositive depth.
            if type(context.triggering_effect_present) is not bool:
                raise UnknownCondition("Missing native triggering effect presence")
            if not context.triggering_effect_present:
                return (
                    -1
                    if name in ("GetTriggeringEffectActionId", "GetTriggeringEffectId")
                    else 0
                )
            if name == "GetTriggeringEffectId":
                if type(context.triggering_effect_reference_id) is not int:
                    raise UnknownCondition(
                        "Missing native source running-effect definition aZE"
                    )
                return context.triggering_effect_reference_id
            if name == "GetTriggeringContainerType":
                value = context.triggering_container_type
                if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
                    raise UnknownCondition("Missing native source container eVo.aZY")
                return value
            if name == "GetTriggeringEffectValue":
                if type(context.triggering_effect_value) is not int:
                    raise UnknownCondition("Missing native source running-effect value")
                return context.triggering_effect_value
            if name == "GetTriggeringEffectActionId":
                if type(context.triggering_effect_action_id) is not int:
                    raise UnknownCondition("Missing native source effect action awM")
                return context.triggering_effect_action_id
            if type(context.triggering_container_is_state) is not bool:
                raise UnknownCondition("Missing native triggering container kind")
            if not context.triggering_container_is_state:
                return 0
            if type(context.triggering_container_state_id) is not int:
                raise UnknownCondition("Missing native source fyW state reference")
            return context.triggering_container_state_id
        if name == "GetTriggeringApplyStateStateId":
            if context.triggering_effect_present is False:
                return -1
            if context.triggering_effect_present is not True:
                raise UnknownCondition("Missing actual eII.aU source presence")
            if context.triggering_source_is_eWu is False:
                return -1
            if context.triggering_source_is_eWu is not True:
                raise UnknownCondition("Missing actual triggering eWu type")
            value = context.triggering_apply_state_reference
            if type(value) is not int or not -32768 <= value <= 32767:
                raise UnknownCondition("Missing actual eWu.ejo signed-short reference")
            return value
        if (
            name == "GetTriggererEffectCaster"
            and "caster" in context.null_actor_aliases
        ):
            return 0
        if name in (
            "GetEffectTargetOriginalController",
            "GetEffectCasterOriginalController",
        ):
            query = (
                context.effect_target_original_controller_query
                if name == "GetEffectTargetOriginalController"
                else context.effect_caster_original_controller_query
            )
            if not callable(query):
                raise UnknownCondition(
                    "Missing native original target controller authority"
                )
            try:
                value = query()
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
                raise UnknownCondition(
                    "Invalid native original target controller result"
                )
            return value
        if name == "GetDistanceBetweenCasterAndTarget":
            value = context.caster_target_distance
            if type(value) is not int or value < -1:
                raise UnknownCondition("Missing authoritative caster/target distance")
            return value
        if name == "GetFightCurrentTableTurn":
            value = context.fight_current_table_turn
            if type(value) is not int or not -32768 <= value < 32768:
                raise UnknownCondition("Missing authoritative native SU table turn")
            return value
        if name == "GetInstanceId":
            actor = context.actors.get("caster")
            if actor is None or actor.is_native_fighter is False:
                actor = context.actors.get("target")
            if (
                actor is None
                or type(actor.native_instance_id) is not int
                or not -(1 << 63) <= actor.native_instance_id < (1 << 63)
            ):
                raise UnknownCondition(
                    "Missing authoritative native arM instance property"
                )
            return actor.native_instance_id
        if name in ("GetTriggeringEffectCaster", "GetTriggeringEffectTarget"):
            if context.triggering_effect_present is False:
                return -1
            value = (
                context.triggering_effect_caster_id
                if name == "GetTriggeringEffectCaster"
                else context.triggering_effect_target_id
            )
            if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
                raise UnknownCondition("Missing native triggering actor identity")
            return value
        if name == "GetEffectTarget":
            actor = context.actors.get("target")
            if actor is None:
                if context.effect_target_absent is True:
                    return 0
                raise UnknownCondition("Missing native effect target resolution")
            value = actor.actor_id
            if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
                raise UnknownCondition("Missing native effect target identity")
            return value
        if name in ("GetX", "GetY", "GetZ"):
            if not callable(context.coordinate_query):
                raise UnknownCondition("Missing native coordinate authority")
            selector = (
                "target" if args and args[0].value.lower() == "target" else "caster"
            )
            try:
                value = context.coordinate_query(name[-1].lower(), selector)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
                raise UnknownCondition("Invalid native coordinate result")
            return value
        if name == "GetSpellLevel":
            if not callable(context.spell_level_query):
                raise UnknownCondition(
                    "Missing native complete owned spellbook authority"
                )
            reference = number(args[0])
            if type(reference) is not int:
                raise UnknownCondition("Native spell reference requires an integer")
            reference = ((reference + (1 << 31)) % (1 << 32)) - (1 << 31)
            try:
                value = context.spell_level_query(
                    reference, args[1].value if len(args) == 2 else "caster"
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
                raise UnknownCondition("Invalid native spell level result")
            return value
        if name == "GetActiveSpellId":
            if not callable(context.active_spell_id_query):
                raise UnknownCondition("Missing native current active spell authority")
            try:
                return context.active_spell_id_query()
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetContainerLevel":
            if not callable(context.current_container_level_query):
                raise UnknownCondition(
                    "Missing native current running-effect level authority"
                )
            try:
                value = context.current_container_level_query()
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not int or not -32768 <= value <= 32767:
                raise UnknownCondition("Invalid native current eZR.fRR short")
            return value
        if name == "GetRealLevel":
            from .combat_real_level import native_real_level

            try:
                return native_real_level(context, args[0].value if args else None)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "GetTeamId":
            selector = args[0].value.lower() if args else "caster"
            if callable(context.team_id_query):
                try:
                    value = context.team_id_query(selector)
                except ValueError as error:
                    raise UnknownCondition(str(error)) from error
            else:
                actor = context.actors.get(selector)
                if actor is not None:
                    value = actor.fight_affiliation
                elif selector not in (
                    "caster",
                    "target",
                    "castercontroller",
                    "triggeringcaster",
                    "triggeringtarget",
                    "eventtarget",
                ):
                    value = -1
                elif selector == "target" and context.effect_target_absent is True:
                    value = -1
                elif (
                    selector in ("triggeringcaster", "triggeringtarget")
                    and context.triggering_effect_present is False
                ):
                    value = -1
                else:
                    raise UnknownCondition(
                        f"Missing native team actor authority: {selector}"
                    )
            if type(value) is not int or not -128 <= value < 128:
                raise UnknownCondition("Missing native signed-byte bcM affiliation")
            return value
        selector = (
            (args[0].value.lower() if args else "caster")
            if name in ("NbSummons", "GetLevel", "GetTeamId", "GetPhysicalRadius")
            else (args[1].value.lower() if len(args) == 2 else "caster")
        )
        actor = context.actors.get(selector)
        if actor is None:
            if (
                name in ("GetCharacInPct", "GetCharacPct", "GetCharacteristicPct")
                and selector == "target"
                and context.effect_target_absent is True
            ):
                return -1.0  # Native eJz: an authoritatively absent eHg.
            raise UnknownCondition(f"Missing native actor: {selector}")
        if name in ("GetEffectCaster", "GetTriggererEffectCaster"):
            value = actor.actor_id
            if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
                raise UnknownCondition("Missing native effect caster identity")
            return value
        if name == "GetPhysicalRadius":
            value = actor.physical_radius
            if type(value) is not int or not -128 <= value < 128:
                raise UnknownCondition("Missing native signed-byte physical radius")
            return value
        if name == "GetTeamId":
            value = actor.fight_affiliation
            if type(value) is not int or not -128 <= value < 128:
                raise UnknownCondition("Missing native signed-byte bcM affiliation")
            return value
        if name == "GetLevel":
            if actor.effective_level is None:
                raise UnknownCondition("Missing authoritative eGj.cmZ actor level")
            return actor.effective_level
        if name == "GetStateLevel":
            if actor.state_levels is None:
                raise UnknownCondition("Missing native ordered state levels")
            return next(
                (
                    level
                    for reference, level in actor.state_levels
                    if reference == args[0].value
                ),
                -1,
            )
        if name == "NbSummons":
            if len(args) == 2:
                # ePs evaluates alP as long, then l2i before eHg.GF(int).
                breed = ((literal_long(args[1]) + (1 << 31)) % (1 << 32)) - (1 << 31)
                if breed == -1:  # eGE.pIq.aXA(): native NONE wildcard.
                    if actor.summon_count is None:
                        raise UnknownCondition("Missing native summon count")
                    return actor.summon_count
                if actor.summon_counts_by_breed is None or (
                    breed not in actor.summon_counts_by_breed
                    and actor.summon_counts_complete is not True
                ):
                    raise UnknownCondition("Missing native filtered summon count")
                return actor.summon_counts_by_breed.get(breed, 0)
            if actor.summon_count is None:
                raise UnknownCondition("Missing native summon count")
            return actor.summon_count
        characteristic = aliases[args[0].value.upper()]
        if actor.characteristics is None or characteristic not in actor.characteristics:
            raise UnknownCondition(f"Missing native characteristic: {characteristic}")
        value = actor.characteristics[characteristic]
        if value is None:
            return -1  # Authoritatively absent native PC, not absent knowledge.
        if name in ("GetCharac", "GetCharacteristic"):
            return value
        if name in ("GetCharacMax", "GetCharacteristicMax"):
            if (
                actor.characteristic_maxima is None
                or characteristic not in actor.characteristic_maxima
            ):
                raise UnknownCondition("Missing native characteristic maximum")
            return actor.characteristic_maxima[characteristic]
        if (
            actor.characteristic_maxima is None
            or characteristic not in actor.characteristic_maxima
        ):
            raise UnknownCondition("Missing native characteristic maximum")
        maximum = actor.characteristic_maxima[characteristic]
        from .combat_characteristic_percentage import characteristic_percentage

        try:
            return characteristic_percentage(value, maximum)
        except ValueError as error:
            raise UnknownCondition(str(error)) from error

    def check(node):
        if isinstance(node, ast.IfExp):
            check(node.test)
            check(node.body)
            check(node.orelse)
            return
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or not isinstance(
                node.ops[0], (ast.Eq, ast.NotEq, ast.GtE, ast.Gt, ast.LtE, ast.Lt)
            ):
                raise UnknownCondition("Unsupported native numeric comparison")
            check_number(node.left)
            check_number(node.comparators[0])
            return
        if isinstance(node, ast.Constant) and type(node.value) is bool:
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            check(node.operand)
            return
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for value in node.values:
                check(value)
            return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name == "IsSpecific":
                name = "IsSpecificArea"  # eQb lexical aliases share one token.
            args = node.args
            if name in ("IsPvp", "GetBooleanSystemConfiguration"):
                check_number(node)
                return
            if name in ("IsActivatedByElement", "IsActivatedBySpell"):
                if (name == "IsActivatedByElement" and len(args) != 1) or len(args) > 1:
                    raise UnknownCondition("Unsupported native activation signature")
                if args:
                    literal_long(args[0])
                return
            if name in ("IsTriggeringEffectCritical", "IsTriggeringEffectBlocked"):
                if args:
                    raise UnknownCondition("Native source predicate takes no arguments")
                return
            if name == "HasBreedInSymbiot":
                if len(args) != 2:
                    raise UnknownCondition(
                        "Native HasBreedInSymbiot requires profile and selector"
                    )
                check_number(args[0])
                if (
                    not isinstance(args[1], ast.Constant)
                    or type(args[1].value) is not str
                ):
                    raise UnknownCondition(
                        "Native symbiot selector requires literal string"
                    )
                return
            if name in (
                "UseGateEffect",
                "UseGateTriggeringEffect",
                "IsOriginalController",
                "CasterAndTargetHaveSameOriginalController",
                "IsSelectedCreatureAvailable",
            ):
                if args:
                    raise UnknownCondition("Native " + name + " takes no arguments")
                return
            if name == "HasValidGateForTp":
                if (
                    len(args) != 3
                    or not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                ):
                    raise UnknownCondition("Unsupported native valid-gate signature")
                check_number(args[1])
                check_number(args[2])
                return
            if (
                name
                not in (
                    "HasState",
                    "HasStateFromLevel",
                    "HasStateFromUser",
                    "IsSpellInDeck",
                    "IsCarried",
                    "IsCarrying",
                    "IsBackstabbed",
                    "IsFacestabbed",
                    "IsSidestabbed",
                    "IsSex",
                    "IsTargetCellFree",
                    "IsBreedId",
                    "IsBreed",
                    "IsInAlignment",
                    "IsInDiagonal",
                    "IsOnBorderCell",
                    "HasLineOfSight",
                    "IsOffPlay",
                    "IsDead",
                    "IsInPlay",
                    "IsEnemy",
                    "IsEnnemy",
                    "HasFightProperty",
                    "HasWorldProperty",
                    "IsOwnSummon",
                    "IsSummon",
                    "IsSummonedFromSymbiot",
                    "HasSummonWithBreed",
                    "HasEffectWithSpecificId",
                    "HasEffectWithActionId",
                    "IsInFight",
                    "IsCharacter",
                    "IsPlayer",
                    "IsChallenger",
                    "IsObstacle",
                    "IsOnEffectAreaType",
                    "CellContainsEffectAreaType",
                    "CellContainsSpecificEffectArea",
                    "IsOwnSpecificArea",
                    "IsAreaType",
                    "IsSpecificArea",
                    "IsOwnDeposit",
                    "IsOwnArea",
                    "IsFreeCell",
                    "HasFreeSurroundingCell",
                    "IsControlledByAI",
                    "HasSurroundingCellWithOwnSummon",
                    "IsOnSpecificEffectArea",
                    "IsTriggeredByMeleeEffect",
                    "IsTriggeredByZoneEffect",
                    "IsTriggeredByIndirectEffect",
                    "IsTriggeredByEffectWithREP",
                    "GetTriggeringEffectCasterIsSameAsCaster",
                    "HasActiveCosmeticId",
                )
                or node.keywords
            ):
                raise UnknownCondition(f"Unsupported native predicate: {name}")
            if name == "HasSurroundingCellWithOwnSummon":
                if (
                    len(args) not in (2, 3)
                    or not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                ):
                    raise UnknownCondition(
                        "Unsupported native surrounding-summon signature"
                    )
                if isinstance(args[1], ast.Constant) and type(args[1].value) is str:
                    if len(args) != 2:
                        raise UnknownCondition(
                            "Unsupported native neighborhood mode signature"
                        )
                else:
                    literal_long(args[1])
                    if len(args) == 3 and not (
                        isinstance(args[2], ast.Constant) and type(args[2].value) is str
                    ):
                        raise UnknownCondition(
                            "Native neighborhood mode requires literal string"
                        )
                return
            if name == "HasActiveCosmeticId":
                if len(args) != 2:
                    raise UnknownCondition(
                        "Native HasActiveCosmeticId requires category and id"
                    )
                check_number(args[0])
                check_number(args[1])
                return
            if name == "HasFreeSurroundingCell":
                if len(args) > 2 or any(
                    not isinstance(arg, ast.Constant) or type(arg.value) is not bool
                    for arg in args
                ):
                    raise UnknownCondition(
                        "Native free-surrounding predicate requires literal booleans"
                    )
                return
            if name == "IsControlledByAI":
                if (
                    len(args) != 1
                    or not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                ):
                    raise UnknownCondition(
                        "Native IsControlledByAI requires one literal string"
                    )
                return
            if name == "IsFreeCell":
                if (
                    len(args) != 3
                    or not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                ):
                    raise UnknownCondition(
                        "Native IsFreeCell requires string and two constructor constants"
                    )
                literal_long(args[1])
                literal_long(args[2])
                return
            if name == "HasSummonWithBreed":
                if len(args) != 1:
                    raise UnknownCondition(
                        "Native HasSummonWithBreed requires one long"
                    )
                check_number(args[0])
                return
            if name in ("IsAreaType", "IsSpecificArea"):
                if len(args) != 1:
                    raise UnknownCondition("Native area identity requires one long")
                check_number(args[0])
                return
            if name in ("IsOwnDeposit", "IsOwnArea"):
                if (
                    len(args) > 1
                    or args
                    and not (
                        isinstance(args[0], ast.Constant)
                        and type(args[0].value) is bool
                    )
                ):
                    raise UnknownCondition(
                        "Native own-deposit requires optional literal boolean"
                    )
                return
            if name == "IsTriggeredByEffectWithREP":
                if len(args) != 1:
                    raise UnknownCondition("Native source REP requires one long")
                check_number(args[0])
                return
            if name in (
                "IsTriggeredByMeleeEffect",
                "IsTriggeredByZoneEffect",
                "IsTriggeredByIndirectEffect",
                "IsTriggeredByEffectWithREP",
                "GetTriggeringEffectCasterIsSameAsCaster",
            ):
                if args:
                    raise UnknownCondition("Native zone trigger takes no arguments")
                return
            if name == "IsPlayer":
                if (
                    len(args) > 1
                    or args
                    and not (
                        isinstance(args[0], ast.Constant) and type(args[0].value) is str
                    )
                ):
                    raise UnknownCondition(
                        "IsPlayer requires zero or one native string selector"
                    )
                return
            if name in ("IsInFight", "IsCharacter", "IsChallenger"):
                if len(args) > 1 or args and not is_selector(args[0]):
                    raise UnknownCondition("Unsupported native IsInFight selector")
                return
            if name == "HasEffectWithActionId":
                if len(args) != 2 or not is_selector(args[0]):
                    raise UnknownCondition(
                        "Unsupported native action-presence arguments"
                    )
                check_number(args[1])
                return
            if name == "HasEffectWithSpecificId":
                if (
                    len(args) != 2
                    or not is_selector(args[0])
                    or not isinstance(args[1], ast.Constant)
                    or type(args[1].value) is not int
                ):
                    raise UnknownCondition(
                        "Unsupported native effect-presence arguments"
                    )
                return
            if name == "HasWorldProperty":
                if len(args) not in (1, 2):
                    raise UnknownCondition(
                        "Unsupported native world property signature"
                    )
                literal_long(args[0])
                if len(args) == 2 and not (
                    isinstance(args[1], ast.Constant) and type(args[1].value) is str
                ):
                    literal_long(args[1])
                return
            if name in ("IsSummon", "IsSummonedFromSymbiot"):
                if (
                    len(args) != 1
                    or not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                ):
                    raise UnknownCondition(
                        name + " requires one native string selector"
                    )
                return
            if name == "IsOwnSummon":
                if not (
                    not args
                    or len(args) == 1
                    and (
                        isinstance(args[0], ast.Constant)
                        and type(args[0].value) is str
                        or isinstance(args[0], ast.Constant)
                        and type(args[0].value) is int
                    )
                    or len(args) == 2
                    and isinstance(args[0], ast.Constant)
                    and type(args[0].value) is int
                    and isinstance(args[1], ast.Constant)
                    and type(args[1].value) is str
                ):
                    raise UnknownCondition("Unsupported native IsOwnSummon arguments")
                return
            args = node.args
            if name == "HasFightProperty":
                if not (
                    len(args) == 1
                    and isinstance(args[0], ast.Constant)
                    and type(args[0].value) is int
                    or len(args) == 2
                    and is_selector(args[0])
                    and isinstance(args[1], ast.Constant)
                    and type(args[1].value) is int
                ):
                    raise UnknownCondition(
                        "Unsupported native HasFightProperty arguments"
                    )
                return
            if name in ("IsEnemy", "IsEnnemy"):
                if args:
                    raise UnknownCondition("Native IsEnemy takes no arguments")
                return
            if name in ("IsOffPlay", "IsDead", "IsInPlay"):
                if len(args) > 1 or (
                    args
                    and (
                        not isinstance(args[0], ast.Constant)
                        or type(args[0].value) is not str
                    )
                ):
                    raise UnknownCondition(f"Unsupported native {name} signature")
                return
            if name == "HasLineOfSight":
                if args:
                    raise UnknownCondition("Native HasLineOfSight takes no arguments")
                return
            if name in ("IsInAlignment", "IsInDiagonal"):
                if args:
                    raise UnknownCondition(f"Unsupported {name} arguments")
                return
            if name == "IsOnBorderCell":
                if (
                    len(args) != 1
                    or not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                ):
                    raise UnknownCondition(
                        "Native IsOnBorderCell requires exactly one string selector"
                    )
                return
            if name == "IsOwnSpecificArea":
                if len(args) not in (1, 2):
                    raise UnknownCondition("Unsupported native owned-area signature")
                literal_long(args[0])
                if len(args) == 2 and (
                    not isinstance(args[1], ast.Constant)
                    or type(args[1].value) is not str
                ):
                    raise UnknownCondition(
                        "Native owned-area selector requires a string"
                    )
                return
            if name == "IsObstacle":
                if len(args) > 1 or (
                    args
                    and (
                        not isinstance(args[0], ast.Constant)
                        or type(args[0].value) is not str
                    )
                ):
                    raise UnknownCondition("Unsupported native IsObstacle selector")
                return
            if name == "IsOnEffectAreaType":
                if (
                    len(args) not in (2, 3)
                    or not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                ):
                    raise UnknownCondition("Unsupported native actor-area signature")
                check_number(args[1])
                if len(args) == 3 and (
                    not isinstance(args[2], ast.Constant)
                    or type(args[2].value) is not bool
                ):
                    raise UnknownCondition(
                        "Native area ownership requires literal alu boolean"
                    )
                return
            if name == "IsOnSpecificEffectArea":
                if len(args) not in (2, 3) or not (
                    isinstance(args[0], ast.Constant) and type(args[0].value) is str
                ):
                    raise UnknownCondition(
                        "Unsupported native specific actor-area signature"
                    )
                check_number(args[1])
                if len(args) == 3 and not (
                    isinstance(args[2], ast.Constant)
                    and type(args[2].value) in (bool, str)
                ):
                    raise UnknownCondition(
                        "Native actor-area ownership requires literal boolean/string"
                    )
                return
            if name in ("CellContainsEffectAreaType", "CellContainsSpecificEffectArea"):
                if len(args) not in (1, 2):
                    raise UnknownCondition("Unsupported native cell area signature")
                check_number(args[0])
                if len(args) == 2:
                    if (
                        not isinstance(args[1], ast.Constant)
                        or type(args[1].value) is not bool
                    ):
                        raise UnknownCondition(
                            "Native area ownership flag requires literal alu boolean"
                        )
                return
            if name == "IsBreed":
                if not args or any(
                    not isinstance(arg, ast.Constant) or type(arg.value) is not str
                    for arg in args
                ):
                    raise UnknownCondition("Native IsBreed requires string arguments")
                return
            if name == "IsBreedId":
                if (
                    len(args) < 2
                    or not is_state_actor_selector(args[0])
                    or any(
                        not isinstance(a, ast.Constant) or type(a.value) is not int
                        for a in args[1:]
                    )
                ):
                    raise UnknownCondition("Unsupported IsBreedId arguments")
                return
            if name == "IsTargetCellFree":
                if len(args) > 1 or (
                    args
                    and (
                        not isinstance(args[0], ast.Constant)
                        or type(args[0].value) is not bool
                    )
                ):
                    raise UnknownCondition("Unsupported IsTargetCellFree arguments")
                return
            if name == "IsSex":
                if len(args) not in (1, 2) or any(
                    not isinstance(arg, ast.Constant) or type(arg.value) is not str
                    for arg in args
                ):
                    raise UnknownCondition("Unsupported IsSex arguments")
                return
            if name in (
                "IsCarrying",
                "IsBackstabbed",
                "IsFacestabbed",
                "IsSidestabbed",
            ):
                if len(args) > 1 or (
                    args
                    and (
                        not isinstance(args[0], ast.Constant)
                        or type(args[0].value) is not str
                    )
                ):
                    raise UnknownCondition(f"Unsupported {name} selector")
                return
            if name == "IsCarried":
                if len(args) > 1 or (
                    args
                    and (
                        not isinstance(args[0], ast.Constant)
                        or type(args[0].value) is not str
                        or args[0].value.lower() not in ("caster", "target")
                    )
                ):
                    raise UnknownCondition("Unsupported IsCarried selector")
                return
            if (
                name in ("HasState", "HasStateFromLevel")
                and len(args) in (2, 3)
                and isinstance(args[1], ast.Constant)
                and type(args[1].value) is int
            ):
                if (
                    not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not int
                ):
                    raise UnknownCondition("Unsupported HasState identity")
                if len(args) == 3 and not is_state_actor_selector(args[2]):
                    raise UnknownCondition("Unsupported HasState actor selector")
                return
            if (
                not 1 <= len(args) <= 2
                or not isinstance(args[0], ast.Constant)
                or type(args[0].value) is not int
            ):
                raise UnknownCondition(f"Unsupported {name} arguments")
            if len(args) == 2 and (
                not isinstance(args[1], ast.Constant)
                or type(args[1].value) is not str
                or args[1].value.lower()
                not in (
                    ("caster", "target", "castercontroller")
                    if name == "IsSpellInDeck"
                    else (
                        (
                            "caster",
                            "target",
                            "triggeringcaster",
                            "triggeringtarget",
                            "castercontroller",
                        )
                        if name in ("HasState", "HasStateFromLevel", "HasStateFromUser")
                        else ("caster", "target")
                    )
                )
            ):
                raise UnknownCondition(f"Unsupported {name} actor selector")
            return
        raise UnknownCondition(f"Unsupported native expression: {ast.dump(node)}")

    def run(node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("IsPvp", "GetBooleanSystemConfiguration")
        ):
            return number(node) == 0
        if isinstance(node, ast.IfExp):
            return run(node.body if run(node.test) else node.orelse)
        if isinstance(node, ast.Compare):
            left, right = number(node.left), number(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            if isinstance(op, ast.GtE):
                return left >= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.LtE):
                return left <= right
            return left < right
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp):
            return not run(node.operand)
        if isinstance(node, ast.BoolOp):
            return (
                all(run(v) for v in node.values)
                if isinstance(node.op, ast.And)
                else any(run(v) for v in node.values)
            )
        name = node.func.id
        if name == "IsSpecific":
            name = "IsSpecificArea"  # Preserve the same area authority callback.
        if name == "HasActiveCosmeticId":
            if not callable(context.has_active_cosmetic_query):
                raise UnknownCondition(
                    "Missing native active cosmetic membership authority"
                )
            category, cosmetic_id = (number(argument) for argument in node.args)
            try:
                result = context.has_active_cosmetic_query(category, cosmetic_id)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not bool:
                raise UnknownCondition("Invalid native active cosmetic membership")
            return result
        if name in ("IsActivatedByElement", "IsActivatedBySpell"):
            if not callable(context.activation_query):
                raise UnknownCondition(
                    "Missing actual native current activation authority"
                )
            argument = -1 if not node.args else literal_long(node.args[0])
            argument = (argument + (1 << 31)) % (1 << 32) - (1 << 31)
            try:
                result = context.activation_query(name, argument)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not bool:
                raise UnknownCondition("Invalid native activation result")
            return result
        if name in ("IsTriggeringEffectCritical", "IsTriggeringEffectBlocked"):
            from .combat_activation_conditions import evaluate_source_predicate

            try:
                return evaluate_source_predicate(name, context)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "HasBreedInSymbiot":
            if not callable(context.breed_in_symbiot_query):
                raise UnknownCondition("Missing native eMd owned roster authority")
            try:
                result = context.breed_in_symbiot_query(
                    number(node.args[0]), run(node.args[1]).strip()
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not bool:
                raise UnknownCondition("Invalid native eMd profile presence result")
            return result
        if name == "IsSelectedCreatureAvailable":
            if not callable(context.selected_creature_available_query):
                raise UnknownCondition("Missing native eHP captured roster authority")
            try:
                result = context.selected_creature_available_query()
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not int or result not in (-2, -1, 0):
                raise UnknownCondition("Invalid native eON availability status")
            return result == 0
        if name in (
            "UseGateEffect",
            "UseGateTriggeringEffect",
            "IsOriginalController",
            "CasterAndTargetHaveSameOriginalController",
        ):
            query = (
                context.use_gate_effect_query
                if name == "UseGateEffect"
                else context.use_gate_triggering_effect_query
                if name == "UseGateTriggeringEffect"
                else context.original_controller_predicate_query
            )
            if not callable(query):
                raise UnknownCondition("Missing native " + name + " authority")
            try:
                result = query() if name.startswith("UseGate") else query(name)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not bool:
                raise UnknownCondition("Invalid native " + name + " result")
            return result
        if name == "IsSex":
            selector = (
                "target"
                if len(node.args) == 2 and node.args[1].value.lower() == "target"
                else "caster"
            )
            actor = context.actors.get(selector)
            if actor is None:
                if selector in context.null_actor_aliases or (
                    selector == "target" and context.effect_target_absent is True
                ):
                    return False
                raise UnknownCondition("Missing native eOO selected eGj authority")
            if actor.is_native_fighter is False:
                return False
            if actor.is_native_fighter is not True:
                raise UnknownCondition("Missing native eII.a eGj type")
            if type(actor.native_sex) is not int or not -128 <= actor.native_sex <= 127:
                raise UnknownCondition("Missing native eGj.aXz sex byte")
            expected = 0 if node.args[0].value.lower() == "male" else 1
            return actor.native_sex == expected
        if name in ("IsBackstabbed", "IsFacestabbed", "IsSidestabbed"):
            query = (
                context.backstabbed_query
                if name == "IsBackstabbed"
                else context.facestabbed_query
                if name == "IsFacestabbed"
                else context.sidestabbed_query
            )
            if not callable(query):
                raise UnknownCondition("Missing native facing authority")
            selector = (
                "target"
                if node.args and node.args[0].value.lower() == "target"
                else "caster"
            )
            try:
                value = query(selector)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not bool:
                raise UnknownCondition("Invalid native facing result")
            return value
        if name == "HasValidGateForTp":
            if not callable(context.valid_gate_for_tp_query):
                raise UnknownCondition("Missing native valid-gate predicate authority")
            bounds = [number(arg) for arg in node.args[1:]]
            if any(
                type(v) is not int or not -(1 << 63) <= v < (1 << 63) for v in bounds
            ):
                raise UnknownCondition("Native gate bounds require signed long")
            try:
                result = context.valid_gate_for_tp_query(node.args[0].value, *bounds)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not bool:
                raise UnknownCondition("Invalid native valid-gate result")
            return result
        if name == "HasSummonWithBreed":
            if not callable(context.has_summon_breed_query):
                raise UnknownCondition("Missing complete native summon breed authority")
            breed = number(node.args[0])
            try:
                result = context.has_summon_breed_query(breed)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(result) is not bool:
                raise UnknownCondition("Invalid native summon breed result")
            return result
        if name == "GetTriggeringEffectCasterIsSameAsCaster":
            if type(context.triggering_caster_is_same) is not bool:
                raise UnknownCondition(
                    "Missing native triggering caster object identity"
                )
            return context.triggering_caster_is_same
        if name == "IsTriggeredByEffectWithREP":
            if context.triggering_effect_present is False:
                return False
            if (
                context.triggering_effect_present is not True
                or context.triggering_effect_flags is None
            ):
                raise UnknownCondition("Missing native source definition REP flags")
            value = number(node.args[0])
            value = (value + (1 << 31)) % (1 << 32) - (1 << 31)  # eOY long->int.
            if value not in (1, 2, 3, 4, 5, 6, *range(8, 38)):
                raise UnknownCondition("Unaudited native REP enum index")
            return value in context.triggering_effect_flags
        if name == "IsTriggeredByMeleeEffect":
            from .combat_trigger_melee import melee_trigger

            return melee_trigger(context)
        if name == "IsTriggeredByIndirectEffect":
            from .combat_trigger_indirect import indirect_trigger

            return indirect_trigger(context)
        if name == "IsTriggeredByZoneEffect":
            if context.triggering_effect_present is False:
                return False
            if (
                context.triggering_effect_present is not True
                or type(context.triggering_zone_effect) is not bool
            ):
                raise UnknownCondition("Missing native source zone definition")
            return context.triggering_zone_effect
        if name == "IsSummonedFromSymbiot":
            selector = "target" if node.args[0].value.lower() == "target" else "caster"
            actor = context.actors.get(selector)
            if actor is None:
                if selector == "target" and context.effect_target_absent is True:
                    return False
                raise UnknownCondition("Missing native eOU selected eHg authority")
            if actor.is_native_ehg is not True:
                raise UnknownCondition("Missing native eII.b fallback eHg authority")
            if type(actor.is_summoned_from_symbiot) is not bool:
                raise UnknownCondition("Missing native eHg.dTC symbiot status")
            return actor.is_summoned_from_symbiot
        if name == "IsSummon":
            selector = node.args[0].value.lower()
            # eII.a unrecognised string -> null -> eOT.a=-1 (false).
            if selector not in (
                "caster",
                "target",
                "castercontroller",
                "triggeringcaster",
                "triggeringtarget",
                "eventtarget",
            ):
                return False
            actor = context.actors.get(selector)
            if actor is None:
                if selector == "target" and context.effect_target_absent is True:
                    return False
                if (
                    selector in ("triggeringcaster", "triggeringtarget")
                    and context.triggering_effect_present is False
                ):
                    return False
                raise UnknownCondition(
                    f"Missing native summon actor authority: {selector}"
                )
            if type(actor.is_summon) is not bool:
                raise UnknownCondition(f"Missing native dTE summon status: {selector}")
            return actor.is_summon
        if name == "IsPlayer":
            selector = node.args[0].value.lower() if node.args else "target"
            if selector not in (
                "caster",
                "target",
                "castercontroller",
                "triggeringcaster",
                "triggeringtarget",
                "eventtarget",
            ):
                return False
            actor = context.actors.get(selector)
            if actor is None:
                if selector == "target" and context.effect_target_absent is True:
                    return False
                if (
                    selector in ("triggeringcaster", "triggeringtarget")
                    and context.triggering_effect_present is False
                ):
                    return False
                raise UnknownCondition("Missing native PLAYER actor authority")
            if type(actor.is_player) is not bool:
                raise UnknownCondition("Missing native PLAYER kind")
            return actor.is_player
        if name == "IsChallenger":
            # eNC defaults to target, unlike IsCharacter's caster default.
            actor = context.actors.get(
                node.args[0].value.lower() if node.args else "target"
            )
            if actor is None or type(actor.is_challenger) is not bool:
                raise UnknownCondition("Missing native PLAYER_CHARACTER/COMPANION kind")
            return actor.is_challenger
        if name == "IsCharacter":
            selector = node.args[0].value.lower() if node.args else "caster"
            actor = context.actors.get(selector)
            if actor is None and selector in context.null_actor_aliases:
                return False  # eND selected eHg null -> -1.
            if actor is None or type(actor.is_character) is not bool:
                raise UnknownCondition("Missing native CHARACTER kind")
            return actor.is_character
        if name == "IsInFight":
            actor = context.actors.get(
                node.args[0].value.lower() if node.args else "caster"
            )
            if actor is None or type(actor.in_fight) is not bool:
                raise UnknownCondition("Missing authoritative native fight membership")
            return actor.in_fight
        if name == "HasEffectWithActionId":
            actor = context.actors.get(node.args[0].value.lower())
            identity = ((int(number(node.args[1])) + (1 << 31)) % (1 << 32)) - (1 << 31)
            if actor is None:
                if (
                    node.args[0].value.lower() == "target"
                    and context.effect_target_absent is True
                ):
                    return False
                raise UnknownCondition("Missing native action-presence actor")
            if actor.is_native_fighter is False:
                return False
            if actor.retained_action_ids is None:
                raise UnknownCondition(
                    "Missing complete native retained action population"
                )
            return identity in actor.retained_action_ids
        if name == "HasEffectWithSpecificId":
            selector = node.args[0].value.lower()
            actor = context.actors.get(selector)
            if actor is None:
                if selector == "target" and context.effect_target_absent is True:
                    return False
                raise UnknownCondition("Missing native effect-presence actor")
            if actor.is_native_ehg is False:
                return False
            if actor.retained_effect_ids is None:
                raise UnknownCondition(
                    "Missing complete native retained effect population"
                )
            identity = ((node.args[1].value + (1 << 31)) % (1 << 32)) - (1 << 31)
            return identity in actor.retained_effect_ids
        if name == "IsOwnSummon":
            args = [a.value for a in node.args]
            breed = (
                ((args[0] + 32768) % 65536) - 32768
                if args and type(args[0]) is int
                else 0
            )
            selector = next((a.lower() for a in args if type(a) is str), "target")
            source = context.actors.get("caster")
            target = context.actors.get(selector)
            if callable(context.own_summon_actor_query):
                try:
                    target = context.own_summon_actor_query(selector)
                except ValueError as error:
                    raise UnknownCondition(str(error)) from error
                if target is None:
                    return False  # eOG known null eII actor returns -1.
            if source is None:
                raise UnknownCondition("Missing native own-summon caster")
            if target is None:
                raise UnknownCondition(
                    "Missing native own-summon target; cell fallback is not attested"
                )
            if target.is_native_fighter is None:
                raise UnknownCondition("Missing native target eGj identity")
            if not target.is_native_fighter:
                return False
            if breed:
                if target.breed_id is None:
                    raise UnknownCondition("Missing native summon breed")
                if target.breed_id != breed:
                    return False
            if target.is_summon is None:
                raise UnknownCondition("Missing native dTE summon status")
            if not target.is_summon:
                return False
            if source.summon_root_id is None or target.summon_root_id is None:
                raise UnknownCondition("Missing native fqK root identity")
            return source.summon_root_id == target.summon_root_id
        if name == "HasSurroundingCellWithOwnSummon":
            if not callable(context.surrounding_own_summon_query):
                raise UnknownCondition("Missing native surrounding-summon authority")
            mode_only = (
                isinstance(node.args[1], ast.Constant)
                and type(node.args[1].value) is str
            )
            breed = -1 if mode_only else literal_long(node.args[1])
            mode = (
                node.args[1].value
                if mode_only
                else node.args[2].value
                if len(node.args) == 3
                else "VON_NEUMANN"
            )
            try:
                result = context.surrounding_own_summon_query(
                    node.args[0].value, breed, mode
                )
                if type(result) is not bool:
                    raise ValueError("Missing native neighborhood boolean")
                return result
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "IsControlledByAI":
            if not callable(context.controlled_by_ai_query):
                raise UnknownCondition("Missing native AI-control authority")
            try:
                result = context.controlled_by_ai_query(node.args[0].value)
                if type(result) is not bool:
                    raise ValueError("Missing native AI-control boolean")
                return result
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "HasFreeSurroundingCell":
            if not callable(context.free_surrounding_cell_query):
                raise UnknownCondition("Missing native free-surrounding cell authority")
            try:
                result = context.free_surrounding_cell_query(
                    node.args[0].value if node.args else False,
                    node.args[1].value if len(node.args) == 2 else True,
                )
                if type(result) is not bool:
                    raise ValueError("Missing native free-surrounding boolean")
                return result
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "IsFreeCell":
            if not callable(context.free_cell_query):
                raise UnknownCondition("Missing native rotated free-cell authority")
            try:
                result = context.free_cell_query(
                    node.args[0].value,
                    literal_long(node.args[1]),
                    literal_long(node.args[2]),
                )
                if type(result) is not bool:
                    raise ValueError("Missing native free-cell boolean")
                return result
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "IsOnSpecificEffectArea":
            if not callable(context.actor_specific_area_query):
                raise UnknownCondition("Missing native specific actor-area authority")
            try:
                return context.actor_specific_area_query(
                    node.args[0].value,
                    number(node.args[1]),
                    node.args[2].value if len(node.args) == 3 else False,
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name in ("IsAreaType", "IsSpecificArea", "IsOwnDeposit", "IsOwnArea"):
            if not callable(context.area_identity_query):
                raise UnknownCondition("Missing native area identity target authority")
            value = (
                (node.args[0].value if node.args else False)
                if name in ("IsOwnDeposit", "IsOwnArea")
                else number(node.args[0])
            )
            try:
                result = context.area_identity_query(name, value)
                if type(result) is not bool:
                    raise ValueError("Missing native area identity boolean result")
                return result
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "IsOwnSpecificArea":
            if not callable(context.own_specific_area_query):
                raise UnknownCondition("Missing native owned-area authority")
            try:
                return context.own_specific_area_query(
                    literal_long(node.args[0]),
                    node.args[1].value if len(node.args) == 2 else "target",
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "IsObstacle":
            if not callable(context.actor_obstacle_query):
                raise UnknownCondition("Missing complete native QI obstacle authority")
            try:
                return context.actor_obstacle_query(
                    node.args[0].value if node.args else "caster"
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "IsOnEffectAreaType":
            if not callable(context.actor_area_type_query):
                raise UnknownCondition("Missing complete native actor-area authority")
            kind = number(node.args[1])
            if type(kind) is not int:
                raise UnknownCondition("Native actor-area type requires a long")
            try:
                return context.actor_area_type_query(
                    node.args[0].value,
                    kind,
                    node.args[2].value if len(node.args) == 3 else False,
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name in ("CellContainsEffectAreaType", "CellContainsSpecificEffectArea"):
            query = (
                context.cell_area_type_query
                if name == "CellContainsEffectAreaType"
                else context.cell_specific_area_query
            )
            if not callable(query):
                raise UnknownCondition("Missing native cell effect-area authority")
            kind = number(node.args[0])
            if type(kind) is not int:
                raise UnknownCondition("Native area type requires a long")
            second = node.args[1] if len(node.args) == 2 else None
            restrict = False if second is None else second.value
            try:
                return query(kind, restrict)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "HasWorldProperty":
            from .combat_world_properties import has_world_property

            second = node.args[1] if len(node.args) == 2 else None
            selector = (
                "target"
                if second is not None
                and isinstance(second, ast.Constant)
                and type(second.value) is str
                and second.value.lower() == "target"
                else "caster"
            )
            actor = context.actors.get(selector)
            if actor is None:
                if selector == "target" and context.effect_target_absent is True:
                    return False
                raise UnknownCondition("Missing native world property actor")
            duration = (
                literal_long(second)
                if second is not None
                and not (isinstance(second, ast.Constant) and type(second.value) is str)
                else None
            )
            try:
                return has_world_property(
                    actor,
                    literal_long(node.args[0]),
                    duration_seconds=duration,
                    now_ms=context.world_property_now_ms,
                )
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
        if name == "HasFightProperty":
            selector = node.args[0].value.lower() if len(node.args) == 2 else "caster"
            identity = (node.args[-1].value + 128) % 256 - 128
            # Native ffe.values IDs, with gaps13/53/89; eMo narrows its argument to byte.
            if identity not in set(range(123)) - {13, 53, 89}:
                return False
            actor = context.actors.get(selector)
            if actor is None and selector in context.null_actor_aliases:
                return False  # eMo receives the proven null eII.b result.
            if actor is None or actor.fight_properties is None:
                raise UnknownCondition("Missing native PV fight properties")
            return identity in actor.fight_properties
        if name in ("IsEnemy", "IsEnnemy"):
            # eNM.a returns0 for a literal null target; amb.b treats0 as true.
            if context.enemy_target_kind == "null":
                return True
            source = context.actors.get("caster")
            if source is None or type(source.fight_affiliation) is not int:
                raise UnknownCondition("Missing native caster bcM affiliation")
            if context.enemy_target_kind == "cell":
                affiliations = context.enemy_cell_affiliations
                if affiliations is None and callable(
                    context.enemy_cell_affiliations_query
                ):
                    try:
                        affiliations = context.enemy_cell_affiliations_query()
                    except ValueError as error:
                        raise UnknownCondition(str(error)) from error
                if affiliations is None:
                    raise UnknownCondition(
                        "Missing native cell occupant/obstacle affiliations"
                    )
                if not isinstance(affiliations, tuple) or any(
                    type(team) is not int or not -128 <= team <= 127
                    for team in affiliations
                ):
                    raise UnknownCondition("Invalid native enemy cell affiliations")
                return any(team != source.fight_affiliation for team in affiliations)
            if context.enemy_target_kind == "other":
                return False  # eNM's proven non-eHg/non-aBn target returns -2.
            if context.enemy_target_kind != "actor":
                raise UnknownCondition("Unknown native enemy target kind")
            target = context.actors.get("target")
            if target is None or type(target.fight_affiliation) is not int:
                raise UnknownCondition("Missing native target bcM affiliation")
            return source.fight_affiliation != target.fight_affiliation
        if name in ("IsDead", "IsInPlay"):
            from .combat_condition_life import life_predicate

            selector = (
                "target"
                if node.args and node.args[0].value.lower() == "target"
                else "caster"
            )
            return life_predicate(context, name, selector)
        if name == "IsOffPlay":
            selector = (
                "target"
                if node.args and node.args[0].value.lower() == "target"
                else "caster"
            )
            actor = context.actors.get(selector)
            if actor is None:
                return False
            if type(actor.is_off_play) is not bool:
                raise UnknownCondition("Missing native baG offplay authority")
            return actor.is_off_play

        if name == "HasLineOfSight":
            if not callable(context.line_of_sight_query):
                raise UnknownCondition("Missing native condition LOS authority")
            value = context.line_of_sight_query()
            if type(value) is not bool:
                raise UnknownCondition("Invalid native condition LOS result")
            return value
        if name == "IsInDiagonal":
            if type(context.is_in_diagonal) is not bool:
                raise UnknownCondition("Missing native caster/target diagonal")
            return context.is_in_diagonal
        if name == "IsOnBorderCell":
            if not callable(context.border_cell_query):
                raise UnknownCondition("Missing native QI border-cell authority")
            selector = "target" if node.args[0].value.lower() == "target" else "caster"
            try:
                value = context.border_cell_query(selector)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not int or value not in (-1, 0):
                raise UnknownCondition("Invalid native eOr border-cell result")
            return value == 0
        if name == "IsInAlignment":
            if context.is_in_alignment is None:
                raise UnknownCondition("Missing native caster/target alignment")
            return context.is_in_alignment
        if name == "IsBreed":
            selector = "caster"
            breeds = set()
            for argument in node.args:
                value = argument.value
                if value.lower() in ("caster", "target"):
                    selector = value.lower()
                else:
                    native = _NATIVE_BREED_NAMES.get(value.upper())
                    if native is not None:
                        breeds.add(native)
            actor = context.actors.get(selector)
            if actor is None:
                # eNs.a uses eII.a (eGj), then returns -1 for a null selection.
                if selector in context.null_actor_aliases or (
                    selector == "target" and context.effect_target_absent is True
                ):
                    return False
                raise UnknownCondition(f"Missing native breed: {selector}")
            if actor.is_native_fighter is False:
                return False
            if actor.breed_id is None:
                raise UnknownCondition(f"Missing native breed: {selector}")
            return actor.breed_id in breeds
        if name == "IsBreedId":
            selector = node.args[0].value.lower()
            actor = context.actors.get(selector)
            if actor is None:
                # eNu.a returns -1 when eII.a resolves an actual null eHg.
                if selector in context.null_actor_aliases or (
                    selector == "target" and context.effect_target_absent is True
                ):
                    return False
                if (
                    selector in ("triggeringcaster", "triggeringtarget")
                    and context.triggering_effect_present is False
                ):
                    return False
                raise UnknownCondition(f"Missing native breed: {selector}")
            # Registered Qq/faV has no eGH breed descriptor. Native eNu's
            # dsG()==null branch returns -1; no breed0 is synthesized.
            if actor.is_native_fighter is False:
                return False
            if actor.breed_id is None:
                raise UnknownCondition(f"Missing native breed: {selector}")
            return actor.breed_id in {
                ((arg.value + 32768) % 65536) - 32768 for arg in node.args[1:]
            }
        if name == "IsTargetCellFree":
            cell = context.target_cell
            if cell is None:
                raise UnknownCondition("Missing authoritative target cell")
            strict = bool(node.args and node.args[0].value)
            return (
                cell.terrain_valid
                and not cell.has_obstacle
                and not (
                    bool(cell.occupant_blocks) if strict else any(cell.occupant_blocks)
                )
            )
        if name == "IsCarrying":
            selector = (
                "target"
                if node.args and node.args[0].value.lower() == "target"
                else "caster"
            )
            actor = context.actors.get(selector)
            if actor is None and selector in context.null_actor_aliases:
                return False  # eNw typed eGj null -> -1.
            if actor is not None and actor.is_native_fighter is False:
                return False  # eII.a rejects faV eHg as non-eGj.
            if actor is None or type(actor.is_carrying) is not bool:
                raise UnknownCondition(
                    f"Missing authoritative carrying status: {selector}"
                )
            return actor.is_carrying
        if name == "IsCarried":
            selector = node.args[0].value.lower() if node.args else "caster"
            actor = context.actors.get(selector)
            if actor is None and selector in context.null_actor_aliases:
                return False  # eNv null is not eHH.
            if actor is None or type(actor.is_carried) is not bool:
                raise UnknownCondition(
                    f"Missing authoritative carry status: {selector}"
                )
            return actor.is_carried
        identity = node.args[0].value
        state_level = (
            node.args[1].value
            if name in ("HasState", "HasStateFromLevel")
            and len(node.args) >= 2
            and type(node.args[1].value) is int
            else None
        )
        if state_level is not None:
            selector = node.args[2].value.lower() if len(node.args) == 3 else "caster"
        else:
            selector = node.args[1].value.lower() if len(node.args) == 2 else "caster"
        actor = context.actors.get(selector)
        if callable(context.state_actor_query) and selector in (
            "caster",
            "target",
            "castercontroller",
            "triggeringcaster",
            "triggeringtarget",
        ):
            try:
                actor = context.state_actor_query(selector)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if actor is None:
                return False  # eII resolved null/non-eHg PV; eME/eMF/eMG return false.
        if actor is None and selector in context.null_actor_aliases:
            if context.state_null_fallback_absent is not True:
                raise UnknownCondition(
                    "Missing native ePy state-null fallback authority"
                )
            return False  # eME/eMF/eMG no selected eHg and no ePy fallback.
        if actor is None:
            raise UnknownCondition(f"Missing authoritative actor: {selector}")
        if name in ("HasState", "HasStateFromLevel"):
            if state_level is not None or name == "HasStateFromLevel":
                threshold = state_level if state_level is not None else 0
                if actor.state_levels is None:
                    raise UnknownCondition(
                        f"Missing authoritative ordered state levels: {selector}"
                    )
                for state_id, level in actor.state_levels:
                    if state_id == identity:
                        return (
                            level >= threshold
                            if name == "HasStateFromLevel"
                            else level == threshold
                        )
                return False
            if actor.state_ids is None:
                raise UnknownCondition(f"Missing authoritative states: {selector}")
            return identity in actor.state_ids
        if name == "HasStateFromUser":
            caster = context.actors.get("caster")
            if actor.state_sources is None or caster is None or caster.actor_id is None:
                raise UnknownCondition(
                    "Missing ordered state sources or caster identity"
                )
            for state_id, source_id in actor.state_sources:
                if state_id == identity:
                    return source_id == caster.actor_id
            return False
        if actor.is_player is None:
            raise UnknownCondition(f"Missing native actor type: {selector}")
        if not actor.is_player:
            return False
        if actor.deck_spell_ids is None or actor.excluded_deck_spell_ids is None:
            raise UnknownCondition(
                f"Missing active deck or native exclusions: {selector}"
            )
        return (
            identity in actor.deck_spell_ids
            and identity not in actor.excluded_deck_spell_ids
        )

    check(root)
    return bool(run(root))
