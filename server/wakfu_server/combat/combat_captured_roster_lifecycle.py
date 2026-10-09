"""biB.dnN -> eHR/bPo.fxn: restore availability during owned PC teardown."""
from dataclasses import replace
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    roster_from_character,
)


def reset_availability(roster):
    """Original bPo.fxn fills all ten pUF entries, including empty slots."""
    if not isinstance(roster, OwnedCapturedRoster):
        raise ValueError("Actual owned captured component required")
    return replace(roster, available=(True,) * 10)


def restore_departing_roster(fight, character):
    """Caller must be the actual owned PC dnN-equivalent teardown boundary.

    This does not run for a captured actor recall859 or ordinary turn expiry.
    The whole input is validated before publishing plain checkpoint records.
    """
    if character.get("breed") != 2:
        return False
    identity = character["id"]
    overlays = getattr(fight, "native_captured_rosters", {})
    updates = getattr(fight, "native_captured_roster_updates", {})
    if not isinstance(overlays, dict) or not isinstance(updates, dict):
        raise ValueError("Malformed owned captured checkpoint component")
    key = str(identity)
    if key in overlays:
        source = OwnedCapturedRoster.from_record(
            overlays[key], expected_owner_id=identity
        )
    elif key in updates:
        source = OwnedCapturedRoster.from_record(
            updates[key], expected_owner_id=identity
        )
    else:
        source = roster_from_character(character)
    if source is None:
        return False  # biB.dnN skips a null dqy component.
    actor = fight.actors.get(identity)
    if (
        actor is None
        or actor.controlled is not True
        or type(actor.owner_id) is not int
        or type(character["account_id"]) is not int
        or actor.owner_id != character["account_id"]
    ):
        raise ValueError("Missing actual departing owned player authority")
    record = reset_availability(source).to_record()
    fight.native_captured_rosters = {**overlays, key: record}
    fight.native_captured_roster_updates = {**updates, key: record}
    return True


def release_captured_slot_on_retirement(fight, actor, owner_id, slot):
    """eGj.ad/eHU.pZ/Z(slot,true) component step after attested retirement.

    The caller owns the Wakemu settled-death policy and QI spatial removal.
    This source-backed component step preserves descriptors and selection.
    """
    if type(owner_id) is not int or type(slot) is not int or not 0 <= slot < 10:
        raise ValueError("Invalid captured retirement owner/slot")
    source = getattr(actor, "native_summon_source", None)
    registrations = getattr(fight, "native_summon_registrations", {})
    row = registrations.get(actor.id) if isinstance(registrations, dict) else None
    authority = row.get("authority") if isinstance(row, dict) else None
    owner = fight.actors.get(owner_id)
    if (
        fight.actors.get(actor.id) is not actor
        or owner is None
        or not isinstance(source, dict)
        or not isinstance(authority, dict)
        or source.get("native_symbiot_source")
        != "eZr324.after_common_factory_and_fan.lE_true"
        or source.get("native_captured_owner_id") != owner_id
        or source.get("native_captured_slot") != slot
        or source.get("caster_id") != owner_id
        or source.get("native_relation_source")
        != "big.new_bje.fdt_initial_registration"
        or authority.get("native_summoned_from_symbiot") is not True
        or authority.get("breed_id") != source.get("ref")
        or authority.get("native_real_level") != source.get("level")
        or row.get("actor_id") != actor.id
        or actor.owner_id != owner.owner_id
    ):
        raise ValueError("Missing actual captured retirement descriptor authority")
    overlays = getattr(fight, "native_captured_rosters", {})
    updates = getattr(fight, "native_captured_roster_updates", {})
    if not isinstance(overlays, dict) or not isinstance(updates, dict):
        raise ValueError("Malformed captured retirement checkpoint component")
    key = str(owner_id)
    original = overlays.get(key, updates.get(key))
    if original is None:
        raise ValueError("Missing actual captured retirement roster")
    roster = OwnedCapturedRoster.from_record(original, expected_owner_id=owner_id)
    descriptor = roster.slots[slot]
    if descriptor is None or descriptor.profile_id != source.get("ref"):
        raise ValueError("Captured retirement slot descriptor changed")
    if roster.available[slot]:
        return False  # Already released; no duplicate update or descriptor mutation.
    flags = list(roster.available)
    flags[slot] = True
    record = replace(roster, available=tuple(flags)).to_record()
    fight.native_captured_rosters = {**overlays, key: record}
    fight.native_captured_roster_updates = {**updates, key: record}
    return True
