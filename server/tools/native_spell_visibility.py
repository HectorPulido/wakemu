"""Independent native available-book query; ownership and castability stay separate."""
from collections.abc import Mapping

SCHEMA = "native-spell-visibility-v1"
CONSUMER = "bPv.f.bPK.gtS"


def validate_visibility(document):
    if document.get("schema") != SCHEMA or not isinstance(document.get("spells"), dict):
        raise ValueError("Invalid native spell visibility document")
    for reference, row in document["spells"].items():
        if (
            not isinstance(reference, str)
            or not reference.isdecimal()
            or int(reference) <= 0
            or row.get("reference") != int(reference)
            or row.get("native_consumer") != CONSUMER
            or row.get("native_parser") != "eQe.tz"
            or type(row.get("native_criterion_present")) is not bool
            or row.get("visibility_criterion_raw") is not None
            and not isinstance(row["visibility_criterion_raw"], str)
            or row["native_criterion_present"]
            and not row.get("visibility_criterion_raw")
        ):
            raise ValueError("Invalid native visibility record: " + str(reference))


def available_owned_actions(owned_actions, visibility, actor_context, *, evaluate=None):
    """Return visibility decisions without changing the complete native book.

    bPv evaluates the actual source actor as BOTH source and target. No player
    fallback, resource grants, casting criteria or target-cell filtering occur.
    Unsupported/missing metadata raises rather than silently hiding ownership.
    """
    owned_actions = tuple(owned_actions)
    validate_visibility(visibility)
    if not isinstance(actor_context.actors, Mapping):
        raise ValueError("Missing native visibility actor context")
    actor = actor_context.actors.get("caster")
    if actor is None or actor_context.actors.get("target") is not actor:
        raise ValueError(
            "Native bPv visibility requires the same actual source/target actor"
        )
    if evaluate is None:
        from wakfu_server.combat_conditions import evaluate_condition

        evaluate = evaluate_condition
    visible, dormant, decisions, seen = [], [], [], set()
    for action in owned_actions:
        reference = action.get("reference")
        if type(reference) is not int or reference <= 0 or reference in seen:
            raise ValueError("Invalid complete owned spell book")
        seen.add(reference)
        row = visibility["spells"].get(str(reference))
        if row is None:
            raise ValueError("Missing exact native spell visibility: " + str(reference))
        admitted = (
            evaluate(row["visibility_criterion_raw"], actor_context)
            if row["native_criterion_present"]
            else True
        )
        if type(admitted) is not bool:
            raise ValueError("Native visibility evaluator did not return a boolean")
        (visible if admitted else dormant).append(action)
        decisions.append(
            dict(
                reference=reference,
                visible=admitted,
                native_consumer=CONSUMER,
                criterion=row["visibility_criterion_raw"],
            )
        )
    return dict(
        owned_actions=tuple(owned_actions),
        available_actions=tuple(visible),
        dormant_actions=tuple(dormant),
        decisions=tuple(decisions),
        ownership_changed=False,
        castability_evaluated=False,
    )
