"""Exact eJo/fcb.bJ membership and eKz native actor-type filters."""


def human_actor_type(value):
    if type(value) is not int or not -128 <= value < 128:
        raise ValueError("Missing native human-range actor type")
    return value in (0, 5)


def monsters_count(rows, team=-1, breed=-1):
    """fbX.e: native signed casts and short-sized collection result."""
    if type(team) is not int or type(breed) is not int:
        raise ValueError("Native monster count requires evaluated long arguments")
    team = (team + 128) % 256 - 128
    breed = (breed + 32768) % 65536 - 32768
    count = 0
    for actor_type, in_play, affiliation, reference in rows:
        if type(in_play) is not bool:
            raise ValueError("Missing native monster-count actor membership")
        if not in_play:
            continue
        if type(actor_type) is not int:
            raise ValueError("Missing native monster-count actor type")
        if actor_type not in (1, 2):
            continue
        if type(affiliation) is not int or type(reference) is not int:
            raise ValueError("Missing native monster-count affiliation/breed")
        if (team == -1 or affiliation == team) and (breed == -1 or reference == breed):
            count += 1
    return (count + 32768) % 65536 - 32768


def allies_membership(in_play, affiliation, reference_affiliation, properties):
    if type(in_play) is not bool:
        raise ValueError("Missing native allies-count membership")
    if any(
        type(value) is not int or not -128 <= value < 128
        for value in (affiliation, reference_affiliation)
    ):
        raise ValueError("Missing native allies-count affiliation")
    if not isinstance(properties, (set, frozenset)):
        raise ValueError("Missing native allies-count properties")
    return in_play and affiliation == reference_affiliation and 114 not in properties
