"""Initial two-team turn order ported from client feq/fex/fet.

Only initial ordering is covered; summon insertion, delay, death and turn-state
mutations remain separate timeline operations. Inputs must reflect actual INIT
and effective level after effects, equipment and level adjustment.
"""


def _int32(value):
    return ((value + 2**31) % 2**32) - 2**31


def tie_hash(actor_id, fight_id, initiative):
    """fex.rG: low16 square, then mix lowest/highest bytes of signed int."""
    seed = (actor_id + fight_id + initiative) & 65535
    square = _int32(seed * seed)
    return (square & 255) ^ ((square >> 16) & 65280)


def _average(team):
    if not team:
        return 0
    total = 0
    for actor in team:
        total = _int32(total + actor["initiative"])
    return (abs(total) // len(team)) * (1 if total >= 0 else -1)


def initial_order(fight_id, actors):
    """Return actor IDs in original client order for teams0 and1.

    effective_level represents fex.bH = actor.drk() if positive else actor.drm().
    Caller selects eligible members: feq queries fight.bJ(team), so this function
    deliberately does not infer eligibility from HP, ID sign or summon status.
    """
    if type(fight_id) is not int or not -(2**31) <= fight_id < 2**31:
        raise ValueError("Invalid fight ID")
    teams = [[], []]
    seen = set()
    for actor in actors:
        for key in ("id", "team", "initiative", "effective_level"):
            if type(actor.get(key)) is not int:
                raise ValueError("Actor turn fields must be integers")
        if (
            actor["team"] not in (0, 1)
            or actor["id"] in seen
            or not -(2**63) <= actor["id"] < 2**63
        ):
            raise ValueError("Invalid or duplicate actor")
        if (
            not -(2**31) <= actor["initiative"] < 2**31
            or not -(2**15) <= actor["effective_level"] < 2**15
        ):
            raise ValueError("Invalid initiative or effective level")
        seen.add(actor["id"])
        teams[actor["team"]].append(actor)
    average = [_average(team) for team in teams]
    first = (
        1
        if average[1] > average[0]
        else 0
        if average[0] > average[1]
        else (1 if fight_id % 2 == 0 else 0)
    )
    for team in teams:
        team.sort(
            key=lambda a: (
                -a["initiative"],
                -a["effective_level"],
                tie_hash(a["id"], fight_id, a["initiative"]),
                a["id"],
            )
        )
    ordered = []
    index = 0
    while index < max(len(teams[0]), len(teams[1])):
        for number in (first, 1 - first):
            if index < len(teams[number]):
                ordered.append(teams[number][index]["id"])
        index += 1
    return ordered
