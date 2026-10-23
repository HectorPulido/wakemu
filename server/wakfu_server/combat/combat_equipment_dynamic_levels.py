"""Finite equipment child-level authority from a real owned fighter snapshot.

Item/container levels never stand in for the actor's native effective level.
The pin caller captures these facts after validating the actual owned fighter;
restoration and execution callers verify them before using the graph proof.
"""
from collections.abc import Mapping
from dataclasses import dataclass


class UnknownDynamicLevel(ValueError):
    """A valid native dynamic shape lacks its authoritative input domain."""


@dataclass(frozen=True)
class OwnerLevelFacts:
    fight_id: int
    actor_id: int
    owner_id: int
    effective_level: int

    def __post_init__(self):
        if (
            any(
                type(value) is not int
                for value in (
                    self.fight_id,
                    self.actor_id,
                    self.owner_id,
                    self.effective_level,
                )
            )
            or self.fight_id <= 0
            or self.actor_id <= 0
            or self.owner_id <= 0
            or not -32768 <= self.effective_level <= 32767
        ):
            raise ValueError("Malformed native equipment owner-level facts")

    @classmethod
    def capture(cls, fight, actor_id, owner_id):
        actor = fight.actors.get(actor_id)
        if (
            fight.phase != "active"
            or actor is None
            or actor.id != actor_id
            or actor.controlled is not True
            or actor.owner_id != owner_id
            or actor.hp <= 0
        ):
            raise UnknownDynamicLevel("Missing actual owned active equipment fighter")
        return cls(fight.id, actor_id, owner_id, actor.effective_level)

    def plain(self):
        return dict(
            version=1,
            fight_id=self.fight_id,
            actor_id=self.actor_id,
            owner_id=self.owner_id,
            effective_level=self.effective_level,
        )

    @classmethod
    def from_plain(cls, value):
        fields = {"version", "fight_id", "actor_id", "owner_id", "effective_level"}
        if (
            not isinstance(value, Mapping)
            or set(value) != fields
            or type(value.get("version")) is not int
            or value["version"] != 1
        ):
            raise ValueError("Malformed pinned native equipment owner-level facts")
        return cls(**{key: value[key] for key in fields - {"version"}})

    def verify(self, fight, *, allow_missing=False):
        if type(allow_missing) is not bool or fight.id != self.fight_id:
            return False
        actor = fight.actors.get(self.actor_id)
        if actor is None:
            # Removed fighters' static source definitions remain necessary for
            # retained inverse/departure cleanup. This does not grant execution
            # against an absent fighter or resolve an unknown target's level.
            return allow_missing
        return (
            actor.id == self.actor_id
            and type(actor.effective_level) is int
            and actor.effective_level == self.effective_level
        )


@dataclass(frozen=True)
class CompanionCustodyLevelFacts:
    """Owned inventory admission facts, never a combat execution authority.

    Custody can evaluate the native level formula before a fight exists.
    Ready must capture OwnerLevelFacts from the actual active NPC again; this
    record deliberately has no fight ID or pinned-source serialization API.
    """

    companion_id: int
    account_id: int
    owner_character_id: int
    breed_ref: int
    effective_level: int

    def __post_init__(self):
        if (
            any(
                type(value) is not int or value <= 0
                for value in (
                    self.companion_id,
                    self.account_id,
                    self.owner_character_id,
                    self.breed_ref,
                )
            )
            or type(self.effective_level) is not int
            or not 0 <= self.effective_level <= 32767
        ):
            raise ValueError("Malformed native companion custody level facts")

    @classmethod
    def capture(cls, companion, owner, level):
        from wakfu_server.companions import level_for_xp

        if (
            not isinstance(companion, Mapping)
            or not isinstance(owner, Mapping)
            or companion.get("account_id") != owner.get("account_id")
            or any(
                type(value) is not int or value <= 0
                for value in (
                    companion.get("id"),
                    companion.get("account_id"),
                    owner.get("id"),
                    companion.get("breed_ref"),
                )
            )
            or type(companion.get("xp")) is not int
            or companion["xp"] < 0
            or type(owner.get("level")) is not int
            or type(level) is not int
            or not 0 <= level <= min(level_for_xp(companion["xp"]), owner["level"])
        ):
            raise ValueError("Missing owned companion custody level authority")
        return cls(
            companion["id"],
            companion["account_id"],
            owner["id"],
            companion["breed_ref"],
            level,
        )


