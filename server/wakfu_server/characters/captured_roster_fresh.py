"""Explicit newly constructed biB.dqt Symbiot source, never persistence recovery."""
from .captured_roster import OwnedCapturedRoster


def initialize_fresh_character_roster(character):
    """Apply native fresh PC initialization before any captured roster hydration."""
    if not isinstance(character, dict) or type(character.get("id")) is not int:
        raise ValueError("Fresh owned PC identity required")
    if "captured_roster" in character:
        raise ValueError("Fresh Symbiot initialization cannot replace hydrated state")
    if character.get("breed") == 2:
        # biB.dqt allocates bPo/eHR: ten null descriptors, false availability,
        # JVM-default selected slot zero. No creature catalog is consulted.
        character["captured_roster"] = OwnedCapturedRoster(character["id"]).to_record()
    return character
