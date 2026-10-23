"""Post-commit mount updates for an existing world actor."""
import struct
from .mount_inventory import actor_pet
from .mount_codec import dismounted, ride_result


def pet_packet(character):
    """eHf29 selects ID then PET, carried by csZ13046 for an existing actor."""
    from wakfu_server.combat_world_refresh import actor_refresh

    return actor_refresh(
        character["id"],
        b"\x1d" + struct.pack(">q", character["id"]) + actor_pet(character),
    )


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
    packets = []
    if changed:
        # eHf.FOR_REMOTE_PET_UPDATE29 carries ID and PET only. A complete
        # format10 actor also replays equipment characteristics on the client.
        packets.append(pet_packet(current))
    from .equipment_appearance import change_packet

    appearance = change_packet(previous, current)
    if appearance is not None:
        packets.append(appearance)
    if changed or before != after:
        packets.append(
            ride_result(current["id"], 0) if after else dismounted(current["id"])
        )
    return packets
