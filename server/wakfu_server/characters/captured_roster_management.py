"""Owned native cnu12014 release and cnv13068 rename persistence."""
from copy import copy
from dataclasses import replace
import struct

from .captured_roster import OwnedCapturedRoster
from .captured_roster_store import load, save


def decode_request(opcode, body):
    if not isinstance(body, bytes):
        raise ValueError("Captured management requires native bytes")
    if opcode == 12014:
        # cnu.aWH writes the slot BEFORE the owner, unlike cnw selection.
        if len(body) != 9:
            raise ValueError("Invalid native captured release payload")
        slot, owner_id = struct.unpack(">bq", body)
        name = None
    elif opcode == 13068:
        # cnv.aWH: long, byte, UTF-8 byte-count, bytes, boolean.
        if len(body) < 11:
            raise ValueError("Invalid native captured rename payload")
        owner_id, slot, size = struct.unpack_from(">qbB", body)
        if len(body) != 11 + size or body[-1] != 1:
            raise ValueError("Unsupported native captured rename payload")
        try:
            name = body[10:-1].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Invalid captured name UTF-8") from error
        # ddO sends an already normalized/checked name. No modern naming
        # grammar or unverified normalization is substituted on this path.
    else:
        raise ValueError("Unknown captured management request")
    if owner_id <= 0 or not 0 <= slot < 10:
        raise ValueError("Invalid owned captured management identity")
    return owner_id, slot, name


def release_slot(roster, slot):
    """Original eHR.eI descriptor deletion and selected-slot fallback."""
    if (
        not isinstance(roster, OwnedCapturedRoster)
        or type(slot) is not int
        or not 0 <= slot < 10
    ):
        raise ValueError("Owned captured release component required")
    slots, available = list(roster.slots), list(roster.available)
    slots[slot], available[slot] = None, False
    occupied = [index for index, entry in enumerate(slots) if entry is not None]
    selected = (
        -1
        if not occupied
        else occupied[0]
        if roster.selected_slot == slot
        else roster.selected_slot
    )
    return replace(
        roster, slots=tuple(slots), available=tuple(available), selected_slot=selected
    )


def rename_slot(roster, slot, name):
    if (
        not isinstance(roster, OwnedCapturedRoster)
        or type(slot) is not int
        or not 0 <= slot < 10
    ):
        raise ValueError("Owned captured rename component required")
    if not isinstance(name, str) or len(name.encode("utf-8")) > 255:
        raise ValueError("Invalid captured name wire length")
    entry = roster.slots[slot]
    if entry is None:
        raise ValueError("Captured rename descriptor is absent")
    slots = list(roster.slots)
    slots[slot] = replace(entry, name=name)
    return replace(roster, slots=tuple(slots))


def manage(store, account_id, generation, character, opcode, body, *, fight=None):
    owner_id, slot, name = decode_request(opcode, body)
    if (
        character.get("id") != owner_id
        or character.get("account_id") != account_id
        or character.get("breed") != 2
    ):
        raise ValueError("Foreign Osamodas management request")

    def mutation(record):
        roster = OwnedCapturedRoster.from_record(record, expected_owner_id=owner_id)
        return (
            release_slot(roster, slot)
            if opcode == 12014
            else rename_slot(roster, slot, name)
        )

    if fight is None:
        with store.connection() as db:
            store.lock_character(db, account_id, generation, owner_id)
            roster = mutation(load(db, character))
            save(db, character, roster)
        # Publish the caller's character component only after durable commit.
        return roster.to_record()

    actor = fight.actors.get(owner_id)
    if (
        actor is None
        or actor.controlled is not True
        or actor.owner_id != account_id
        or getattr(actor, "pve_withdrawn", False)
    ):
        raise ValueError("Missing active owned Osamodas management actor")
    overlays = getattr(fight, "native_captured_rosters", {})
    updates = getattr(fight, "native_captured_roster_updates", {})
    if not isinstance(overlays, dict) or not isinstance(updates, dict):
        raise ValueError("Invalid captured management checkpoint component")
    source = overlays.get(
        str(owner_id), updates.get(str(owner_id), character.get("captured_roster"))
    )
    record = mutation(source).to_record()
    if opcode == 12014:
        # Native eHR.pY must stop finding the descriptor's retired actorUID;
        # clearing a slot does not delete the historical summoned actor.
        from wakfu_server.combat_captured_descriptor_binding import (
            clear_descriptor_actor,
        )

        candidate = copy(fight)
        clear_descriptor_actor(candidate, owner_id, slot)
        bindings = candidate.native_captured_descriptor_actor_ids
    else:
        bindings = None
    fight.native_captured_rosters = {**overlays, str(owner_id): record}
    fight.native_captured_roster_updates = {**updates, str(owner_id): record}
    if bindings is not None:
        fight.native_captured_descriptor_actor_ids = bindings
    return record
