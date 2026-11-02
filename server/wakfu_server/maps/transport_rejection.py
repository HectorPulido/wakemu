"""Keep a rejected atomic entrance payment outside scene replacement."""
from wakfu_server.dungeon_entry_payment import InsufficientEntranceItems


def requires_scene_recovery(error, *, transition_committed):
    """Only a known rolled-back payment can omit the legacy recovery snapshot.

    Native bEk restores input permission before sending cpJ12296. A missing
    payment is raised before the entrance transaction commits, so it needs
    feedback rather than another csW13974 world installation. Unknown errors,
    committed transitions and failed attach/delivery retain scene recovery.
    """
    return not (
        transition_committed is False and isinstance(error, InsufficientEntranceItems)
    )
