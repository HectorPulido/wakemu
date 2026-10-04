"""Restricted native effect criteria, with explicit unknowns instead of guesses.

Evidence: wakfu-client.jar eQb tokens 198/342 -> eQd eME/eOS.
eME.a tests eHg.kY(stateId); its numeric second argument uses eHg.v,
which compares the FIRST matching state level for equality (not a threshold). eII.a resolves absent selectors to caster.
eGj.kY iterates state effects and compares fyW.guI state IDs. eOS defaults to caster,
requires a player (aGJ == 0), an active deck, and excludes eEI/eEL.pby IDs.
HasStateFromUser: eQb224 -> eQd/eMG -> eGj.a(long,eHg) compares
the FIRST matching state effect source Sn with caster Sn. IsCarried:
eQb257 -> eQd/eNv -> eGj.buX tests non-null carrier. IsTargetCellFree:
eQb288 -> eQd/eOV validates terrain QI.R, occupants Qq.bcP and QI.V
obstacles; optional True rejects even nonblocking occupants.
NbSummons: eQb384/ePs -> eGj.dTB/GF (active owned summons filtered).
IsBreedId: eQb256/eNu compares eGH.aXA with short-converted IDs.
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
    breed_id: int | None = None
    effective_level: int | None = None
    fight_properties: frozenset[int] | None = None  # PV.a(ffe), not world properties.
    fight_affiliation: int | None = (
        None  # eHg.bcM(), independent of bcN targeting team.
    )
    is_native_fighter: bool | None = None
    is_character: bool | None = None  # eHg.a(eHh.CHARACTER), includes NPCs.
    is_summon: bool | None = None  # eGj.dTE(), not merely an NPC kind.
    summon_root_id: int | None = None  # Identity of eGj.fqK ownership-chain root.
    retained_effect_ids: frozenset[int] | None = None  # PK.aZE in complete owned Qf.
    in_fight: bool | None = None  # Authoritative eHg.dnz actor membership.
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
    effect_target_absent: bool | None = None  # Proven eII.b result null; missing context remains unknown.
    triggering_effect_present: bool | None = None
    triggering_effect_reference_id: int | None = None  # Source eZR.aZE definition reference.
    triggering_effect_value: int | None = None  # Source eZR.getValue signed int.
    triggering_effect_action_id: int | None = None  # Source eVn.awM, NOT aZE.
    triggering_container_is_state: bool | None = None
    triggering_container_state_id: int | None = None  # Source fyW.guI signed short.


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
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = literal_long(node.operand)
            if isinstance(node.op, ast.USub):
                value = -value
        else:
            raise UnknownCondition("Native triggering depth requires a constant integer")
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
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
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
        if name in ("GetTriggeringContainerStateId", "GetTriggeringEffectValue"):
            if args:
                raise UnknownCondition("Native triggering state ID takes no arguments")
            return
        if name in ("GetTriggeringEffectActionId", "GetTriggeringEffectId"):
            if len(args) > 1:
                raise UnknownCondition("Native triggering depth requires a constant integer")
            if args:
                literal_long(args[0])
            return

        if (
            name in ("GetDistanceBetweenCasterAndTarget", "GetEffectCaster", "GetEffectTarget")
            and not args
        ):
            return
        if name == "GetPhysicalRadius":
            if len(args) != 1 or not is_selector(args[0]):
                raise UnknownCondition(
                    "Native GetPhysicalRadius requires an actor selector"
                )
            return
        if name in ("GetLevel", "GetTeamId"):
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
                not isinstance(node.op, ast.Div)
                and integral(node.left)
                and integral(node.right)
            )
        if isinstance(node, ast.IfExp):
            return integral(node.body) and integral(node.orelse)
        return isinstance(node, ast.Call) and node.func.id not in (
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
        if name in ("GetTriggeringContainerStateId", "GetTriggeringEffectActionId", "GetTriggeringEffectValue", "GetTriggeringEffectId"):
            if name in ("GetTriggeringEffectActionId", "GetTriggeringEffectId") and args and literal_long(args[0]) <= 0:
                return -1  # eLK does not resolve a source for nonpositive depth.
            if type(context.triggering_effect_present) is not bool:
                raise UnknownCondition("Missing native triggering effect presence")
            if not context.triggering_effect_present:
                return -1 if name in ("GetTriggeringEffectActionId", "GetTriggeringEffectId") else 0
            if name == "GetTriggeringEffectId":
                if type(context.triggering_effect_reference_id) is not int:
                    raise UnknownCondition("Missing native source running-effect definition aZE")
                return context.triggering_effect_reference_id
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
        if name == "GetDistanceBetweenCasterAndTarget":
            value = context.caster_target_distance
            if type(value) is not int or value < -1:
                raise UnknownCondition("Missing authoritative caster/target distance")
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
                    "HasStateFromUser",
                    "IsSpellInDeck",
                    "IsCarried",
                    "IsTargetCellFree",
                    "IsBreedId",
                    "IsInAlignment",
                    "IsEnemy",
                    "IsEnnemy",
                    "HasFightProperty",
                    "IsOwnSummon",
                    "HasEffectWithSpecificId",
                    "IsInFight",
                    "IsCharacter",
                )
                or node.keywords
            ):
                raise UnknownCondition(f"Unsupported native predicate: {name}")
            if name in ("IsInFight", "IsCharacter"):
                if len(args) > 1 or args and not is_selector(args[0]):
                    raise UnknownCondition("Unsupported native IsInFight selector")
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
            if name == "IsOwnSummon":
                if not (
                    not args
                    or len(args) == 1
                    and (
                        is_selector(args[0])
                        or isinstance(args[0], ast.Constant)
                        and type(args[0].value) is int
                    )
                    or len(args) == 2
                    and isinstance(args[0], ast.Constant)
                    and type(args[0].value) is int
                    and is_selector(args[1])
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
            if name == "IsInAlignment":
                if args:
                    raise UnknownCondition("Unsupported IsInAlignment arguments")
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
                name == "HasState"
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
                or args[1].value.lower() not in ("caster", "target")
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
        if name == "IsInAlignment":
            if context.is_in_alignment is None:
                raise UnknownCondition("Missing native caster/target alignment")
            return context.is_in_alignment
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
            if name == "HasState"
            and len(node.args) >= 2
            and type(node.args[1].value) is int
            else None
        )
        if state_level is not None:
            selector = node.args[2].value.lower() if len(node.args) == 3 else "caster"
        else:
            selector = node.args[1].value.lower() if len(node.args) == 2 else "caster"
        actor = context.actors.get(selector)
        if actor is None:
            raise UnknownCondition(f"Missing authoritative actor: {selector}")
        if name == "HasState":
            if state_level is not None:
                if actor.state_levels is None:
                    raise UnknownCondition(
                        f"Missing authoritative ordered state levels: {selector}"
                    )
                for state_id, level in actor.state_levels:
                    if state_id == identity:
                        return level == state_level
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
