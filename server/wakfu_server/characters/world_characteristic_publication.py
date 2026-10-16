"""Publish exploration characteristics with native owned-build invalidation."""

from wakfu_server import builds


def packets(character, snapshot):
    """Flush native maximum-only changes without changing authoritative values.

    The caller must be in exploration and must already have installed this
    character's build registries and selected build. Native same-build selection
    notifies the existing characteristic wrappers, even when current HP did not
    change. Removing and reapplying equipment can temporarily clamp AP/MP/WP;
    replaying the identical authoritative snapshot restores those resources.
    This must not be used for an actor attached to a fight.
    """
    if character.get("level") is None:
        raise ValueError("World characteristic publication requires an owned actor")
    if (
        not isinstance(snapshot, tuple)
        or len(snapshot) != 2
        or type(snapshot[0]) is not int
        or not isinstance(snapshot[1], bytes)
    ):
        raise ValueError(
            "World characteristic publication requires an encoded snapshot"
        )
    selection = builds.selection_message(character)
    return snapshot, selection, snapshot
