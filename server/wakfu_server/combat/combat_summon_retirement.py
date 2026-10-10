"""Settled KO-zero retirement for source-attested class summons.

Native fcb.aD/fcb.H separates OUT_OF_PLAY from OFF_PLAY and removes the QI
entry while retaining the fighter object and global fighter identity. The
server policy runs only after the outer effect chain has settled and only for
fully registered summons with exact HP, status, and KO_TIME authority.
"""
from copy import deepcopy

from .combat_captured_roster_lifecycle import release_captured_slot_on_retirement
from .combat_global_pv_collections import (
    global_fighter_guards,
    global_fighter_registered,
    set_global_fighter_status,
)
from .combat_qi_fight import current_registry
from .combat_qi_registry import NativeQIRegistry


SOURCE = "wakemu.summon_retirement.ko_zero_after_settlement.v1"
PROTECTED_SOURCE = "wakemu.summon_retirement.protected_332_boundary.v1"
RELATION_SOURCE = "big.new_bje.fdt_initial_registration"
ORDINARY_SYMBIOT_SOURCE = "eZl.new_eHD.pRO_false"
CAPTURED_SYMBIOT_SOURCE = "eZr324.after_common_factory_and_fan.lE_true"
COPIED_SYMBIOT_SOURCE = "eZw1002.new_eHI.pRO_false"


def _registration(fight, actor_id):
    row = getattr(fight, "native_summon_registrations", {}).get(actor_id)
    actor = fight.actors.get(actor_id)
    source = getattr(actor, "native_summon_source", None) if actor is not None else None
    authority = row.get("authority") if isinstance(row, dict) else None
    controller_id = row.get("controller_id") if isinstance(row, dict) else None
    controller = fight.actors.get(controller_id)
    if (
        actor is None
        or not isinstance(source, dict)
        or not isinstance(authority, dict)
        or row.get("actor_id") != actor_id
        or authority.get("is_summon") is not True
        or authority.get("is_player") is not False
        or source.get("native_relation_source") != RELATION_SOURCE
        or type(source.get("ref")) is not int
        or type(source.get("level")) is not int
        or source.get("ref") != authority.get("breed_id")
        or source.get("level") != authority.get("native_real_level")
        or source.get("caster_id") != row.get("caster_id")
        or source.get("controller_id") != controller_id
        or authority.get("native_controller_id") != controller_id
        or getattr(actor, "native_controller_id", None) != controller_id
        or getattr(actor, "native_master_id", None) != controller_id
        or controller is None
        or actor.controlled != controller.controlled
        or actor.owner_id != controller.owner_id
    ):
        raise ValueError("Missing complete native summon retirement registration")
    symbiot = source.get("native_symbiot_source")
    captured = symbiot == CAPTURED_SYMBIOT_SOURCE
    copied = symbiot == COPIED_SYMBIOT_SOURCE
    if (
        symbiot
        not in (ORDINARY_SYMBIOT_SOURCE, CAPTURED_SYMBIOT_SOURCE, COPIED_SYMBIOT_SOURCE)
        or authority.get("native_summoned_from_symbiot") is not captured
    ):
        raise ValueError("Unknown native summon retirement origin")
    if captured:
        owner_id, slot = source.get("native_captured_owner_id"), source.get(
            "native_captured_slot"
        )
        if type(owner_id) is not int or type(slot) is not int or not 0 <= slot < 10:
            raise ValueError("Missing exact captured summon retirement slot")
    elif "native_captured_slot" in source or "native_captured_owner_id" in source:
        raise ValueError("Ordinary summon carries an unproved captured slot")
    if copied:
        copy_source = getattr(actor, "native_copy_pa_source", None)
        effect_reference = source.get("native_copy_effect_reference")
        runner_uid = source.get("native_copy_runner_uid")
        source_actor_id = source.get("native_copy_source_actor_id")
        if (
            source.get("native_character_copy_source") != "eZw1002.faB.eHI.bPl"
            or source["ref"]
            != (copy_source.get("profile") if isinstance(copy_source, dict) else None)
            or source_actor_id != source.get("caster_id")
            or type(effect_reference) is not int
            or effect_reference <= 0
            or type(runner_uid) is not int
            or runner_uid <= 0
            or not isinstance(copy_source, dict)
            or copy_source.get("producer") != "eHI.pRU.ffh.a"
            or copy_source.get("actor_id") != actor.id
            or copy_source.get("source_actor_id") != source_actor_id
            or copy_source.get("profile") != source["ref"]
            or copy_source.get("effect_reference") != effect_reference
        ):
            raise ValueError("Missing complete copied-summon retirement provenance")
    return actor, row, source, captured, copied


