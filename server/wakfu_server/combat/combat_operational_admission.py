"""Optional local release holds before allocating any combat state."""
import os


def require_operational_encounter(members):
    raw = os.environ.get("WAKFU_COMBAT_HELD_REFERENCES", "").strip()
    if not raw:
        return
    try:
        held = {int(value.strip()) for value in raw.split(",")}
        if any(reference <= 0 for reference in held):
            raise ValueError
    except ValueError as error:
        raise ValueError("Invalid server combat release configuration") from error
    if any(member["ref"] in held for member in members):
        raise ValueError(
            "This encounter is temporarily unavailable in this local release."
        )
