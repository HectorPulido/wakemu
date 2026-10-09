"""Native class-capture profile metadata, selected only by actual owned roster."""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import dataclass
from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT
from wakfu_server.characters.captured_roster import CapturedCreature
from wakfu_server.combat_summon_spellbook import fresh_action_book


@lru_cache(maxsize=1)
def native_captured_profiles():
    path = DATA_ROOT / "native-class-captured-profiles.json"
    if not protocol_catalog.exists(path):
        raise ValueError("Missing scoped original native captured profile source")
    document = protocol_catalog.load(path)
    if document.get("schema") != "owned-captured-native-profiles-v1":
        raise ValueError("Unverified native captured profile schema")
    if (
        document.get("seed_identity", {}).get("schema")
        != "native-capturable-class-profile-seeds-v1"
    ):
        raise ValueError("Missing original class capture capability domain")
    profiles = document["profiles"]
    expected = {
        str(reference) for reference in document["seed_identity"]["profile_ids"]
    }
    if set(profiles) != expected:
        raise ValueError("Incomplete scoped native captured profile export")
    for key, profile in profiles.items():
        if (
            profile.get("profile_id") != int(key)
            or 40 not in profile["fight_properties"]
            or 28 in profile["fight_properties"]
            or not isinstance(profile.get("abilities"), list)
            or len(profile["initial_state_triples"]) % 3
            or type(profile.get("descriptor_initial_hp")) is not int
        ):
            raise ValueError("Invalid original native captured profile metadata")
        fresh_action_book(int(key), 0, profiles=profiles)
    return profiles


@dataclass(frozen=True)
class NativeCapturedDescriptor:
    entry: CapturedCreature
    owner_id: int
    level: int
    actor_id: int
    minimum_hp: int
    profile: dict


def captured_descriptor(entry, *, owner_id, level, actor_id, profiles=None):
    if not isinstance(entry, CapturedCreature):
        raise ValueError("Actual owned captured descriptor entry required")
    profiles = native_captured_profiles() if profiles is None else profiles
    profile = profiles.get(str(entry.profile_id))
    if not isinstance(profile, dict) or profile.get("profile_id") != entry.profile_id:
        raise ValueError(
            "Owned captured profile is outside imported native class domain"
        )
    if type(level) is not int or not 0 <= level <= 32767:
        raise ValueError("Missing actual native caster descriptor level")
    if (
        type(owner_id) is not int
        or type(actor_id) is not int
        or not 0 < actor_id < (1 << 63)
    ):
        raise ValueError("Missing actual captured descriptor identities")
    return NativeCapturedDescriptor(
        entry, owner_id, level, actor_id, profile["descriptor_initial_hp"], profile
    )


def initialize_captured_descriptor(actor, descriptor, *, definitions):
    """Native eHD.a minimum-HP override/name, before inheritance and registration."""
    if (
        not isinstance(descriptor, NativeCapturedDescriptor)
        or actor.id != descriptor.actor_id
    ):
        raise ValueError("Actual native captured descriptor initialization required")
    if (
        not isinstance(actor.effect_stats, dict)
        or 1 not in actor.effect_stats
        or not isinstance(actor.effect_minima, dict)
        or 1 not in actor.effect_minima
        or not isinstance(actor.effect_maxima, dict)
        or 1 not in actor.effect_maxima
        or actor.effect_frozen is None
    ):
        raise ValueError("Missing actual captured HP PA source")
    # Original fff.on ignores frozen PA and clamps to native minimum/current
    # maximum, or hard upper bound for expandable PA. No effect runner used.
    if descriptor.minimum_hp > 0 and 1 not in actor.effect_frozen:
        from .combat_hp_raw import hp_raw_present, set_hp_raw_current

        if hp_raw_present(actor):
            # eHD.a calls PA.on: preserve the original raw operand alongside
            # effective HP before fan reads/scales that same PA component.
            set_hp_raw_current(actor, descriptor.minimum_hp)
        else:
            row = definitions["1"]
            maximum = (
                row["hard_maximum"] if row["expandable"] else actor.effect_maxima[1]
            )
            actor.effect_stats[1] = max(
                actor.effect_minima[1], min(maximum, descriptor.minimum_hp)
            )
            actor.hp = actor.effect_stats[1]
    actor.native_captured_name = descriptor.entry.name
    actor.native_captured_descriptor = dict(
        profile_id=descriptor.entry.profile_id,
        owner_id=descriptor.owner_id,
        minimum_hp=descriptor.minimum_hp,
        level=descriptor.level,
        actor_id=descriptor.actor_id,
        name=descriptor.entry.name,
        direction=-1,
        native_source="bPq.cm -> bPs/eHD; stored yS descriptor",
    )
