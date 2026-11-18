"""Server-owned order trials reconstructed from native pizza tutorial rules.

This is a pure transition kernel, not a network handler. Callers must obtain
receipts from committed spell, movement and turn actions, and persist the state
and receipt together. Neither a client score nor a generic victory is accepted.
Production profiles require reviewed scoring and arena data before activation.
"""
from dataclasses import dataclass, replace
import hashlib
import json


COLORS = ("blue", "red", "green")
INGREDIENTS = ("tomato", "cheese", "pepper")
RECIPES = frozenset(
    (color, ingredient) for color in COLORS for ingredient in INGREDIENTS
)


@dataclass(frozen=True)
class OrderRules:
    """Explicit encounter-owned scoring; no guessed default score weights."""

    weights: tuple
    score_threshold: int = 400
    strike_limit: int = 3
    ingredient_batch: int = 2
    ingredient_capacity: int = 10

    def __post_init__(self):
        pairs = dict(self.weights)
        if (
            len(self.weights) != 9
            or set(pairs) != RECIPES
            or any(
                type(value) is not int or value <= 0 or value % 5
                for value in pairs.values()
            )
            or type(self.score_threshold) is not int
            or self.score_threshold <= 0
            or type(self.strike_limit) is not int
            or self.strike_limit <= 0
            or type(self.ingredient_batch) is not int
            or self.ingredient_batch <= 0
            or type(self.ingredient_capacity) is not int
            or self.ingredient_capacity < self.ingredient_batch
        ):
            raise ValueError(
                "An order trial requires a complete reviewed scoring matrix"
            )


@dataclass(frozen=True)
class Larva:
    actor_id: int
    color: str
    tenderized: bool = False
    ingredient: str | None = None


@dataclass(frozen=True)
class OrderTrial:
    owner_id: int
    encounter_id: int
    hard_mode: bool
    orders: tuple
    larvae: tuple = ()
    ingredient: str | None = None
    charges: int = 0
    score: int = 0
    strikes: int = 0
    turn: int = 1
    finished: bool = False
    receipts: frozenset = frozenset()

    @property
    def score_state_level(self):
        """Native state3050 displays five points for each state level."""
        return self.score // 5


def start(*, owner_id, encounter_id, hard_mode, orders):
    if (
        type(owner_id) is not int
        or owner_id <= 0
        or type(encounter_id) is not int
        or encounter_id <= 0
        or type(hard_mode) is not bool
    ):
        raise ValueError("Invalid order trial identity")
    return OrderTrial(owner_id, encounter_id, hard_mode, _orders(orders))


def _orders(orders):
    if type(orders) not in (tuple, list) or any(
        type(order) not in (tuple, list)
        or len(order) != 2
        or any(type(part) is not str for part in order)
        for order in orders
    ):
        raise ValueError("Native orders require explicit recipe pairs")
    orders = tuple(tuple(order) for order in orders)
    if len(orders) != 3 or len(set(orders)) != 3 or not set(orders) <= RECIPES:
        raise ValueError("Native orders require three distinct recipes")
    return orders


def larva_limit(turn):
    if type(turn) is not int or turn < 1:
        raise ValueError("Invalid native turn")
    return 1 if turn < 6 else 2 if turn < 10 else 3


