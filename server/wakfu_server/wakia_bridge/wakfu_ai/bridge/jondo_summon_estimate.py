"""Small advisory cache of spell projections already produced on a summon turn."""
from collections import OrderedDict
from threading import Lock
from time import monotonic

from ..native.native_control import effective_affiliation, effective_server_controlled

_LOCK = Lock()
_BOOKS = OrderedDict()
_MAX_BOOKS = 128


def _direct_npc_controller(fight, actor, registration, source):
    """Bounded sufficient subset of NPC control for advisory estimates only."""
    from wakfu_server.combat_controller_registry import current_native_controller

    authority = registration.get("authority")
    if (
        not isinstance(authority, dict)
        or getattr(actor, "controlled", None) is not False
        or authority.get("is_summon") is not True
        or authority.get("native_actor_type") != 1
        or registration.get("actor_id") != actor.id
        or registration.get("caster_id") != source.get("caster_id")
        or authority.get("breed_id") != source.get("ref")
        or authority.get("native_real_level") != source.get("level")
    ):
        return False
    controller_id = current_native_controller(fight, actor.id)
    if (
        type(controller_id) is not int
        or controller_id == actor.id
        or controller_id != source.get("controller_id")
        or controller_id != registration.get("controller_id")
    ):
        return False
    controller = fight.actors.get(controller_id)
    if (
        controller is None
        or controller.hp <= 0
        or getattr(controller, "controlled", None) is not False
        or getattr(controller, "native_controlled_by_ai", None) is not True
    ):
        return False
    slot = getattr(actor, "native_obstacle_id", None)
    if type(slot) is not int or not 0 <= slot <= 126:
        return False
    if not hasattr(fight, "native_pointer_checkpoint"):
        # Legacy QI keeps detached scalar slot rows across Fight copies. This
        # checks only the current actor's own indexed slot, not the complete
        # QI topology or a cast/LOS certificate.
        slots = getattr(fight, "native_qi_slots", None)
        position = getattr(actor, "position", None)
        radius = getattr(actor, "physical_radius", None)
        retirements = getattr(fight, "native_summon_retirements", {})
        if (
            type(slots) is not list
            or len(slots) != 127
            or type(position) is not tuple
            or len(position) != 3
            or any(type(value) is not int for value in position)
            or type(radius) is not int
            or radius < 0
            or ("retired" in registration and registration["retired"] is not False)
            or not isinstance(retirements, dict)
            or actor.id in retirements
        ):
            return False
        row = slots[slot]
        if (
            type(row) is not dict
            or len(row) != 5
            or set(row)
            != {"identity", "position", "radius", "indexed", "movement_blocking"}
        ):
            return False
        identity, cell = row["identity"], row["position"]
        return (
            type(identity) is list
            and len(identity) == 2
            and type(identity[0]) is str
            and identity[0] == "actor"
            and type(identity[1]) is int
            and identity[1] == actor.id
            and type(cell) is list
            and len(cell) == 2
            and all(type(value) is int for value in cell)
            and cell == list(position[:2])
            and type(row["radius"]) is int
            and row["radius"] == radius
            and row["indexed"] is True
            and type(row["movement_blocking"]) is bool
        )

    from wakfu_server.combat_pointer_qi_actor import ActualActorQI, ActorQK
    from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint

    checkpoint = fight.native_pointer_checkpoint
    if type(checkpoint) is not NativePointerCheckpoint:
        return False
    qi = getattr(checkpoint, "_qi", None)
    if (
        type(qi) is not ActualActorQI
        or qi.fight is not fight
        or type(qi.slots) is not list
        or slot >= len(qi.slots)
        or type(qi.objects) is not dict
    ):
        return False
    obj = qi.slots[slot]
    return (
        type(obj) is ActorQK and qi.objects.get(actor.id) is obj and obj.actor is actor
    )


