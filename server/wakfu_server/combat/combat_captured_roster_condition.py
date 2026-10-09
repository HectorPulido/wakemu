"""Original eON consumes only the actual caster eHP.drI owned component."""
from wakfu_server.characters.captured_roster import selected_availability_status
from wakfu_server.characters.captured_roster import OwnedCapturedRoster


def selected_creature_status(authority):
    if authority.native_is_ehp is not True:
        raise ValueError("Native eON requires actual eHP caster type")
    return selected_availability_status(authority.native_captured_roster)


def space_in_symbiot(authority):
    """eLm/eHR.fxp counts null descriptors among ten slots, not availability."""
    if authority.native_is_ehp is False:
        return -1
    if authority.native_is_ehp is not True:
        raise ValueError("Missing native eLm caster eHP type")
    roster = authority.native_captured_roster
    if not isinstance(roster, OwnedCapturedRoster):
        raise ValueError("Missing actual owned eHR component for symbiot space")
    return roster.free_slots


def breed_in_symbiot(authority, reference):
    """eMd: saturated positive short profile; all occupied slots, even unavailable."""
    if type(reference) is not int:
        raise ValueError("Native symbiot breed requires evaluated long")
    reference = max(-32768, min(32767, reference))
    if reference <= 0 or authority is None:
        return False
    if authority.native_is_ehp is False:
        return False
    if authority.native_is_ehp is not True:
        raise ValueError("Missing actual native eHP symbiot type")
    roster = authority.native_captured_roster
    if not isinstance(roster, OwnedCapturedRoster):
        raise ValueError("Missing actual owned eHR component for symbiot breed")
    return any(
        entry is not None and entry.profile_id == reference for entry in roster.slots
    )