def apply(
    state,
    rules,
    *,
    owner_id,
    encounter_id,
    receipt,
    action,
    target_id=None,
    color=None,
    ingredient=None,
    next_orders=None,
    population_limit=None,
    charges_after=None
):
    """Apply a committed, authenticated encounter event exactly once.

    ``bake`` means the combat producer already verified a push into an oven;
    ``escape`` means the producer observed the larva crossing its escape cell.
    A spawn producer may supply its own authenticated population limit: the
    conveyor replacement and turn constructor have different native guards.
    A browser/client packet must never directly call this function. Receipts
    identify actual committed actions, not values supplied by the player.
    """
    if not isinstance(state, OrderTrial) or not isinstance(rules, OrderRules):
        raise ValueError("Invalid order trial state")
    if owner_id != state.owner_id or encounter_id != state.encounter_id:
        raise ValueError("Order trial authority mismatch")
    if not isinstance(receipt, str) or not receipt:
        raise ValueError("A committed action receipt is required")
    if receipt in state.receipts or state.finished:
        return state
    if action not in (
        "spawn",
        "pickup",
        "tenderize",
        "destroy_tenderized",
        "garnish",
        "bake",
        "escape",
        "turn_end",
        "refill",
        "finish",
    ):
        raise ValueError("Unknown order trial action")
    result = replace(state, receipts=state.receipts | {receipt})
    larvae = {larva.actor_id: larva for larva in state.larvae}
    if action == "spawn":
        if (
            type(target_id) is not int
            or target_id == 0
            or target_id in larvae
            or color not in COLORS
        ):
            raise ValueError("Invalid larva spawn")
        limit = (
            larva_limit(state.turn) if population_limit is None else population_limit
        )
        if type(limit) is not int or limit < 1:
            raise ValueError("Invalid native spawn population limit")
        if len(larvae) >= limit:
            raise ValueError("Native larva population limit exceeded")
        larvae[target_id] = Larva(target_id, color)
    elif action == "pickup":
        if ingredient not in INGREDIENTS:
            raise ValueError("Unknown native barrel")
        previous = state.charges if state.ingredient == ingredient else 0
        charges = min(previous + rules.ingredient_batch, rules.ingredient_capacity)
        if charges_after is not None and (
            type(charges_after) is not int or charges_after != charges
        ):
            raise ValueError(
                "Native ingredient carrier disagrees with its additive pickup"
            )
        result = replace(result, ingredient=ingredient, charges=charges)
    elif action in ("tenderize", "destroy_tenderized", "garnish", "bake", "escape"):
        if target_id not in larvae:
            raise ValueError("Action target is not an encounter larva")
        larva = larvae[target_id]
        if action == "tenderize":
            # This witnesses the actual successful3045 application. Its native
            # two-turn expiry can allow another first application later.
            larvae[target_id] = replace(larva, tenderized=True)
        elif action == "destroy_tenderized":
            if not larva.tenderized:
                raise ValueError("Native second-hit death lacks its first tenderize")
            del larvae[target_id]  # Actual native28/118970 death, without a strike.
        elif action == "garnish":
            if not larva.tenderized or larva.ingredient or not state.charges:
                raise ValueError("Native garnish preconditions are not satisfied")
            larvae[target_id] = replace(larva, ingredient=state.ingredient)
            result = replace(result, charges=state.charges - 1)
        else:
            del larvae[target_id]
            if action == "escape" or larva.ingredient is None:
                result = replace(result, strikes=state.strikes + 1)
            else:
                recipe = (larva.color, larva.ingredient)
                if recipe in state.orders:
                    result = replace(
                        result,
                        score=state.score + dict(rules.weights)[recipe],
                        orders=tuple(
                            order for order in state.orders if order != recipe
                        ),
                    )
                # A garnished, unrequested pizza earns zero without a strike.
    elif action == "turn_end":
        result = replace(result, turn=state.turn + 1)
    elif action == "refill":
        if state.orders:
            raise ValueError("Orders refill only when all three have been served")
        result = replace(result, orders=_orders(next_orders or ()))
    elif action == "finish":
        result = replace(result, finished=True)
    return replace(
        result,
        larvae=tuple(larvae.values()),
        finished=result.finished or result.strikes >= rules.strike_limit,
    )


def qualifies(state, rules):
    """Only a finished hard-mode score can settle native objective4261."""
    return state.finished and state.hard_mode and state.score >= rules.score_threshold


def _rules_digest(rules):
    if not isinstance(rules, OrderRules):
        raise ValueError("Invalid order trial rules")
    document = dict(
        weights=sorted(
            (color, ingredient, value) for (color, ingredient), value in rules.weights
        ),
        score_threshold=rules.score_threshold,
        strike_limit=rules.strike_limit,
        ingredient_batch=rules.ingredient_batch,
        ingredient_capacity=rules.ingredient_capacity,
    )
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()