def _ko_current(actor):
    names = (
        "effect_stats",
        "effect_minima",
        "effect_maxima",
        "effect_base_minima",
        "effect_base_maxima",
        "effect_percentages",
    )
    values = [getattr(actor, name, None) for name in names]
    if any(
        not isinstance(item, dict) or type(item.get(14)) is not int for item in values
    ):
        raise ValueError(
            "Missing complete native KO_TIME snapshot for summon retirement"
        )
    if not isinstance(getattr(actor, "effect_frozen", None), frozenset):
        raise ValueError("Missing native KO_TIME mutability for summon retirement")
    current, minimum, maximum, raw_minimum, raw_maximum, percentage = (
        item[14] for item in values
    )
    if (
        minimum > current
        or current > maximum
        or raw_minimum > raw_maximum
        or type(percentage) is not int
    ):
        raise ValueError("Inconsistent native KO_TIME snapshot for summon retirement")
    return current


def retired_summon_ids(fight, *, registry=None):
    """Validate persistent retirement records and return their actor IDs."""
    records = getattr(fight, "native_summon_retirements", {})
    if not isinstance(records, dict):
        raise ValueError("Malformed native summon retirement checkpoint")
    if not records:
        return frozenset()
    if registry is None:
        arena = getattr(fight, "native_qi_snapshot", None)
        slots = getattr(fight, "native_qi_slots", None)
        touched = getattr(fight, "native_qi_touched_cells", None)
        if (
            not isinstance(arena, dict)
            or not isinstance(slots, list)
            or not isinstance(touched, list)
        ):
            raise ValueError("Missing QI checkpoint for retired summon")
        registry = NativeQIRegistry(
            arena,
            slots,
            touched_cells=touched,
            byte_topology=getattr(fight, "native_qi_byte_topology", None),
        )
    result = set()
    for actor_id, record in records.items():
        if (
            type(actor_id) is not int
            or not isinstance(record, dict)
            or record.get("source") not in (SOURCE, PROTECTED_SOURCE)
            or record.get("actor_id") != actor_id
            or type(record.get("qi_slot")) is not int
            or not 0 <= record["qi_slot"] <= 126
            or type(record.get("sequence")) is not int
        ):
            raise ValueError("Invalid native summon retirement record")
        actor, _, source, captured, copied = _registration(fight, actor_id)
        event = next(
            (
                item
                for item in getattr(fight, "events", ())
                if item.get("sequence") == record["sequence"]
            ),
            None,
        )
        if (
            actor.hp != 0
            or _ko_current(actor) != 0
            or actor.native_obstacle_id != -1
            or list(actor.position[:2]) != record.get("position")
            or record.get("breed_id") != source["ref"]
            or record.get("captured") is not captured
            or not isinstance(event, dict)
            or event.get("kind") != "summon_out_of_play"
            or event.get("actor_id") != actor_id
            or event.get("source") != record["source"]
            or event.get("qi_slot") != record["qi_slot"]
            or event.get("breed_id") != source["ref"]
            or event.get("captured") is not captured
            or event.get("copied") is not copied
            or record.get("copied") is not copied
        ):
            raise ValueError("Native summon retirement facts changed")
        if global_fighter_guards(fight, actor_id) != dict(
            baF=False, baG=False, baK=True
        ):
            raise ValueError("Retired summon lacks OUT_OF_PLAY status")
        if not global_fighter_registered(fight, actor_id):
            raise ValueError("Retired summon lost its native fighter identity")
        if any(
            row is not None and row["identity"] == ["actor", actor_id]
            for row in registry.slots
        ):
            raise ValueError("Retired summon still occupies a native QI slot")
        if captured:
            owner_id = source["native_captured_owner_id"]
            slot = source["native_captured_slot"]
            overlays = getattr(fight, "native_captured_rosters", {})
            updates = getattr(fight, "native_captured_roster_updates", {})
            record_data = overlays.get(str(owner_id), updates.get(str(owner_id)))
            if not isinstance(record_data, dict):
                raise ValueError("Retired captured summon lost its roster checkpoint")
            from wakfu_server.characters.captured_roster import OwnedCapturedRoster

            roster = OwnedCapturedRoster.from_record(
                record_data, expected_owner_id=owner_id
            )
            descriptor = roster.slots[slot]
            if (
                descriptor is None
                or descriptor.profile_id != source["ref"]
                or roster.available[slot] is not True
            ):
                raise ValueError("Retired captured summon slot is not released")
        result.add(actor_id)
    return frozenset(result)


