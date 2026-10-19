"""Post-commit mount updates for an existing world actor."""
from wakfu_server import wire
from .mount_inventory import actor_pet
from .mount_codec import dismounted, ride_result


def snapshot(character):
    """Restore riding only after the actor and its PET have been installed."""
    from .mount_inventory import equipped

    mounted = character.get("mount_state", {}).get("mounted", False)
    if type(mounted) is not bool:
        raise ValueError("Invalid authoritative riding state")
    if not mounted:
        return []
    if equipped(character) is None:
        raise ValueError("Mounted actor has no equipped mount")
    return [ride_result(character["id"], 0)]


def equipment_changes(template, previous, current):
    """Publish active equipment appearance and mount differences after commit.

    Callers supply owned snapshots before and after a successful transaction.
    Riding state must follow the PET refresh, which can recreate the mount.
    """
    if any(previous[key] != current[key] for key in ("id", "account_id")):
        raise ValueError("Mount publication belongs to another actor")
    before = previous.get("mount_state", {}).get("mounted", False)
    after = current.get("mount_state", {}).get("mounted", False)
    if type(before) is not bool or type(after) is not bool:
        raise ValueError("Invalid authoritative riding state")
    changed = actor_pet(previous) != actor_pet(current)
    packets = [wire.refresh_player(template, current)] if changed else []
    from .equipment_appearance import change_packet

    # A PET replacement already carries the complete canonical slot map.
    appearance = None if changed else change_packet(previous, current)
    if appearance is not None:
        packets.append(appearance)
    if changed or before != after:
        packets.append(
            ride_result(current["id"], 0) if after else dismounted(current["id"])
        )
    return packets