def snapshot(state, rules):
    """Encode an earned trial for the owning combat checkpoint transaction.

    This is persistence data, never a client input format. The caller must
    persist it with the accepted combat action and its frozen admission.
    """
    if not isinstance(state, OrderTrial):
        raise ValueError("Invalid order trial state")
    document = dict(
        schema=1,
        rules_sha256=_rules_digest(rules),
        owner_id=state.owner_id,
        encounter_id=state.encounter_id,
        hard_mode=state.hard_mode,
        orders=[list(order) for order in state.orders],
        larvae=[
            dict(
                actor_id=larva.actor_id,
                color=larva.color,
                tenderized=larva.tenderized,
                ingredient=larva.ingredient,
            )
            for larva in state.larvae
        ],
        ingredient=state.ingredient,
        charges=state.charges,
        score=state.score,
        strikes=state.strikes,
        turn=state.turn,
        finished=state.finished,
        receipts=sorted(state.receipts),
    )
    restore(document, rules, owner_id=state.owner_id, encounter_id=state.encounter_id)
    return document


def restore(document, rules, *, owner_id, encounter_id):
    """Restore only a matching owner's trial under its original frozen rules."""
    fields = {
        "schema",
        "rules_sha256",
        "owner_id",
        "encounter_id",
        "hard_mode",
        "orders",
        "larvae",
        "ingredient",
        "charges",
        "score",
        "strikes",
        "turn",
        "finished",
        "receipts",
    }
    if (
        not isinstance(document, dict)
        or set(document) != fields
        or type(document["schema"]) is not int
        or document["schema"] != 1
        or document["rules_sha256"] != _rules_digest(rules)
        or type(owner_id) is not int
        or owner_id <= 0
        or type(encounter_id) is not int
        or encounter_id <= 0
        or type(document["owner_id"]) is not int
        or document["owner_id"] != owner_id
        or type(document["encounter_id"]) is not int
        or document["encounter_id"] != encounter_id
        or type(document["hard_mode"]) is not bool
        or type(document["finished"]) is not bool
        or any(
            type(document[key]) is not int
            for key in ("charges", "score", "strikes", "turn")
        )
        or not 0 <= document["charges"] <= rules.ingredient_capacity
        or document["score"] < 0
        or document["score"] % 5
        or not 0 <= document["strikes"] <= rules.strike_limit
        or document["turn"] < 1
        or (document["strikes"] == rules.strike_limit and not document["finished"])
        or document["ingredient"] not in (None, *INGREDIENTS)
        or (document["ingredient"] is None and document["charges"] != 0)
        or type(document["orders"]) is not list
        or type(document["larvae"]) is not list
        or type(document["receipts"]) is not list
    ):
        raise ValueError("Invalid or incompatible order trial checkpoint")
    orders = document["orders"]
    if len(orders) > 3 or any(
        type(order) is not list
        or len(order) != 2
        or any(type(part) is not str for part in order)
        for order in orders
    ):
        raise ValueError("Invalid checkpoint orders")
    orders = tuple(tuple(order) for order in orders)
    if len(set(orders)) != len(orders) or not set(orders) <= RECIPES:
        raise ValueError("Invalid checkpoint orders")
    larvae = []
    for row in document["larvae"]:
        if (
            type(row) is not dict
            or set(row) != {"actor_id", "color", "tenderized", "ingredient"}
            or type(row["actor_id"]) is not int
            or row["actor_id"] == 0
            or row["color"] not in COLORS
            or type(row["tenderized"]) is not bool
            or row["ingredient"] not in (None, *INGREDIENTS)
            or (row["ingredient"] is not None and not row["tenderized"])
        ):
            raise ValueError("Invalid checkpoint larva")
        larvae.append(Larva(**row))
    receipts = document["receipts"]
    if (
        len({larva.actor_id for larva in larvae}) != len(larvae)
        or any(type(receipt) is not str or not receipt for receipt in receipts)
        or len(set(receipts)) != len(receipts)
    ):
        raise ValueError("Invalid checkpoint actors or action receipts")
    return OrderTrial(
        owner_id=owner_id,
        encounter_id=encounter_id,
        hard_mode=document["hard_mode"],
        orders=orders,
        larvae=tuple(larvae),
        ingredient=document["ingredient"],
        charges=document["charges"],
        score=document["score"],
        strikes=document["strikes"],
        turn=document["turn"],
        finished=document["finished"],
        receipts=frozenset(receipts),
    )
