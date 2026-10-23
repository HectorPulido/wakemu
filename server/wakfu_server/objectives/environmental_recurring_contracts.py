"""Compile source-backed recurring families without activating journal entries.

Calendar metadata is not an objective producer. Only the native hunter-variable
sum grammar is executable here. Other families retain explicit missing contracts
for a normalized importer; no title-to-boss or seasonal quest inference is made.
"""
from dataclasses import dataclass
import re


class UnresolvedRecurringContract(ValueError):
    pass


def _integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value < 2**63:
        raise ValueError("Invalid recurring " + name)
    return value


@dataclass(frozen=True)
class NativeReward:
    kind: str
    reference: int | None
    amount: int
    native_flag: bool


@dataclass(frozen=True)
class HunterContract:
    definition_id: int
    objective_id: int
    minimum_level: int
    boss_references: tuple[int, ...]
    variable_names: tuple[str, ...]
    required_distinct: int
    anchor_ms: int
    period_ms: int
    cooldown_ms: int
    rewards: tuple[NativeReward, ...]
    # Original variables/thresholds plus observed distinct-boss family behavior;
    # this is not a claim that the original server variable writer was recovered.
    interpretation_policy: str = "wakemu.hunter-weekly-distinct-boss-source-v1"

    def period(self, at_ms):
        _integer(at_ms, "clock")
        return (
            None
            if at_ms < self.anchor_ms
            else (at_ms - self.anchor_ms) // self.period_ms
        )


@dataclass(frozen=True)
class AcceptedHunter:
    definition_id: int
    character_id: int
    period: int
    accepted_at_ms: int
    real_level: int
    receipt_key: str


@dataclass(frozen=True)
class HunterProgress:
    acceptance: AcceptedHunter
    defeated: frozenset[int] = frozenset()
    # A receipt identity cannot be reinterpreted as another boss on replay.
    receipts: tuple[tuple[int, int], ...] = ()
    completed_at_ms: int | None = None


_VARIABLE = re.compile(r'GetAchievementVariable\("(hunterLevel(\d+)Boss(\d+))"\)')


def hunter_objective(objectives):
    if type(objectives) not in (list, tuple) or len(objectives) != 1:
        raise UnresolvedRecurringContract("hunter_objective_shape_unresolved")
    objective = objectives[0]
    expressions = objective.get("ckf")
    if type(expressions) is not list or len(expressions) != 1:
        raise UnresolvedRecurringContract("native_objective_producer_unrecovered")
    expression = expressions[0].get("ckm")
    if type(expression) is not str:
        raise UnresolvedRecurringContract("native_objective_producer_unrecovered")
    expression = re.sub(r"\s+", "", expression)
    compare = re.fullmatch(r"\((.+)\)>=(\d+)", expression)
    if compare is None:
        raise UnresolvedRecurringContract("unsupported_native_objective_expression")
    terms = compare[1].split("+")
    matches = [_VARIABLE.fullmatch(term) for term in terms]
    if not terms or any(match is None for match in matches):
        raise UnresolvedRecurringContract("unsupported_native_objective_expression")
    names = tuple(match[1] for match in matches)
    bosses = tuple(int(match[3]) for match in matches)
    required = int(compare[2])
    # The level substring belongs to the original variable name, not a level
    # eligibility gate. Preserve mixed source prefixes; use the real criterion.
    if len(set(bosses)) != len(bosses) or not 0 < required <= len(bosses):
        raise UnresolvedRecurringContract("invalid_distinct_boss_contract")
    for boss in bosses:
        _integer(boss, "boss", 1)
    return _integer(objective["d"], "objective", 1), names, bosses, required


def _rewards(rows):
    result = []
    for row in rows:
        parameters = row.get("parameters")
        flag = row.get("raw_flag_ckk")
        if type(flag) is not bool or type(parameters) is not list:
            raise UnresolvedRecurringContract("native_reward_parameters_unqualified")
        if row.get("type") == "GIVE_PLAYER_XP" and len(parameters) == 1:
            result.append(
                NativeReward(
                    "player_xp", None, _integer(parameters[0], "reward XP"), flag
                )
            )
        elif row.get("type") == "GIVE_PLAYER_ITEM" and len(parameters) == 2:
            result.append(
                NativeReward(
                    "item",
                    _integer(parameters[0], "reward item", 1),
                    _integer(parameters[1], "reward quantity", 1),
                    flag,
                )
            )
        else:
            raise UnresolvedRecurringContract("native_reward_family_unqualified")
    return tuple(result)


