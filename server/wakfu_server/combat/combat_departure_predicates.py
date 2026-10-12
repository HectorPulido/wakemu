"""Native eGz departure fields, independent of HP, retirement and team."""
SOURCE = "native.eGz.pHJ.pHK.v1"
WRITERS = {"fresh.eGz.constructor", "eGj.lt", "eGj.lC", "eGn.pW.Ui"}


def _validated(actor):
    if type(actor.id) is not int:
        raise ValueError("Invalid native departure actor identity")
    value = getattr(actor, "native_departure_flags", None)
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"source", "actor_id", "abandonning", "fleeing", "writers"}
        or value["source"] != SOURCE
        or type(value["actor_id"]) is not int
        or value["actor_id"] != actor.id
        or not isinstance(value["writers"], dict)
        or set(value["writers"]) != {"abandonning", "fleeing"}
    ):
        raise ValueError("Malformed native departure-field authority")
    for name in ("abandonning", "fleeing"):
        if type(value[name]) is not bool or value["writers"][name] not in WRITERS:
            raise ValueError("Missing native departure-field writer")
    return value


def initialize_fresh_departure_flags(actor):
    if type(actor.id) is not int:
        raise ValueError("Invalid fresh native actor identity")
    if getattr(actor, "native_departure_flags", None) is not None:
        raise ValueError("Fresh departure fields already initialized")
    actor.native_departure_flags = dict(
        source=SOURCE,
        actor_id=actor.id,
        abandonning=False,
        fleeing=False,
        writers=dict(
            abandonning="fresh.eGz.constructor", fleeing="fresh.eGz.constructor"
        ),
    )


def query(actor, name):
    if name not in ("abandonning", "fleeing"):
        raise ValueError("Unknown native departure field")
    value = _validated(actor)
    return None if value is None else value[name]


def _write(actor, name, value, writer):
    current = _validated(actor)
    if current is None or type(value) is not bool:
        raise ValueError("Missing actual departure-field mutation authority")
    current[name] = value
    current["writers"][name] = writer


def set_abandonning(actor, value):
    """Actual eGj.lt(bool) -> eGZ.lt -> eGz.pHJ."""
    _write(actor, "abandonning", value, "eGj.lt")


def set_fleeing(actor, value):
    """Actual eGj.lC(bool) -> eGZ.lJ -> eGz.pHK."""
    _write(actor, "fleeing", value, "eGj.lC")


def hydrate_fleeing_from_pW(actor, payload):
    """Only the recovered eGn field Ui; other payload fields remain unrelated."""
    if (
        not isinstance(payload, dict)
        or set(payload) != {"source", "actor_id", "Ui"}
        or payload["source"] != "native.pW.Ui"
        or type(payload["actor_id"]) is not int
        or type(actor.id) is not int
        or payload["actor_id"] != actor.id
    ):
        raise ValueError("Missing actual pW.Ui hydration authority")
    _write(actor, "fleeing", payload["Ui"], "eGn.pW.Ui")


def restore_departure_flags(actor, snapshot):
    """Typed checkpoint restoration; no fresh defaults for unknown old actors."""
    from copy import deepcopy

    previous = getattr(actor, "native_departure_flags", None)
    actor.native_departure_flags = deepcopy(snapshot)
    try:
        _validated(actor)
    except Exception:
        if previous is None:
            del actor.native_departure_flags
        else:
            actor.native_departure_flags = previous
        raise