def _signature(oracle, fight, actor):
    """Read only installed authority; reject books with unhandled overlays."""
    identity = actor.id
    if fight.actors.get(identity) is not actor or actor.hp <= 0:
        return None
    registration = getattr(fight, "native_summon_registrations", {}).get(identity)
    source = getattr(actor, "native_summon_source", None)
    book = getattr(actor, "native_summon_action_book", None)
    if (
        type(registration) is not dict
        or type(source) is not dict
        or type(book) is not dict
        or source.get("native_relation_source")
        != "big.new_bje.fdt_initial_registration"
        or source.get("native_symbiot_source") != "eZl.new_eHD.pRO_false"
        or getattr(actor, "native_summoned_from_symbiot", None) is not False
        or getattr(actor, "native_character_copy_book_source", None) is not None
        or getattr(fight, "native_morph_spellbooks", {}).get(identity) is not None
        or getattr(fight, "native_spell_grants", {}).get(identity)
        or getattr(fight, "native_removed_spell_uids", {}).get(identity)
        or getattr(fight, "native_controller_action_books", {}).get(identity)
    ):
        return None
    if (
        len(book) != 4
        or set(book) != {"producer", "profile", "descriptor_level", "actions"}
        or book.get("producer") != "big.new_bje.bz.aQc.bPD"
        or book.get("profile") != source.get("ref")
        or book.get("descriptor_level") != source.get("level")
        or not isinstance(book.get("actions"), list)
        or len(book["actions"]) > 80
    ):
        return None
    actions = []
    for row in book["actions"]:
        if (
            type(row) is not dict
            or len(row) != 3
            or set(row) != {"uid", "reference", "level"}
        ):
            return None
        uid, reference, level = row.get("uid"), row.get("reference"), row.get("level")
        if (
            type(uid) is not int
            or uid != reference
            or type(level) is not int
            or not 0 < uid < 2**31
            or not 0 <= level <= 32767
        ):
            return None
        actions.append((reference, level))
    if len({ref for ref, _ in actions}) != len(actions):
        return None
    try:
        if hasattr(fight, "native_controller_registry"):
            flag = getattr(actor, "native_controlled_by_ai", None)
            if flag is True:
                if not effective_server_controlled(fight, actor):
                    return None
            elif flag is False:
                if not _direct_npc_controller(fight, actor, registration, source):
                    return None
            else:
                return None
        elif not effective_server_controlled(fight, actor):
            return None
        oracle.descriptor(fight, actor)
        team = effective_affiliation(fight, actor)
        if hasattr(fight, "native_controller_registry"):
            from wakfu_server.combat_controller_registry import (
                current_native_controller,
            )

            controller = current_native_controller(fight, identity)
        else:
            controller = getattr(actor, "native_controller_id", None)
        if controller != source.get("controller_id"):
            return None
        modifiers = getattr(actor, "spell_ap_cost_modifiers", None)
        ranges = getattr(actor, "spell_range_modifiers", None)
        stats = getattr(actor, "effect_stats", None)
        entries = getattr(getattr(actor, "state_ledger", None), "entries", None)
        if (
            not isinstance(modifiers, dict)
            or len(modifiers) > 128
            or not isinstance(ranges, dict)
            or len(ranges) > 128
            or not isinstance(stats, dict)
            or len(stats) > 256
            or entries is None
            or len(entries) > 128
        ):
            return None
        scalar_maps = []
        for values in (modifiers, ranges, stats):
            if any(type(k) is not int or type(v) is not int for k, v in values.items()):
                return None
            scalar_maps.append(tuple(sorted(values.items())))
        states = tuple(
            (row.reference, row.level, row.duration, row.caster_id) for row in entries
        )
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        ReferenceError,
        IndexError,
    ):
        return None
    position = getattr(actor, "position", None)
    if (
        not isinstance(position, tuple)
        or len(position) != 3
        or any(type(value) is not int for value in position)
        or type(getattr(actor, "direction", None)) is not int
    ):
        return None
    return (
        identity,
        source.get("ref"),
        source.get("level"),
        source.get("caster_id"),
        source.get("controller_id"),
        registration.get("caster_id"),
        registration.get("controller_id"),
        actor.effective_level,
        team,
        *scalar_maps,
        states,
        position,
        actor.direction,
        actor.hp,
        tuple(actions),
    )


