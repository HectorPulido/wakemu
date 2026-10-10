"""Native rK/rN/wU complete property counters, not a nullable placeholder."""
import struct

from .combat_property_stack import property_present


def fight_property_payload(counts):
    """eGp.zm replaces the client PB from this complete signed-byte snapshot."""
    property_present(counts, 0)
    return (
        b"\x01"
        + struct.pack(">H", len(counts))
        + b"".join(
            struct.pack(">bb", identity, count)
            for identity, count in sorted(counts.items())
        )
    )


def ordinary_monster_property_counts(monster, actor=None):
    if actor is not None:
        counts = getattr(actor, "native_fight_property_counts", None)
        if counts is not None:
            property_present(counts, 0)
            return counts
        if getattr(actor, "native_fight_properties", None) is not None:
            raise ValueError("Live native property set lacks counter population")
    from .combat_ordinary_authority import native_property_catalog
    from .combat_fight_property import property_registry

    row = native_property_catalog()["npc"].get(str(monster["ref"]))
    if row is None:
        raise ValueError("Missing ordinary NPC native property profile")
    return {
        identity: 1
        for identity in row["fight_properties"]
        if identity in property_registry()
    }
