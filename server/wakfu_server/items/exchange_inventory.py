"""Authoritative reconciliation after the native client's optimistic closure.

cuG0 clones offered units retaining source UID and performs its own merges.
Replace the native BAGS section and full UID registry from committed SQL,
so partial transfers reconcile receiving UIDs without item-loss notifications.
No actor-wide entity or combat state is replaced by this adapter.
"""
from .inventory_items import equipment_inventory
from .inventory_move import synchronization


def packets(character, transfers):
    """Replace bags and the full registry with authoritative owned units.

    This sequence requires a live generation-scoped socket. If a write fails,
    close that socket and recover through normal owned inventory bootstrap;
    do not repeat optimistic closure on the same connection.
    """
    identity = character["id"]
    current = character.get("inventory_items")
    if current is None or any(item["character_id"] != identity for item in current):
        raise ValueError("Foreign exchange inventory snapshot")
    previous = transfers.get("previous_uids", {}).get(str(identity))
    offered = transfers.get("offered_uids")
    if not isinstance(previous, list) or not isinstance(offered, list):
        raise ValueError("Missing exchange inventory reconciliation receipt")
    # cwP removals emit selfDrop messages even for units still owned. Native
    # BAGS format35 replaces the section quietly; the following full registry
    # restores rich ProtoItem/ProtoPet metadata omitted by binary bag items.
    return [synchronization(character), equipment_inventory(character)]