def remember(oracle, fight, actor, source, owned, spells, stable_casting):
    """Keep projections only after native owned-book validation has succeeded."""
    deadline = monotonic() + 0.001
    signature = _signature(oracle, fight, actor)
    if signature is None or dict(signature[-1]) != owned:
        return
    if monotonic() >= deadline:
        return
    rows = []
    for spell in spells[:80]:
        if len(rows) >= 16:
            break
        # An interrupted refresh is not evidence that the previous book was
        # revoked. Keep it for readers that can still verify its signature.
        if monotonic() >= deadline:
            return
        reference, level = spell.get("id"), spell.get("grade")
        cost, minimum, maximum = (
            spell.get("cost"),
            spell.get("minRange"),
            spell.get("maxRange"),
        )
        costs = spell.get("nativeCosts")
        if (
            (reference, level) not in signature[-1]
            or (reference, level) not in stable_casting
            or spell.get("unknownProjection")
            or type(cost) is not int
            or cost < 0
            or type(minimum) is not int
            or type(maximum) is not int
            or not 0 <= minimum <= maximum <= 128
            or not isinstance(costs, dict)
            or costs.get("mp") != 0
            or costs.get("wp") != 0
        ):
            continue
        damage_rows = [
            row for row in spell.get("rows", ()) if row.get("kind") == "damage"
        ]
        if len(damage_rows) != 1:
            continue
        row = damage_rows[0]
        base = row.get("nativeBase")
        mask, flags, localization = (
            row.get("nativeCoefficientMask"),
            row.get("nativeDamageFlags"),
            row.get("nativeLocalization"),
        )
        if (
            row.get("target") != "enemy"
            or row.get("conditional") is not False
            or row.get("probability") != 100
            or type(row.get("amount")) is not int
            or not 0 < row["amount"] <= 1000000
            or type(mask) is not int
            or mask not in range(4)
            or not isinstance(flags, list)
            or len(flags) > 32
            or any(type(flag) is not int for flag in flags)
            or type(localization) is not bool
            or not isinstance(base, dict)
            or base.get("kind") != 0
            or base.get("sourceBindingKnown") is not True
        ):
            continue
        rows.append(
            (
                reference,
                level,
                cost,
                minimum,
                maximum,
                row["amount"],
                row.get("element", "physical"),
                mask,
                tuple(flags),
                localization,
            )
        )
    if monotonic() >= deadline:
        return
    if not _LOCK.acquire(blocking=False):
        return
    try:
        key = (
            source["fightInstanceId"],
            source["fightId"],
            source["catalogRevision"],
            actor.id,
        )
        if not rows:
            _BOOKS.pop(key, None)
            return
        _BOOKS[key] = (signature, tuple(rows))
        _BOOKS.move_to_end(key)
        while len(_BOOKS) > _MAX_BOOKS:
            _BOOKS.popitem(last=False)
    finally:
        _LOCK.release()


def estimates(oracle, fight, actor, visible, source):
    """Return only still-owned estimates for currently visible allied summons."""
    deadline = monotonic() + 0.001
    if not _LOCK.acquire(blocking=False):
        return []
    try:
        candidates = []
        for summon in visible[:128]:
            if len(candidates) >= 4:
                break
            key = (
                source["fightInstanceId"],
                source["fightId"],
                source["catalogRevision"],
                summon.id,
            )
            cached = _BOOKS.get(key)
            if cached is not None:
                candidates.append((summon, key, cached))
    finally:
        _LOCK.release()
    result = []
    for summon, key, cached in candidates:
        if monotonic() >= deadline:
            break
        signature = _signature(oracle, fight, summon)
        if monotonic() >= deadline:
            break
        if (
            signature != cached[0]
            or signature[3] != actor.id
            or signature[8] != effective_affiliation(fight, actor)
        ):
            continue
        if not _LOCK.acquire(blocking=False):
            break
        try:
            current = _BOOKS.get(key) is cached
        finally:
            _LOCK.release()
        if not current:
            continue
        result.append(
            dict(
                actorId=summon.id,
                spells=[
                    dict(
                        id=ref,
                        grade=level,
                        cost=cost,
                        minRange=minimum,
                        maxRange=maximum,
                        damage=damage,
                        element=element,
                        nativeCoefficientMask=mask,
                        nativeDamageFlags=list(flags),
                        nativeLocalization=localization,
                    )
                    for ref, level, cost, minimum, maximum, damage, element, mask, flags, localization in cached[
                        1
                    ]
                ],
            )
        )
    return result
