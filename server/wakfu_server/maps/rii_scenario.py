"""Original client scenario events observed during the Rii introduction."""

import struct

SCENARIO = 2536
ENTRY = 22339
INTRO = 22360
INTRO_GUIDE = 22530
ECOLOGY_GUIDE = 22538
PLANTING_GUIDE = 22539
ZAAP_LEAVE = 22534


def packet(event):
    """Encode a qualified presentation event for the installed native script."""
    if event not in (
        ENTRY,
        INTRO,
        INTRO_GUIDE,
        ECOLOGY_GUIDE,
        PLANTING_GUIDE,
        ZAAP_LEAVE,
    ):
        raise ValueError("Unqualified Rii scenario event")
    return 13411, struct.pack(">BiiB", 0, event, SCENARIO, 0)


def finish_intro(connection, store, account_id, generation, character, *, in_combat):
    """Consume the owner connection's actual intro, then show the native guide."""
    if (
        getattr(connection, "pending_rii_intro", None) != character["id"]
        or (character["map_id"], character.get("instance_id", 0)) != (1385, 0)
        or in_combat
    ):
        raise ValueError("Rii introduction callback is not pending")
    from wakfu_server.characters import incarnam_completion

    packets = incarnam_completion.complete_after_rii_intro(
        store, account_id, generation, character
    )
    connection.pending_rii_intro = None
    return [*packets, packet(INTRO_GUIDE)]


def login_packets(character, state):
    """Resume the native entry scene if its final Incarnam objective is pending."""
    if (character.get("map_id"), character.get("instance_id", 0)) != (1385, 0):
        return []
    result = [packet(ENTRY)]
    if 5139 in state["running"] and 10568 not in state["objectives"]:
        result.append(packet(INTRO))
    else:
        from wakfu_server.achievements import incarnam_tutorial

        result.append(incarnam_tutorial.interface_recovery_packet())
    return result
