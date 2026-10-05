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
    characteristics: Mapping[str, int | None] | None = None
    characteristic_maxima: Mapping[str, int] | None = None


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
    effect_target_absent: bool | None = (
        None  # Proven eII.b result null; missing context remains unknown.
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
    fight_current_table_turn: int | None = (
        None  # Native SU.bhN signed short, not personal turn.
    )
    triggering_container_is_state: bool | None = None
    triggering_container_state_id: int | None = None  # Source fyW.guI signed short.
    triggering_container_type: int | None = None  # Source eVo.aZY, zero for known null.
    world_property_now_ms: int | None = None
    areas_base_id_query: object = None  # ePj/ePi exact Qs prototype count.
    actor_specific_area_query: object = None  # eOv selected eHg/Qq geometry.
    own_summon_actor_query: object = None  # eOG/eII arbitrary native selector.
    own_specific_area_query: object = None  # eOF Qz/owner criterion.
    specific_area_range_query: object = None  # eLn/eJW complete Qs authority.
    coordinate_query: object = None  # eLT/eLU/eLW eHg or explicit aBn target.
    backstabbed_query: object = None  # eNn/eIG current selected eGj Sl and opposite PV.
    active_spell_id_query: object = None  # eJn current fight PZ, not trigger.
    effect_target_original_controller_query: object = (
        None  # eKc current Qe.bbc/eHg.dTD.
    )
    current_container_level_query: object = None  # eJE current eZR, not trigger.
    area_type_range_query: object = None
    state_actor_query: object = None  # eII selector -> known actor or proven null.
    actor_obstacle_query: object = None
    viewer_id: int | None = None
    actor_area_type_query: object = None
    team_area_range_query: object = None
    cell_specific_area_query: object = None
    cell_area_type_query: object = None  # eID Qq.d native geometry.
    line_of_sight_query: object = None  # eMr/eII.aR/fcr exact runtime authority.
    random_number_query: object = None  # eLb transaction-owned uniform index.
    fighters_breed_range_query: object = None  # eKt/eKn complete fUQ breed roster.
    has_summon_breed_query: object = None  # eMI exact breed/direct dpu over fUQ.
    enemy_range_query: object = None  # Complete live eKf/eKn roster authority.
    allies_range_query: object = None  # eJp affiliation/inPlay/114 filters.
    team_id_query: object = None  # eLx/eII.a actual selector relationship.
    own_team_state_range_query: object = None  # eKS filters state caster affiliation.
    state_range_query: object = None  # eLr complete actor + Qq carrier population.
    item_quantity_query: object = None  # eKE current source actor inventory.
    current_fighter_id: int | None = (
        None  # eJJ current SU identity; zero if no active turn.
    )


def evaluate_condition(criteria: str, context: ConditionContext) -> bool:
    """Evaluate the proven subset; raise UnknownCondition for all other input.

    Validate every branch before evaluation, including short-circuited branches,
    so unsupported expressions can never be mistaken for supported conditions.
    This is a boolean subset, not a Python eval or the full native script language.
    """
    if not criteria.strip():
        return True
    from .combat_local_criteria import parse_local_criterion, LocalCriterionSyntax

    try:
        root = parse_local_criterion(criteria.strip())
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
        if name in ("GetEnnemyCountInRange", "GetAlliesCountInRange"):
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
                "GetTriggeringEffectCaster",
                "GetTriggeringEffectTarget",
                "GetEffectTarget",
                "GetEffectTargetOriginalController",
                "GetInstanceId",
                "GetFightCurrentTableTurn",
                "GetCurrentFighterId",
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
            if (
                len(args) > 2
                or (args and not is_selector(args[0]))
                or (
                    len(args) == 2
                    and (
                        not isinstance(args[1], ast.Constant)
                        or type(args[1].value) is not int
                    )
                )
            ):
                raise UnknownCondition("Unsupported NbSummons arguments")
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
                or (len(args) == 2 and not is_selector(args[1]))
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
        if name == "GetCurrentFighterId":
            value = context.current_fighter_id
            if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
                raise UnknownCondition("Missing authoritative current fighter identity")
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
        if name in ("GetEnnemyCountInRange", "GetAlliesCountInRange"):
            query = (
                context.enemy_range_query
                if name == "GetEnnemyCountInRange"
                else context.allies_range_query
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
        if name == "GetEffectTargetOriginalController":
            if not callable(context.effect_target_original_controller_query):
                raise UnknownCondition(
                    "Missing native original target controller authority"
                )
            try:
                value = context.effect_target_original_controller_query()
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
            raise UnknownCondition(f"Missing native actor: {selector}")
        if name == "GetEffectCaster":
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
                if (
                    actor.summon_counts_by_breed is None
                    or args[1].value not in actor.summon_counts_by_breed
                ):
                    raise UnknownCondition("Missing native filtered summon count")
                return actor.summon_counts_by_breed[args[1].value]
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
        if maximum <= 0:
            raise UnknownCondition(
                "Nonpositive native maximum requires nonfinite percentage semantics"
            )
        f32 = lambda value: struct.unpack("f", struct.pack("f", value))[0]
        return float(math.floor(f32(f32(f32(value) / f32(maximum)) * 100.0)))

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
            args = node.args
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
                    "IsTargetCellFree",
                    "IsBreedId",
                    "IsBreed",
                    "IsInAlignment",
                    "HasLineOfSight",
                    "IsOffPlay",
                    "IsEnemy",
                    "IsEnnemy",
                    "HasFightProperty",
                    "HasWorldProperty",
                    "IsOwnSummon",
                    "IsSummon",
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
                    "IsOnSpecificEffectArea",
                    "IsTriggeredByMeleeEffect",
                    "IsTriggeredByZoneEffect",
                    "IsTriggeredByIndirectEffect",
                    "IsTriggeredByEffectWithREP",
                    "GetTriggeringEffectCasterIsSameAsCaster",
                )
                or node.keywords
            ):
                raise UnknownCondition(f"Unsupported native predicate: {name}")
            if name == "HasSummonWithBreed":
                if len(args) != 1:
                    raise UnknownCondition(
                        "Native HasSummonWithBreed requires one long"
                    )
                check_number(args[0])
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
            if name == "IsSummon":
                if (
                    len(args) != 1
                    or not isinstance(args[0], ast.Constant)
                    or type(args[0].value) is not str
                ):
                    raise UnknownCondition(
                        "IsSummon requires one native string selector"
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
            if name == "IsOffPlay":
                if len(args) > 1 or (
                    args
                    and (
                        not isinstance(args[0], ast.Constant)
                        or type(args[0].value) is not str
                    )
                ):
                    raise UnknownCondition("Unsupported native IsOffPlay signature")
                return
            if name == "HasLineOfSight":
                if args:
                    raise UnknownCondition("Native HasLineOfSight takes no arguments")
                return
            if name == "IsInAlignment":
                if args:
                    raise UnknownCondition("Unsupported IsInAlignment arguments")
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
                    or not is_selector(args[0])
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
            if name in ("IsCarrying", "IsBackstabbed"):
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
                if len(args) == 3 and not is_selector(args[2]):
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
                        if name == "HasStateFromUser"
                        else ("caster", "target")
                    )
                )
            ):
                raise UnknownCondition(f"Unsupported {name} actor selector")
            return
        raise UnknownCondition(f"Unsupported native expression: {ast.dump(node)}")

    def run(node):
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
        if name == "IsBackstabbed":
            if not callable(context.backstabbed_query):
                raise UnknownCondition("Missing native facing authority")
            selector = (
                "target"
                if node.args and node.args[0].value.lower() == "target"
                else "caster"
            )
            try:
                value = context.backstabbed_query(selector)
            except ValueError as error:
                raise UnknownCondition(str(error)) from error
            if type(value) is not bool:
                raise UnknownCondition("Invalid native facing result")
            return value
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
            actor = context.actors.get(
                node.args[0].value.lower() if node.args else "caster"
            )
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
            actor = context.actors.get(node.args[0].value.lower())
            if actor is None or actor.retained_effect_ids is None:
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
                if affiliations is None:
                    raise UnknownCondition(
                        "Missing native cell occupant/obstacle affiliations"
                    )
                return any(team != source.fight_affiliation for team in affiliations)
            if context.enemy_target_kind != "actor":
                raise UnknownCondition("Unknown native enemy target kind")
            target = context.actors.get("target")
            if target is None or type(target.fight_affiliation) is not int:
                raise UnknownCondition("Missing native target bcM affiliation")
            return source.fight_affiliation != target.fight_affiliation
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
            if actor is None or actor.breed_id is None:
                raise UnknownCondition(f"Missing native breed: {selector}")
            return actor.breed_id in breeds
        if name == "IsBreedId":
            selector = node.args[0].value.lower()
            actor = context.actors.get(selector)
            if actor is None or actor.breed_id is None:
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
            if actor is None or type(actor.is_carrying) is not bool:
                raise UnknownCondition(
                    f"Missing authoritative carrying status: {selector}"
                )
            return actor.is_carrying
        if name == "IsCarried":
            selector = node.args[0].value.lower() if node.args else "caster"
            actor = context.actors.get(selector)
            if actor is None or actor.is_carried is None:
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
        if name == "HasStateFromUser" and callable(context.state_actor_query):
            actor = context.state_actor_query(selector)
            if actor is None:
                return False  # eMG: proven null selected eHg produces -1.
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
