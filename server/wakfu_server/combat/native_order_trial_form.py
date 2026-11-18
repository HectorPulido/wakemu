"""Opt-in order-trial preparation through original state3049/eWG118992.

This module publishes no encounter. The original selected mode proof and an
enabled admission document are prerequisites; native state retention installs
the temporary command book. Base player progression is never copied or edited.
"""

from dataclasses import dataclass
from collections.abc import Mapping

SPELLS = (4535, 4538, 4537, 4536)


@dataclass(frozen=True)
class FormPlan:
    owner_id: int
    account_id: int
    instance_id: int
    encounter_id: int
    admission_sha256: str
    native_profile_sha256: str
    mode: str
    book: tuple


def prepare_form(proof, *, encounter_id, character, value=None, profiles=None):
    """Prepare an original mode's native SELF state, without mutating combat."""
    from wakfu_server import native_order_trial_admission as admission
    from .combat_morph_spellbook import build_morph_book, native_morph_profiles

    value = admission.document() if value is None else admission.validate(value)
    if (
        value["enabled"] is not True
        or not isinstance(proof, admission.Admission)
        or proof.profile_id != value["id"]
        or proof.profile_sha256 != admission.digest(value)
        or proof.generation is None
        or proof.mode not in ("normal", "hard")
        or proof.hard_mode is not (proof.mode == "hard")
        or type(encounter_id) is not int
        or encounter_id <= 0
        or type(proof.instance_id) is not int
        or proof.instance_id <= 0
        or (
            character.get("id"),
            character.get("account_id"),
            character.get("instance_id"),
            character.get("map_id"),
        )
        != (
            proof.owner_id,
            proof.account_id,
            proof.instance_id,
            value["context"]["map_id"],
        )
    ):
        raise ValueError("Order form requires its enabled selected native mode")
    source = value["sources"][proof.mode]
    effects = [
        e
        for g in source["descriptor"]["groups"]
        for a in g["actions"]
        for e in a["effects"]
    ]
    if (
        proof.source_id != source["object_id"]
        or proof.source_map_id != source["map_id"]
        or proof.descriptor_sha256 != source["descriptor_sha256"]
        or len(effects) != 1
        or proof.effect_reference != effects[0]["action_reference"]
    ):
        raise ValueError("Order form lost its original mode source")
    profiles = native_morph_profiles() if profiles is None else profiles
    native = profiles.get("3217")
    if (
        not isinstance(native, dict)
        or native.get("profile_id") != 3217
        or native.get("minimum_level") != 1
        or tuple(row.get("reference") for row in native.get("abilities", ())) != SPELLS
        or any(
            row.get("casting_uid") != row.get("reference")
            or row.get("override_level") != -1
            for row in native["abilities"]
        )
    ):
        raise ValueError("Order form lacks its original native3217 command book")
    book = tuple(build_morph_book(native, 1).items())
    if book != tuple((ref, 1) for ref in SPELLS):
        raise ValueError("Order form changed its native descriptor-level book")
    return FormPlan(
        proof.owner_id,
        proof.account_id,
        proof.instance_id,
        encounter_id,
        proof.profile_sha256,
        admission.digest(native),
        proof.mode,
        book,
    )


def apply_form(dispatcher, plan, *, instance_id, value=None):
    """Run the actual native3049 carrier; never synthesize an effect933."""
    from wakfu_server import native_order_trial_admission as admission
    from .combat_definitions import effect_profile, state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload
    from .combat_morph_spellbook import morph_record, native_morph_profiles

    value = admission.document() if value is None else admission.validate(value)
    if (
        not isinstance(plan, FormPlan)
        or instance_id != plan.instance_id
        or value["enabled"] is not True
        or admission.digest(value) != plan.admission_sha256
    ):
        raise ValueError("Order form belongs to another owned instance")
    handler, retention = dispatcher.native_state_handler, dispatcher.native_retention
    fight = handler.fight
    actor = fight.actors.get(plan.owner_id)
    if (
        fight.id != plan.encounter_id
        or retention.fight is not fight
        or fight.phase not in ("placement", "active")
        or actor is None
        or actor.owner_id != plan.account_id
        or actor.controlled is not True
        or actor.hp <= 0
        or admission.digest(native_morph_profiles().get("3217"))
        != plan.native_profile_sha256
    ):
        raise ValueError("Order form lost its actual registered combat owner")
    native = state_profile(handler.catalog, 3049, 1)
    edge = handler.catalog["effects"].get("118992")
    if (
        native["duration"] != -1
        or native["realtime_duration"] != -1000
        or 118992 not in native["effects"]
        or not isinstance(edge, Mapping)
        or edge.get("effect_class") != 933
        or effect_profile(edge, 1)["parameters"] != [3217]
    ):
        raise ValueError("Order form lacks its original state3049 to118992 edge")
    current = morph_record(fight, actor.id)
    existing = any(row.reference == 3049 for row in actor.state_ledger.entries)
    if existing or current is not None:
        if (
            existing
            and current is not None
            and current["profile_id"] == 3217
            and tuple(current["levels"].items()) == plan.book
        ):
            return False
        raise ValueError("Order form cannot overwrite another temporary book")
    invocation = EffectInvocation(
        2226,
        1,
        actor.id,
        actor.id,
        actor.position,
        native_retained_container={"present": False},
    )
    carrier = StateCarrierContext(
        native["duration"],
        native["realtime_duration"],
        False,
        None,
        None,
        False,
        False,
        False,
        0,
        native_time_payload(realtime_remaining=native["realtime_duration"]),
    )
    if not retention.apply_state_reference(
        handler, invocation, 3049, 1, carrier_context=carrier
    ):
        raise ValueError("Original order form carrier was not applied")
    current = morph_record(fight, actor.id)
    if (
        current is None
        or current["profile_id"] != 3217
        or tuple(current["levels"].items()) != plan.book
    ):
        raise ValueError("Original order form did not install its native command book")
    return True


def restored_book(fight, plan, base_book):
    """Verify common native removal restored the unchanged player book pointer."""
    from .combat_morph_spellbook import active_morph_book, morph_record
    from .combat_spell_level import NativeSpellBook

    if (
        not isinstance(plan, FormPlan)
        or fight.id != plan.encounter_id
        or not isinstance(base_book, NativeSpellBook)
    ):
        raise ValueError("Order restoration requires its original fight and base book")
    if morph_record(fight, plan.owner_id) is not None:
        raise ValueError("Native temporary order form has not been removed")
    current = active_morph_book(fight, plan.owner_id, base_book)
    if current is not base_book:
        raise ValueError("Order exit did not restore the native player book pointer")
    return current
