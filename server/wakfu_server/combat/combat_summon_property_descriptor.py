"""Canonical eHN keys from the actual native summon constructor increments."""


def descriptor_property_keys(properties):
    """NativeSummonBuilder supplies distinct eZl.C map keys, not raw aMb flags."""
    if not isinstance(properties, frozenset) or any(
        type(identity) is not int or not 0 <= identity < 128 for identity in properties
    ):
        raise ValueError("Missing native constructed descriptor property keys")
    return tuple(sorted(properties))
