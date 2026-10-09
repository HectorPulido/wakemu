"""Scoped bje/bPD actions for freshly created class summons.

Fresh big creation initializes descriptor level before bje.aQc. The later
dsj half-level refresh is a distinct, currently unavailable producer.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache

from wakfu_server.paths import DATA_ROOT
from .combat_spell_level import NativeSpellBook


@lru_cache(maxsize=1)
def profile_abilities():
    from .combat_captured_dependencies import merge_profile_component
    from .combat_copy_dependencies import (
        merge_profile_component as merge_copy_component,
    )

    source = protocol_catalog.load(DATA_ROOT / "native-class-summon-abilities.json")[
        "profiles"
    ]
    return merge_copy_component(
        merge_profile_component(source, "abilities"), "abilities"
    )


def fresh_action_book(reference, level, *, profiles=None):
    """Return plain checkpoint-safe exact UID/reference/level records."""
    if type(reference) is not int or type(level) is not int or not 0 <= level <= 32767:
        raise ValueError("Invalid fresh native summon book source")
    profiles = profile_abilities() if profiles is None else profiles
    profile = profiles.get(str(reference))
    if not isinstance(profile, dict) or not isinstance(profile.get("abilities"), list):
        raise ValueError("Missing scoped native class summon ability profile")
    actions = []
    seen = set()
    for ability in profile["abilities"]:
        ref, uid, override, maximum = (
            ability.get(key)
            for key in ("reference", "casting_uid", "override_level", "maximum_level")
        )
        if (
            any(type(value) is not int for value in (ref, uid, override, maximum))
            or not 0 < ref < 1 << 31
            or uid != ref
            or ref in seen
            or not -1 <= override <= 32767
            or not 0 <= maximum <= 32767
        ):
            raise ValueError("Invalid complete native summon ability profile")
        seen.add(ref)
        actions.append(
            dict(
                uid=uid,
                reference=ref,
                level=min(level if override == -1 else override, maximum),
            )
        )
    return dict(
        producer="big.new_bje.bz.aQc.bPD",
        profile=reference,
        descriptor_level=level,
        actions=actions,
    )


def actor_action_book(actor):
    """Attest the complete fresh book against the native profile, not a deck."""
    source = getattr(actor, "native_summon_source", None)
    book = getattr(actor, "native_summon_action_book", None)
    if (
        isinstance(source, dict)
        and source.get("native_relation_source")
        == "big.new_bje.fdt_initial_registration"
        and getattr(actor, "native_character_copy_book_source", None) is not None
    ):
        from .combat_character_copy_runtime_book import validated_copied_action_book

        return validated_copied_action_book(actor, source)
    profiles = None
    if (
        isinstance(source, dict)
        and source.get("native_symbiot_source")
        == "eZr324.after_common_factory_and_fan.lE_true"
    ):
        from .combat_captured_profiles import native_captured_profiles

        profiles = native_captured_profiles()
    if (
        not isinstance(source, dict)
        or source.get("native_relation_source")
        != "big.new_bje.fdt_initial_registration"
        or not isinstance(book, dict)
        or book
        != fresh_action_book(source.get("ref"), source.get("level"), profiles=profiles)
    ):
        raise ValueError("Missing or changed fresh native summon action book")
    return book


def actor_spellbook(actor):
    book = actor_action_book(actor)
    return NativeSpellBook(
        {row["reference"]: row["level"] for row in book["actions"]}, False
    )


def validate_controlled_owner(fight, actor, character_id, owner_id):
    """Validate the actual registered controller chain to this character."""
    if fight.actors.get(actor.id) is not actor:
        raise ValueError("Caster is absent from the current native roster")
    registrations = getattr(fight, "native_summon_registrations", {})
    seen = set()
    current = actor
    while current.id != character_id:
        row = registrations.get(current.id)
        source = getattr(current, "native_summon_source", None)
        authority = row.get("authority") if isinstance(row, dict) else None
        if (
            current.id in seen
            or not isinstance(source, dict)
            or not isinstance(authority, dict)
            or row.get("actor_id") != current.id
            or authority.get("is_summon") is not True
            or authority.get("is_player") is not False
            or authority.get("breed_id") != source.get("ref")
            or authority.get("native_real_level") != source.get("level")
            or authority.get("summon_root_id") != character_id
            or row.get("controller_id") != source.get("controller_id")
            or row.get("controller_id")
            != getattr(current, "native_controller_id", None)
            or authority.get("native_controller_id") != row.get("controller_id")
            or not isinstance(authority.get("targeting"), dict)
            or authority["targeting"].get("dpr_id") != row.get("controller_id")
            or current.owner_id != owner_id
            or current.controlled is not True
        ):
            raise ValueError("Missing owned native summon controller authority")
        seen.add(current.id)
        current = fight.actors.get(row["controller_id"])
        if current is None:
            raise ValueError("Native summon controller is no longer registered")
    if current.owner_id != owner_id or current.controlled is not True:
        raise ValueError("Native summon controller belongs to another owner")


def resolve_controlled_action(fight, actor, character_id, owner_id, uid):
    """Authorize the exact registered actor's own action and controller chain."""
    validate_controlled_owner(fight, actor, character_id, owner_id)
    if type(uid) is not int:
        raise ValueError("Invalid native summon action UID")
    for action in actor_action_book(actor)["actions"]:
        if action["uid"] == uid:
            return action["reference"], action["level"]
    raise ValueError("Spell UID is absent from the summon-owned action book")
