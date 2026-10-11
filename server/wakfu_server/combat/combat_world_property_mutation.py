"""Typed eGj.f/g world/fight manager mutation; no eHC timestamp writes."""
from .combat_property_stack import add_property, remove_property, property_present


def mutate_property_manager(counts, identity, *, namespace, applying, notify):
    """None denotes actual absent manager, not unknown counter authority."""
    if (
        type(namespace) is not int
        or namespace not in (0, 1)
        or type(applying) is not bool
        or not callable(notify)
    ):
        raise ValueError("Missing native typed property mutation authority")
    if counts is None:
        if namespace == 1 or not applying:
            return None
        counts = {}
    property_present(counts, identity)
    (add_property if applying else remove_property)(counts, identity)
    notify(identity, applying)
    return None if namespace == 0 and not applying and not counts else counts
