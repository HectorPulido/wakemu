"""Owned rail path accounting from byT/byU and dbe.a(byR).

This consumes an already validated requested path, rather than generating the
client mouse-projection/A* path. Physical legality remains the movement FSM's
responsibility. Team membership follows fcb.fg -> bL, not microbot ownership.
"""
from .combat_microbot_network import SOURCE
from .combat_casting_range import int32


def rail_path_cost(length, always_one):
    if type(length) is not int or length <= 0 or type(always_one) is not bool:
        raise ValueError("Invalid actual rail path accounting")
    return 1 if always_one else int32(int32(length + 3) - 1) // 3


def movement_cost(fight, actor, path):
    networks = getattr(fight, "native_microbot_networks", {})
    provider = getattr(fight, "native_rail_movement_authority", None)
    if not networks and provider is None:
        return len(path), False
    if not callable(provider) or not callable(getattr(provider, "properties", None)):
        raise ValueError("Missing actual rail movement actor authority")
    from .combat_runtime_adapter import NativeActorAuthority

    facts = provider(fight, actor)
    properties = provider.properties(fight, actor)
    if (
        not isinstance(facts, NativeActorAuthority)
        or type(facts.is_carried) is not bool
        or not isinstance(properties, frozenset)
    ):
        raise ValueError("Missing actual rail carry or PB snapshot")
    # Native byT delegates to ordinary movement before reading rail-only PB
    # whenever carried or MP<=0. Ordinary MP validation still follows.
    if facts.is_carried or actor.mp <= 0:
        return len(path), False
    cells = set()
    if not isinstance(networks, dict):
        raise ValueError("Malformed actual rail owner networks")
    for owner_id, network in networks.items():
        owner = fight.actors.get(owner_id)
        if owner is None:
            # fcb.bL does not recover actors absent from the roster.
            continue
        if owner.team != actor.team:
            continue
        if not isinstance(network, dict) or network.get("source") != SOURCE:
            raise ValueError("Missing actual rail network provenance")
        if not network.get("segments"):
            continue
        if not isinstance(network.get("cells"), list):
            raise ValueError("Missing actual rail membership")
        cells.update(tuple(cell) for cell in network["cells"])
    on_rail = (
        actor.position in cells
        and bool(path)
        and all(tuple(cell) in cells for cell in path)
    )
    always_one = 98 in properties
    usable = on_rail and (always_one or len(path) <= int32(actor.mp * 3))
    if usable:
        return rail_path_cost(len(path), always_one), True
    if 77 in properties:
        raise ValueError("Native movement is restricted to rails")
    return len(path), False
