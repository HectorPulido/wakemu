"""Native conditional cost table selection over authoritative cast context.

fyF.A replaces its whole fyP with each matching conditional table; it does not
add conditional values to base costs. Identity-key HashMap iteration can make
unequal overlapping matches ambiguous; reject those instead of inventing order.
This selects unmodified costs. Live eHl/fyU cost modifiers remain a separate
explicit caller input; no state/deck facts are inferred from absent context.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from dataclasses import dataclass
from wakfu_server.paths import DATA_ROOT
from .combat_conditions import evaluate_condition, UnknownCondition


@dataclass(frozen=True)
class ConditionalCostContext:
    conditions: object
    # Complete native eHl.pOJ snapshot by fyU category ID. Empty means
    # authoritatively no modifiers; None means unknown and must not become0.
    ap_modifiers_by_category: object


def native_modifiers(spell_id, snapshot):
    metadata = native_catalog()["spell_categories"]
    if str(spell_id) not in metadata:
        raise UnknownCondition("Missing native spell category metadata")
    categories = set(metadata[str(spell_id)])
    if not categories:
        return dict(ap=0, mp=0, wp=0)
    if not isinstance(snapshot, dict) or any(
        type(k) is not int or type(v) is not int for k, v in snapshot.items()
    ):
        raise UnknownCondition("Missing complete native eHl AP modifier snapshot")
    # eHl.a(ffw,fyU) only has resource cost modifier for AP(sgD).
    # sgK is RANGE, not MP/WP; these resource adjustments are native0.
    return dict(
        ap=sum(snapshot.get(category, 0) for category in categories), mp=0, wp=0
    )


@lru_cache(maxsize=1)
def native_catalog():
    from .combat_common_spell_catalog import merge_conditional_catalog

    return merge_conditional_catalog(
        protocol_catalog.load(DATA_ROOT / "conditional-spell-costs.json")
    )


def catalog():
    return native_catalog()["spells"]


def resolve_costs(spell_id, level, base, context, *, modifiers=None, rules=None):
    if type(level) is not int or not 1 <= level <= MAX_CHARACTER_LEVEL:
        raise ValueError("Invalid conditional spell level")
    baseline = tuple(base[k] for k in ("ap", "mp", "wp"))
    if any(type(v) is not int or v < 0 for v in baseline):
        raise ValueError("Invalid native baseline costs")
    table = catalog().get(str(spell_id)) if rules is None else rules
    if base.get("conditional_rules", 0) and table is None:
        raise UnknownCondition("Missing exported conditional costs")
    matches = []
    irrelevant = 0
    for rule in table or ():
        if level > len(rule["levels"]):
            raise UnknownCondition("Conditional cost level unavailable")
        selected = tuple(rule["levels"][level - 1])
        if any(type(v) is not int or v < 0 for v in selected):
            raise UnknownCondition("Invalid exported conditional costs")
        try:
            matched = evaluate_condition(rule["criteria"], context)
        except UnknownCondition:
            # An unknown criterion selecting exactly baseline costs cannot
            # change any resource cost. This proof does not validate effects.
            if selected != baseline:
                raise
            irrelevant += 1
            continue
        if matched:
            matches.append(selected)
    distinct = set(matches)
    if irrelevant and any(value != baseline for value in distinct):
        raise UnknownCondition(
            "Unknown baseline branch could override a matched conditional cost"
        )
    if len(distinct) > 1:
        raise UnknownCondition(
            "Overlapping unequal native cost matches have no stable order"
        )
    chosen = next(iter(distinct)) if distinct else baseline
    adjustments = {"ap": 0, "mp": 0, "wp": 0} if modifiers is None else modifiers
    if set(adjustments) != {"ap", "mp", "wp"} or any(
        type(v) is not int for v in adjustments.values()
    ):
        raise UnknownCondition("Incomplete native cost modifier snapshot")
    # fyF.g caps all three resource costs at zero after native modifiers.
    result = {k: max(0, v + adjustments[k]) for k, v in zip(("ap", "mp", "wp"), chosen)}
    return dict(
        result,
        conditional_rules=0,
        matched_rules=len(matches),
        irrelevant_unknown_rules=irrelevant,
    )
