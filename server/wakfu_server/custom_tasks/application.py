"""Selected-character task list application boundary, without socket side effects."""
import re
from . import presentation, service


def publication(
    store,
    account_id,
    generation,
    character_id,
    *,
    existing_packages,
    cap_reached,
    definitions=None
):
    """Return native13369 only after the owned selected-session transaction commits.

    Genuine gift packages and cap status are required explicit inputs. The caller
    must source them from its current server gift authority; supplying an empty
    tuple asserts that no genuine gifts exist. This function never queries an
    official account, accepts client progress, claims a gift, or sends packets.
    A caller may send the returned packet after return. Do not invoke from an
    existing character-held mutation transaction: lock_character orders session
    before character. Combat/planting should schedule a later refresh after their
    commit instead of calling this facade while holding gameplay fences.
    """
    if any(
        type(value) is not int or not 0 < value < 2**63
        for value in (account_id, character_id)
    ):
        raise ValueError("Invalid custom task publication owner")
    if type(generation) is not str or not re.fullmatch(r"[0-9a-f]{32}", generation):
        raise ValueError("Invalid custom task publication session generation")
    if type(existing_packages) not in (tuple, list) or type(cap_reached) is not bool:
        raise ValueError("Explicit genuine gift package list and cap status required")
    with store.connection() as db:
        # selected=True forbids projecting another owned hero under this lease.
        store.lock_character(db, account_id, generation, character_id, selected=True)
        snapshot = service.snapshot(db, account_id, character_id, definitions)
        packet = presentation.publication(
            snapshot, existing_packages=existing_packages, cap_reached=cap_reached
        )
    # Context exit commits first. Any commit failure propagates without a packet.
    return packet