def compile_hunter_contract(
    *,
    definition_id,
    objectives,
    rewards,
    anchor_ms,
    period_seconds,
    cooldown_seconds,
    repeatable,
    activation_criteria,
    eligibility_criteria,
    acceptance_criteria=None
):
    if repeatable is not True or period_seconds != 604800:
        raise UnresolvedRecurringContract("hunter_weekly_recurrence_unqualified")
    if activation_criteria.strip() == "False":
        raise UnresolvedRecurringContract("native_activation_disabled")
    eligibility = re.sub(r"\s+", "", eligibility_criteria)
    minimum = (
        re.fullmatch(r"GetRealLevel\(\)>=(\d+)", eligibility) if eligibility else None
    )
    if eligibility and minimum is None:
        raise UnresolvedRecurringContract(
            "native_eligibility_requires_original_evaluator"
        )
    if activation_criteria.strip():
        raise UnresolvedRecurringContract(
            "native_activation_requires_original_evaluator"
        )
    objective, variables, bosses, required = hunter_objective(objectives)
    minimum_level = int(minimum[1]) if minimum else None
    if acceptance_criteria is not None:
        from .environmental_recurring_offers import hunter_acceptance_condition

        offered_minimum, _ = hunter_acceptance_condition(
            acceptance_criteria, definition_id=definition_id
        )
        minimum_level = max(minimum_level or 0, offered_minimum)
    if minimum_level is None:
        raise UnresolvedRecurringContract("native_acceptance_minimum_unrecovered")
    return HunterContract(
        _integer(definition_id, "definition", 1),
        objective,
        minimum_level,
        bosses,
        variables,
        required,
        _integer(anchor_ms, "anchor"),
        _integer(period_seconds, "period", 1) * 1000,
        _integer(cooldown_seconds, "cooldown") * 1000,
        _rewards(rewards),
    )


def accept_hunter(contract, *, character_id, real_level, at_ms, acceptance_receipt_key):
    """Freeze an already authenticated original acceptance, not a player request."""
    _integer(character_id, "character", 1)
    _integer(real_level, "real level", 1)
    if (
        type(acceptance_receipt_key) is not str
        or not 1 <= len(acceptance_receipt_key) <= 200
    ):
        raise ValueError("Missing durable original hunter acceptance receipt")
    period = contract.period(at_ms)
    if period is None or real_level < contract.minimum_level:
        raise ValueError("Hunter contract is not eligible at acceptance")
    return HunterProgress(
        AcceptedHunter(
            contract.definition_id,
            character_id,
            period,
            at_ms,
            real_level,
            acceptance_receipt_key,
        )
    )


def advance_hunter(
    contract,
    progress,
    *,
    character_id,
    fight_id,
    boss_reference,
    completed_at_ms,
    won,
    original_boss,
    final_room_completed
):
    """Project a durable accepted owner's actual final-room victory.

    Caller authenticates these facts from settled combat receipts. Persistence
    reserves a completion entitlement before publishing rewards; this function
    never claims inventory, XP or native quest activation by itself.
    """
    _integer(character_id, "character", 1)
    _integer(fight_id, "fight", 1)
    _integer(boss_reference, "boss", 1)
    _integer(completed_at_ms, "completion clock")
    if any(
        type(value) is not bool for value in (won, original_boss, final_room_completed)
    ):
        raise ValueError("Hunter victory requires authoritative boolean facts")
    accepted = progress.acceptance
    if (
        accepted.definition_id != contract.definition_id
        or accepted.character_id != character_id
    ):
        raise ValueError("Foreign hunter acceptance")
    prior = dict(progress.receipts)
    if fight_id in prior:
        if prior[fight_id] != boss_reference:
            raise ValueError("Hunter receipt identity changed on replay")
        return progress
    if (
        not (won and original_boss and final_room_completed)
        or completed_at_ms < accepted.accepted_at_ms
        or contract.period(completed_at_ms) != accepted.period
        or boss_reference not in contract.boss_references
        or progress.completed_at_ms is not None
    ):
        return progress
    defeated = progress.defeated | {boss_reference}
    complete_at = (
        completed_at_ms if len(defeated) >= contract.required_distinct else None
    )
    return HunterProgress(
        accepted,
        defeated,
        progress.receipts + ((fight_id, boss_reference),),
        complete_at,
    )