@dataclass(frozen=True)
class OwnerChildLevels:
    mode: object
    levels: tuple
    facts: OwnerLevelFacts | CompanionCustodyLevelFacts
    requires_context: tuple = ("native_owned_actor_level", "native_dynamic_child_level")


def group_child_levels(effect, level, facts):
    """Use native999 arithmetic only when its selected actor is invariant.

    No rebind plus parameter6==1 can use exact owned-caster facts. Other
    selections require the complete native output-type descendant proof;
    no owner level is substituted for a future target or rebound caster.
    """
    from wakfu_server.combat_definitions import effect_profile
    from wakfu_server.combat_effect_groups import decode_group_mode
    from wakfu_server.combat_level_group import level_group_override
    from wakfu_server.combat_native_events import validate_group_registration_flags

    if effect.get("effect_class") != 999:
        raise UnknownDynamicLevel(
            "No pinned actor-level authority for this dynamic family"
        )
    if facts is not None and type(facts) not in (
        OwnerLevelFacts,
        CompanionCustodyLevelFacts,
    ):
        raise UnknownDynamicLevel("Missing typed native equipment owner-level facts")
    raw = effect.get("parameters")
    count = effect.get("parameter_count")
    if (
        type(count) is not int
        or count not in (8, 10)
        or not isinstance(raw, (list, tuple))
        or len(raw) != 2 * count
    ):
        raise ValueError("Unknown native999 parameter shape")
    flags = effect.get("native_effect_flags")
    if not isinstance(flags, (list, tuple)):
        raise UnknownDynamicLevel("Missing exact native group flags")
    if 8 in flags and effect.get("_capability_reference") is None:
        raise UnknownDynamicLevel("Missing native target-order identity")
    # This validates the actual constructor flag contract without pretending
    # that a static parse is live active execution. The pin caller separately
    # captures a real active owner; execution keeps its actual phase guard.
    validate_group_registration_flags(
        flags,
        active=False,
        constructor=True,
        effect=effect,
        reference=effect.get("_capability_reference"),
    )
    values = effect_profile(effect, level)["parameters"]
    mode = decode_group_mode(values[:6], raw_target_parameter=raw[4])
    if (
        mode.actor_rebind
        or values[6] != 1
        or type(facts) not in (OwnerLevelFacts, CompanionCustodyLevelFacts)
    ):
        from .combat_equipment_selected_level_domain import SelectedChildLevels

        return SelectedChildLevels(mode)
    child_level = level_group_override(effect, level, facts.effective_level)
    if type(child_level) is not int or not -32768 <= child_level <= 32767:
        raise ValueError("Native group child level is not a signed short")
    return OwnerChildLevels(mode, (child_level,), facts)


def owner_child_levels(effect, level, facts):
    """Retain the exact-owner API; whole-domain graphs use group_child_levels."""
    proof = group_child_levels(effect, level, facts)
    if getattr(proof, "child_level_domain", None) is not None:
        raise UnknownDynamicLevel(
            "Native group level requires a complete selected-actor domain"
        )
    return proof


def source_level_facts(source):
    """Return optional digest-bound facts from an accepted equipment source."""
    value = source.get("_generic_owner_level_facts")
    return None if value is None else OwnerLevelFacts.from_plain(value)


def verify_source_level_facts(
    source, fight, *, actor_id=None, owner_id=None, allow_missing=False
):
    facts = source_level_facts(source)
    if facts is None:
        return True  # Legacy/non-dynamic sources have their existing authority.
    if (actor_id is not None and facts.actor_id != actor_id) or (
        owner_id is not None and facts.owner_id != owner_id
    ):
        return False
    return facts.verify(fight, allow_missing=allow_missing)
