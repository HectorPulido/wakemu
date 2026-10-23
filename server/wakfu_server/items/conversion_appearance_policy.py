"""Explicit Wakemu preservation of valid appearances across native conversions.

Original fusion eligibility defines valid source and destination appearances.
Preserving one across a conversion is Wakemu policy, not recovered official
server inheritance. No appearance is granted or changed by this validator.
"""


def validate_target(db, source_reference, target_reference, appearance_reference):
    """Return an existing override only if both equipment models accept it."""
    if any(
        type(value) is not int or value <= 0
        for value in (source_reference, target_reference, appearance_reference)
    ):
        raise ValueError(
            "Appearance preservation requires positive template identities"
        )
    from .item_appearance_fusion import _target

    source = _target(db, source_reference)
    target = _target(db, target_reference)
    appearance = _target(db, appearance_reference)
    if not (
        source["normalized_type"]
        == target["normalized_type"]
        == appearance["normalized_type"]
    ):
        raise ValueError(
            "Converted appearance does not match both native equipment types"
        )
    if appearance["item_level"] > min(source["item_level"], target["item_level"]):
        raise ValueError("Converted appearance exceeds a native equipment level")
    return appearance_reference
