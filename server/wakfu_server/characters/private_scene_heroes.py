"""Restore native private-scene movement roles after a completed hero swap."""

from wakfu_server.haven_bag import HavenBagSession, entry_result
from wakfu_server.haven_ranch import RanchSession


def messages(session, character, *, generation):
    """Return post-12054 role packets without resetting the current map.

    Native dbY copies the previous actor's active bpq bag model. Its path filter
    compares character IDs, so the selected hero must receive its own role.
    Ranch entry already unregisters chk and clears the active bpq reference.
    Repeating 13019 would dereference that cleared reference in the client.
    Hero swaps copy the empty reference. 13307 binds the authorized bag
    model to the selected actor, preserving real host data for public guests.
    """
    if session is None:
        return ()
    if not isinstance(session, (HavenBagSession, RanchSession)) or not session.owns(
        character
    ):
        raise ValueError("Hero private-scene role requires its current session")
    if isinstance(session, RanchSession):
        session.validate_lease(generation)
        return ()
    return (
        (
            13307,
            entry_result(
                success=True,
                own=session.is_owner,
                owner=None if session.is_owner else session.owner,
            ),
        ),
    )
