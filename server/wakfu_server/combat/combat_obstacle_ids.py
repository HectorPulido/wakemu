"""Fight-local QI.O byte identities; actor UID64 and affiliation are separate."""


def assign_obstacle_ids(actors):
    actors = list(actors)
    used = set()
    for actor in actors:
        value = getattr(actor, "native_obstacle_id", None)
        if value is None:
            continue
        if type(value) is not int or not 0 <= value <= 126 or value in used:
            raise ValueError("Invalid or duplicate native obstacle byte identity")
        used.add(value)
    if len(actors) > 127:
        raise ValueError("Native fight obstacle byte capacity exceeded")
    available = iter(i for i in range(127) if i not in used)
    for actor in actors:
        if getattr(actor, "native_obstacle_id", None) is None:
            value = next(available, None)
            if value is None:
                raise ValueError("Native fight obstacle byte capacity exceeded")
            actor.native_obstacle_id = value


def obstacle_id(actor):
    value = getattr(actor, "native_obstacle_id", None)
    if type(value) is not int or not 0 <= value <= 126:
        raise ValueError("Missing native obstacle byte identity")
    return value
