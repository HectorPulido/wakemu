"""eHR.d installation of a fresh bPq.cm descriptor into the lowest empty slot."""
from dataclasses import replace
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    CapturedCreature,
)


def add_fresh_capture(roster, profile):
    """Return native slot amount and immutable component; full roster returns -1.

    bPq.cm allocates a new bPs every time. Equal profile IDs therefore do not
    trigger eHR.d's Java object-identity duplicate check.
    """
    if not isinstance(roster, OwnedCapturedRoster):
        raise ValueError("Actual eHP.drI captured component required")
    if (
        not isinstance(profile, dict)
        or type(profile.get("profile_id")) is not int
        or not isinstance(profile.get("native_profile_name"), str)
    ):
        raise ValueError("Actual bPq descriptor profile/name required")
    slot = next(
        (index for index, entry in enumerate(roster.slots) if entry is None), -1
    )
    if slot == -1:
        return -1, roster
    slots, available = list(roster.slots), list(roster.available)
    slots[slot] = CapturedCreature(
        slot, profile["profile_id"], profile["native_profile_name"]
    )
    available[slot] = True
    return slot, replace(
        roster,
        slots=tuple(slots),
        available=tuple(available),
        selected_slot=slot if roster.free_slots == 10 else roster.selected_slot,
    )