def _death_is_registered(fight, actor):
    from .combat_ordinary_death import registered_ordinary_death

    return registered_ordinary_death(fight, actor) is True


def _retire_one(preview, actor_id, *, protected=False):
    actor, _, source, captured, copied = _registration(preview, actor_id)
    if actor.hp != 0:
        raise ValueError("Only a zero-HP summon can leave play")
    life = global_fighter_guards(preview, actor_id)
    if protected:
        from .combat_protected_kill import registered_protected_kill

        if life != dict(
            baF=True, baG=False, baK=False
        ) or not registered_protected_kill(preview, actor):
            raise ValueError(
                "Protected summon retirement requires the exact eZG receipt"
            )
    else:
        if life != dict(baF=False, baG=True, baK=False):
            raise ValueError("Summon retirement requires an actual OFF_PLAY death")
        if not _death_is_registered(preview, actor):
            raise ValueError("Summon retirement has no registered death transition")
    retirement_source = PROTECTED_SOURCE if protected else SOURCE
    ko = _ko_current(actor)
    if ko != 0:
        return False
    if not global_fighter_registered(preview, actor_id):
        raise ValueError("Summon retirement requires current fdt membership")
    slot = actor.native_obstacle_id
    if type(slot) is not int or not 0 <= slot <= 126:
        raise ValueError("Missing actual summon QI slot for retirement")
    registry = current_registry(preview)
    descriptor = registry.slots[slot]
    if descriptor is None or descriptor["identity"] != ["actor", actor_id]:
        raise ValueError("Summon retirement QI identity changed")

    # Source fcb.aD sets OUT_OF_PLAY, then H removes QI and releases a captured
    # descriptor. Probe the component step on an isolated copy so any missing
    # roster authority fails before the transaction publishes any mutation.
    if captured:
        probe = deepcopy(preview)
        release_captured_slot_on_retirement(
            probe,
            probe.actors[actor_id],
            source["native_captured_owner_id"],
            source["native_captured_slot"],
        )
        preview.native_captured_rosters = probe.native_captured_rosters
        preview.native_captured_roster_updates = probe.native_captured_roster_updates

    set_global_fighter_status(preview, actor_id, "OUT_OF_PLAY")
    registry.remove(slot, ("actor", actor_id))
    # Native QI.g removes the row and calls the actor's QK.M(-1); keep the
    # prior byte only in the retirement record for audit/history.
    actor.native_obstacle_id = -1
    preview.native_qi_slots = registry.serialized_slots()
    preview.native_qi_touched_cells = registry.serialized_cells()
    preview.native_qi_byte_topology = registry.serialized_byte_topology()
    event = preview._event(
        "summon_out_of_play",
        actor_id=actor_id,
        source=retirement_source,
        qi_slot=slot,
        breed_id=source["ref"],
        captured=captured,
        copied=copied,
    )
    records = getattr(preview, "native_summon_retirements", {})
    if not isinstance(records, dict) or actor_id in records:
        raise ValueError("Duplicate or malformed summon retirement record")
    preview.native_summon_retirements = {
        **records,
        actor_id: dict(
            source=retirement_source,
            actor_id=actor_id,
            qi_slot=slot,
            position=list(actor.position[:2]),
            breed_id=source["ref"],
            captured=captured,
            copied=copied,
            sequence=event["sequence"],
        ),
    }
    return True


