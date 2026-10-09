"""Bounded target search through the production cast validator, without effects."""
from copy import deepcopy
import struct


def candidate_cells(fight, actor_id, *, limit=256):
    if type(limit) is not int or not 1 <= limit <= 4096:
        raise ValueError("Invalid bounded casting candidate limit")
    actor = fight.actors[actor_id]
    enemies = sorted(
        (
            value
            for value in fight.actors.values()
            if value.id != actor_id and value.team != actor.team
        ),
        key=lambda value: value.id,
    )
    allies = sorted(
        (
            value
            for value in fight.actors.values()
            if value.id != actor_id and value.team == actor.team
        ),
        key=lambda value: value.id,
    )
    cells = list(
        dict.fromkeys(
            (
                *(value.position for value in enemies),
                actor.position,
                *(value.position for value in allies),
                *sorted(
                    fight.walkable,
                    key=lambda cell: (
                        abs(cell[0] - actor.position[0])
                        + abs(cell[1] - actor.position[1]),
                        cell,
                    ),
                ),
            )
        )
    )
    return tuple(cells[:limit]), len(cells)


def eligible_cast_targets(
    fight,
    character,
    deck,
    spell_uid,
    *,
    adapter,
    line_of_sight,
    actor_id=None,
    limit=256,
    maximum_eligible=3,
    validate=None
):
    """Return plans accepted by actual ownership/cost/criterion/QI/usage checks.

    No effect runtime factory is created per candidate. One private copy is
    shared by read-only validation; accepted plans are then executed through
    the ordinary server transaction against the caller's unchanged fight.
    Unknown authority and bounded exhaustion are distinct from no context.
    """
    if type(maximum_eligible) is not int or not 1 <= maximum_eligible <= 16:
        raise ValueError("Invalid eligible casting target count")
    if validate is None:
        from wakfu_server.combat_cast import prepare_spell_cast

        validate = prepare_spell_cast
    identity = character["id"] if actor_id is None else actor_id
    cells, total = candidate_cells(fight, identity, limit=limit)
    preview = deepcopy(fight)
    actor = preview.actors[identity]
    eligible, rejected = [], []
    unresolved = False
    for target in cells:
        try:
            if not isinstance(actor.effect_stats, dict) or 4 not in actor.effect_stats:
                raise ValueError("Initialize native characteristics before casting")
            plan = validate(
                struct.pack(">qqiih", identity, spell_uid, *target),
                character,
                preview,
                actor.owner_id,
                deck,
                wp=actor.effect_stats[4],
                line_of_sight=line_of_sight,
                conditional_context=lambda request, current: adapter.cast_condition(
                    current, request
                ),
            )
            eligible.append(dict(target=target, plan=plan))
            if len(eligible) == maximum_eligible:
                break
        except Exception as error:
            # Only explicit production rejection fields prove a known negative.
            # An arbitrary ValueError can mean absent authority, not an invalid
            # target; neither its type nor its message establishes eligibility.
            result = getattr(error, "native_casting_result", None)
            code = getattr(error, "cast_validation_code", None)
            known = (
                type(result) is str
                and result
                in {
                    "twE",
                    "twF",
                    "twG",
                    "twH",
                    "twI",
                    "twJ",
                    "twT",
                    "twU",
                    "twV",
                    "twX",
                    "twY",
                }
                or type(code) is str
                and code in {"insufficient_resources", "alignment_rejected"}
            )
            unknown = not known
            diagnostic = getattr(error, "native_casting_diagnostic", None)
            rejected.append(
                dict(
                    target=target,
                    status="validation_rejected",
                    error=type(error).__name__,
                    reason=str(error),
                    native_casting_result=result,
                    validation_code=code,
                    native_casting_diagnostic=diagnostic,
                    authority_unresolved=unknown,
                )
            )
            unresolved = unresolved or unknown
    status = (
        "eligible_targets_found"
        if eligible
        else "eligibility_authority_unresolved"
        if unresolved
        else "bounded_search_exhausted"
        if total > len(cells)
        else "no_eligible_context"
    )
    return dict(
        status=status,
        eligible=eligible,
        rejected=rejected,
        candidate_count=total,
        candidate_limit=limit,
        candidate_truncated=total > len(cells),
        checked_count=len(eligible) + len(rejected),
        search_complete=len(eligible) + len(rejected) == total,
    )
