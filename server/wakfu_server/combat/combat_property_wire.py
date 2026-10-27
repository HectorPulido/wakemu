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


def _fighter_property_section(snapshot):
    """Read the original full2/full3 rK boundary after its complete PC table."""
    if not isinstance(snapshot, bytes) or not snapshot or snapshot[0] not in (2, 3):
        raise ValueError("Native property refresh requires full fighter data")
    offset = 31 + (8 if snapshot[0] == 3 else 0)
    if len(snapshot) < offset + 2:
        raise ValueError("Truncated native fighter characteristics")
    count = struct.unpack_from(">H", snapshot, offset)[0]
    offset += 2 + count * 17
    if offset >= len(snapshot) or snapshot[offset] not in (0, 1):
        raise ValueError("Missing native fighter property component")
    present = snapshot[offset] == 1
    offset += 1
    counts = None
    if present:
        if len(snapshot) < offset + 2:
            raise ValueError("Truncated native fighter property count")
        count = struct.unpack_from(">H", snapshot, offset)[0]
        offset += 2
        end = offset + 2 * count
        if len(snapshot) < end:
            raise ValueError("Truncated native fighter property counters")
        pairs = list(struct.iter_unpack(">bb", snapshot[offset:end]))
        counts = dict(pairs)
        if len(counts) != len(pairs):
            raise ValueError("Duplicate native fighter property counter")
        offset = end
    if len(snapshot) < offset + 2:
        raise ValueError("Missing native fighter breed after properties")
    return counts, struct.unpack_from(">h", snapshot, offset)[0]


def _current_counts(actor, attribute, presence_attribute, fallback):
    counts = getattr(actor, attribute, None)
    presence = getattr(actor, presence_attribute, None)
    if counts is None:
        counts = fallback()
    property_present(counts, 0)
    if presence is not None and frozenset(presence) != frozenset(
        identity for identity, value in counts.items() if value != 0
    ):
        raise ValueError("Live native property counters disagree with presence")
    return dict(counts)


def actor_property_snapshot(full_snapshot, actor):
    """Format26 supplies BOTH complete live PB populations after a PC refresh.

    Null WORLD_PROPERTIES clears the original eGj world manager. Never use a
    nullable placeholder to mean unchanged. Profile fallback is permitted only
    when it agrees with any retained live presence; existing counters always win.
    """
    encoded_fight, breed = _fighter_property_section(full_snapshot)
    profile_cache = []

    def profile_counts(domain):
        from .combat_ordinary_authority import native_property_catalog
        from .combat_property_stack import add_property

        if not profile_cache:
            catalog = native_property_catalog()
            profile = (
                catalog["player"]
                if full_snapshot[0] == 3
                else catalog["npc"].get(str(breed))
            )
            if not isinstance(profile, dict):
                raise ValueError("Missing actual native property profile")
            profile_cache.append(profile)
        values = profile_cache[0].get(domain)
        if not isinstance(values, (tuple, list)):
            raise ValueError("Missing native profile property population")
        counts = {}
        for identity in values:
            add_property(counts, identity)
        return counts

    fight = _current_counts(
        actor,
        "native_fight_property_counts",
        "native_fight_properties",
        lambda: encoded_fight
        if encoded_fight is not None
        else profile_counts("fight_properties"),
    )

    def legacy_world_counts():
        counts = profile_counts("world_properties")
        presence = getattr(actor, "native_world_properties", None)
        baseline = frozenset(
            identity for identity, value in counts.items() if value != 0
        )
        source = getattr(actor, "native_summon_source", None)
        # Before world counters were checkpointed, the common eHD constructor
        # retained its profile plus exactly one inherited category0/property47.
        # Every dynamic world mutation materializes a full counter map. Do not
        # infer arbitrary stack counts from presence or an ambiguous baseline47.
        if (
            full_snapshot[0] == 2
            and 47 not in counts
            and presence is not None
            and frozenset(presence) == baseline | {47}
            and isinstance(source, dict)
            and type(source.get("ref")) is int
            and source["ref"] == breed
            and source.get("native_relation_source")
            == "big.new_bje.fdt_initial_registration"
            and source.get("native_symbiot_source")
            in (
                "eZl.new_eHD.pRO_false",
                "eZr324.after_common_factory_and_fan.lE_true",
            )
        ):
            from .combat_property_stack import add_property

            add_property(counts, 47)
        return counts

    world = _current_counts(
        actor,
        "native_world_property_counts",
        "native_world_properties",
        legacy_world_counts,
    )
    return b"\x1a" + fight_property_payload(world) + fight_property_payload(fight)
