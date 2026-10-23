"""Original weekly hunter offer grammar, independently of NPC/server graphs.

A choice containing an exact reset/active-category predicate proves its offer
conditions. It does not prove a speaker spawn, dialogue edge or acceptance action.
"""
from dataclasses import dataclass
import re
import struct

from .environmental_recurring_contracts import UnresolvedRecurringContract


@dataclass(frozen=True)
class HunterOffer:
    definition_id: int
    node_id: int
    choice_id: int
    minimum_level: int
    category_id: int
    criterion: str


_PATTERN = re.compile(
    r"GetRealLevel\(\)>=(\d+)and\(CanResetAchievement\((\d+)\)or"
    r"GetAchievementCategoryActiveCount\((\d+)\)<1\)"
)


def hunter_acceptance_condition(criterion, *, definition_id):
    if type(criterion) is not str:
        raise UnresolvedRecurringContract("missing_native_hunter_offer_criterion")
    matched = _PATTERN.fullmatch(re.sub(r"\s+", "", criterion))
    if matched is None or int(matched[2]) != definition_id:
        raise UnresolvedRecurringContract("unsupported_native_hunter_offer_criterion")
    level, category = int(matched[1]), int(matched[3])
    if level <= 0 or category <= 0:
        raise UnresolvedRecurringContract("invalid_native_hunter_offer_scope")
    return level, category


def compile_hunter_offers(nodes, definition_ids):
    """Resolve exact original target IDs/criteria; never infer from translations."""
    identities = set(definition_ids)
    if any(type(i) is not int or i <= 0 for i in identities):
        raise ValueError("Invalid qualified hunter definition scope")
    result = {}
    for node in nodes:
        for choice in node.get("choices", ()):
            criterion = choice.get("criteria", "")
            matched = _PATTERN.fullmatch(re.sub(r"\s+", "", criterion))
            if matched is None or int(matched[2]) not in identities:
                continue
            identity = int(matched[2])
            if choice.get("type") != 5 or type(choice.get("type")) is not int:
                raise UnresolvedRecurringContract(
                    "unexpected_native_hunter_choice_type"
                )
            if identity in result:
                raise UnresolvedRecurringContract("ambiguous_native_hunter_offer")
            if any(
                type(value) is not int or value <= 0
                for value in (node["id"], choice["id"])
            ):
                raise ValueError("Invalid original dialogue offer identity")
            level, category = hunter_acceptance_condition(
                criterion, definition_id=identity
            )
            result[identity] = HunterOffer(
                identity, node["id"], choice["id"], level, category, criterion
            )
    if set(result) != identities:
        raise UnresolvedRecurringContract("native_hunter_offer_missing")
    return result


def offer_eligible(offer, *, real_level, can_reset, category_active_count):
    """Evaluate original conditions using authenticated owner state supplied by caller."""
    if (
        type(real_level) is not int
        or real_level <= 0
        or type(can_reset) is not bool
        or type(category_active_count) is not int
        or category_active_count < 0
    ):
        raise ValueError(
            "Hunter offer requires authoritative owner level/category facts"
        )
    return real_level >= offer.minimum_level and (
        can_reset or category_active_count < 1
    )


def decode_native_accept_request(body):
    """cnK13397 codec only; decoding is not authorization or an NPC producer."""
    if type(body) is not bytes or len(body) != 4:
        raise ValueError("Invalid native achievement acceptance request")
    (identity,) = struct.unpack(">i", body)
    if identity <= 0:
        raise ValueError("Invalid native achievement acceptance identity")
    return identity