def settle_summon_retirements(fight):
    """Apply the server OUT_OF_PLAY policy after the outer effect chain settles."""
    registrations = getattr(fight, "native_summon_registrations", {})
    if not isinstance(registrations, dict):
        raise ValueError("Malformed native summon registration checkpoint")
    if not registrations:
        return ()
    existing = retired_summon_ids(fight)
    candidates = []
    for actor_id in registrations:
        if actor_id in existing:
            continue
        actor = fight.actors.get(actor_id)
        if actor is None:
            raise ValueError("Registered summon actor is missing at death settlement")
        if actor.hp > 0:
            continue
        # PA.on(0), including eYO, does not itself register a death. Elect
        # retirement from the actual fdy transition, never from HP alone.
        life = global_fighter_guards(fight, actor_id)
        if life == dict(baF=True, baG=False, baK=False):
            continue
        # Establish complete source and KO facts before treating any missing
        # information as a policy decision.
        _registration(fight, actor_id)
        if _ko_current(actor) != 0:
            continue
        candidates.append(actor_id)
    if not candidates:
        return ()
    if getattr(fight, "_resolution_depth", 0) != 0:
        raise ValueError("Summon retirement cannot run inside a nested effect chain")

    # Preflight every candidate and captured component on a private snapshot;
    # publish only the lifecycle fields after all candidates validate.
    preview = deepcopy(fight)
    retired = []
    for actor_id in candidates:
        if _retire_one(preview, actor_id):
            retired.append(actor_id)
    if not retired:
        return ()
    fight.native_qi_slots = preview.native_qi_slots
    fight.native_qi_touched_cells = preview.native_qi_touched_cells
    fight.native_qi_byte_topology = preview.native_qi_byte_topology
    fight.native_global_pv_collections = preview.native_global_pv_collections
    if hasattr(preview, "native_captured_rosters"):
        fight.native_captured_rosters = preview.native_captured_rosters
    if hasattr(preview, "native_captured_roster_updates"):
        fight.native_captured_roster_updates = preview.native_captured_roster_updates
    fight.native_summon_retirements = preview.native_summon_retirements
    for actor_id in retired:
        # Publish the exact QK.M(-1) identity update alongside the QI row
        # removal; actor objects are retained rather than replaced by preview.
        fight.actors[actor_id].native_obstacle_id = -1
    fight.events = preview.events
    fight.sequence = preview.sequence
    return tuple(retired)


def retire_protected_summon(fight, actor):
    """Server replacement policy after an attested eZG runner has completed.

    The original server publisher is unavailable. Native eZG proves HP minimum
    and KO clock zero, not fdy removal. This explicit policy closes registered
    summons before sibling free-cell criteria; ordinary fighters stay unchanged.
    """
    if actor.id not in getattr(fight, "native_summon_registrations", {}):
        return False
    if actor.hp != 0 or _ko_current(actor) != 0:
        return False
    return _retire_one(fight, actor.id, protected=True)
