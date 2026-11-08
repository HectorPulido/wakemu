"""QI population produced by fresh owned placement and explicit QK events."""
from .combat_qi_registry import NativeQIRegistry
from .combat_state import Actor, Fight
from .combat_retained_collections import OwnedMap
from .combat_global_pv_read_view import NativeGlobalPVReadView
from . import combat_carrying as _carrying_module
from . import combat_forced_retirement as _forced_retirement_module
from . import combat_global_pv_collections as _pv_collections_module
from . import combat_global_pv_read_view as _pv_view_module

_SOURCE_PV_VIEW_STATE = NativeGlobalPVReadView._state
_SOURCE_PV_VIEW_GUARDS = NativeGlobalPVReadView.guards
_SOURCE_PV_VIEW_INIT = NativeGlobalPVReadView.__init__
_SOURCE_CARRYING_RELATIONS = _carrying_module.carrying_relations
_SOURCE_CARRY_PAIRS = _carrying_module._pairs
_SOURCE_CARRY_POPULATION = _carrying_module._population
_SOURCE_FORCED_TRANSITION = _forced_retirement_module.forced_retirement_transition
_SOURCE_FORCED_TRANSITIONS = _forced_retirement_module._TRANSITIONS
_SOURCE_GLOBAL_FIGHTER_GUARDS = _pv_collections_module.global_fighter_guards
_NO_CLASS_FIELD = object()
_SOURCE_FIGHT_ACTORS_FIELD = Fight.__dict__.get("actors", _NO_CLASS_FIELD)
_SOURCE_ACTOR_FIELDS = {
    name: Actor.__dict__.get(name, _NO_CLASS_FIELD)
    for name in (
        "id",
        "hp",
        "position",
        "native_obstacle_id",
        "physical_radius",
        "native_carrier_id",
        "native_carried_actor_id",
    )
}


def _current_registry_pv_view_allowed(fight, registry):
    """Prove the loop uses only native, callback-free PV readers."""
    fields = (
        object.__getattribute__(fight, "__dict__") if type(fight) is Fight else None
    )
    if fields is None or Fight.__getattribute__ is not object.__getattribute__:
        return False
    if Fight.__dict__.get("actors", _NO_CLASS_FIELD) is not _SOURCE_FIGHT_ACTORS_FIELD:
        return False
    if any(
        Actor.__dict__.get(name, _NO_CLASS_FIELD) is not value
        for name, value in _SOURCE_ACTOR_FIELDS.items()
    ):
        return False
    actors = fields.get("actors")
    if (
        type(actors) is not OwnedMap
        or type(actors).get is not dict.get
        or OwnedMap.__dict__.get("__getattribute__", object.__getattribute__)
        is not object.__getattribute__
        or "get" in object.__getattribute__(actors, "__dict__")
        or Actor.__getattribute__ is not object.__getattribute__
        or _pv_collections_module._collections
        is not _pv_collections_module._SOURCE_COLLECTIONS
        or _pv_collections_module.NativeTroveLongMap
        is not _pv_collections_module._SOURCE_TROVE_TYPE
        or any(
            _pv_collections_module.NativeTroveLongMap.__dict__.get(name) is not method
            for name, method in _pv_collections_module._SOURCE_TROVE_METHODS.items()
        )
        or _pv_view_module._collections
        is not _pv_collections_module._SOURCE_COLLECTIONS
        or _pv_view_module.NativeTroveLongMap
        is not _pv_collections_module._SOURCE_TROVE_TYPE
        or NativeGlobalPVReadView._state is not _SOURCE_PV_VIEW_STATE
        or NativeGlobalPVReadView.guards is not _SOURCE_PV_VIEW_GUARDS
        or NativeGlobalPVReadView.__init__ is not _SOURCE_PV_VIEW_INIT
        or _pv_collections_module.global_fighter_guards
        is not _SOURCE_GLOBAL_FIGHTER_GUARDS
        or _carrying_module.carrying_relations is not _SOURCE_CARRYING_RELATIONS
        or _carrying_module._pairs is not _SOURCE_CARRY_PAIRS
        or _carrying_module._population is not _SOURCE_CARRY_POPULATION
        or _forced_retirement_module.forced_retirement_transition
        is not _SOURCE_FORCED_TRANSITION
        or _forced_retirement_module._TRANSITIONS is not _SOURCE_FORCED_TRANSITIONS
    ):
        return False
    # Python dict lookup can call an opaque stored key's equality method even
    # when the queried identity is an int. Prove map keys once per operation,
    # before sharing the native Trove validation across actor lookups.
    if any(type(key) is not int for key in dict.keys(actors)):
        return False
    state = fields.get("native_global_pv_collections")
    if type(state) is not dict:
        return False
    if any(type(key) is not str for key in dict.keys(state)):
        return False
    topology = state.get("fighters")
    if (
        type(topology) is not dict
        or any(type(key) is not str for key in dict.keys(topology))
        or type(topology.get("keys")) is not list
        or type(topology.get("states")) is not list
        or type(state.get("fighter_status")) is not dict
        or type(state.get("retired_fighters")) is not list
    ):
        return False
    statuses = state["fighter_status"]
    if any(
        type(key) is not str or type(value) is not str
        for key, value in dict.items(statuses)
    ):
        return False
    pairs = fields.get("native_carry_pairs", {})
    if type(pairs) is not dict or pairs or _forced_retirement_module._TRANSITIONS.get():
        return False
    return type(registry) is NativeQIRegistry and type(registry.slots) is list


def _current_registry_actor_row_native(row):
    return (
        type(row) is dict
        and type(row.get("identity")) is list
        and len(row["identity"]) == 2
        and type(row["identity"][0]) is str
        and type(row["identity"][1]) is int
        and type(row.get("position")) in (list, tuple)
        and len(row["position"]) == 2
        and all(type(value) is int for value in row["position"])
        and type(row.get("radius")) is int
        and type(row.get("indexed")) is bool
    )


def _current_registry_actor_values_native(actor, identity):
    if type(actor) is not Actor:
        return False
    fields = object.__getattribute__(actor, "__dict__")
    position = fields.get("position")
    return (
        type(fields.get("id")) is int
        and fields["id"] == identity
        and type(fields.get("hp")) is int
        and fields["hp"] > 0
        and type(fields.get("native_obstacle_id")) is int
        and type(fields.get("physical_radius")) is int
        and type(position) is tuple
        and len(position) == 3
        and all(type(value) is int for value in position)
        and fields.get("native_carrier_id") is None
        and fields.get("native_carried_actor_id") is None
    )


def prepare_fresh_actor_slots(fight, *, physical_radii):
    """Consume the constructor's fresh registration boundary exactly once.

    initialize_fight_snapshots calls this only after validating the complete
    ordinary PC/NPC creation sources. Actor obstacle bytes are the same bytes
    serialized in placement. Missing serialized terrain stays unknown.
    """
    pending = getattr(fight, "native_qi_fresh_actor_order", None)
    if pending is None:
        raise ValueError("Missing fresh native QI creation boundary")
    if (
        fight.phase != "placement"
        or tuple(fight.actors) != tuple(pending)
        or fight.native_effect_uid_next is not None
        or getattr(fight, "native_qi_slots", None) is not None
        or getattr(fight, "native_effect_areas", {})
    ):
        raise ValueError("Native QI population is not fresh ordinary placement")
    arena = getattr(fight, "native_qi_snapshot", None)
    if arena is None:
        return None
    if set(physical_radii) != set(fight.actors):
        raise ValueError("Missing complete fresh actor physical radii")
    slots = [None] * 127
    for identity in pending:
        actor = fight.actors[identity]
        slot, radius = actor.native_obstacle_id, physical_radii[identity]
        if (
            type(slot) is not int
            or not 0 <= slot <= 126
            or slots[slot] is not None
            or type(radius) is not int
            or not -128 <= radius <= 127
            or actor.hp <= 0
        ):
            raise ValueError("Missing actual fresh actor QK registration facts")
        from .combat_qi_snapshot import NativeQISnapshot

        inside = NativeQISnapshot(arena).aK(*actor.position[:2])
        if not inside:
            # Actual buH.x skips QI.i for OOB actors; their supplied byte is
            # not a reserved QI slot. This owned producer requires placement
            # fully inside the serialized arena rather than inventing a slot.
            raise ValueError("Fresh actor QI placement is outside serialized arena")
        slots[slot] = dict(
            identity=["actor", identity],
            position=list(actor.position[:2]),
            radius=radius,
            indexed=inside,
            movement_blocking=True,
        )
    registry = NativeQIRegistry(arena, slots)
    registry.capture_fresh_cell_topology(
        [fight.actors[identity].native_obstacle_id for identity in pending]
    )
    return registry


def install_fresh_actor_slots(fight, registry):
    """Commit only a population prepared with the complete actor snapshots."""
    if registry is not None:
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_touched_cells = registry.serialized_cells()
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
    fight.native_qi_fresh_actor_order = None


def _actor_lifecycle_error(identity, slot, actor, row, *, boundary):
    """Keep a rejected QK's actual identity and mismatch in bounded diagnostics."""
    actual = (
        None
        if actor is None
        else (
            actor.native_obstacle_id,
            actor.physical_radius,
            tuple(actor.position[:2]),
        )
    )
    expected = (slot, row["radius"], tuple(row["position"]))
    return ValueError(
        "Native QI actor registration requires an actual lifecycle update: "
        f"actor={identity} boundary={boundary} actual={actual} expected={expected}"
    )


def current_registry(fight, *, pending_area_id=None):
    if hasattr(fight, "native_pointer_checkpoint"):
        from .combat_pointer_qi_checkpoint import NativePointerCheckpoint
        from .combat_pointer_qi_registry import PointerRegistryCompatibility

        checkpoint = fight.native_pointer_checkpoint
        if not isinstance(checkpoint, NativePointerCheckpoint):
            raise ValueError("Missing typed canonical native pointer owner")
        if pending_area_id is not None:
            row = getattr(fight, "native_effect_areas", {}).get(pending_area_id)
            if (
                not isinstance(row, dict)
                or row.get("uid") != pending_area_id
                or row.get("native_obstacle_id") != -1
                or pending_area_id in checkpoint._qi.area_objects
            ):
                raise ValueError("Missing actual pending canonical Qq constructor")
        return PointerRegistryCompatibility(checkpoint.validate(fight))
    """Reject stale or unproved populations instead of rebuilding a roster."""
    arena = getattr(fight, "native_qi_snapshot", None)
    slots = getattr(fight, "native_qi_slots", None)
    touched = getattr(fight, "native_qi_touched_cells", None)
    if (
        not isinstance(arena, dict)
        or not isinstance(slots, list)
        or not isinstance(touched, list)
    ):
        raise ValueError("Missing complete owned native QI population")
    registry = NativeQIRegistry(
        arena,
        slots,
        touched_cells=touched,
        byte_topology=getattr(fight, "native_qi_byte_topology", None),
    )
    seen = set()
    from .combat_pve_departure import retired_pve_actor_ids
    from .combat_summon_retirement import retired_summon_ids

    from .combat_ordinary_qi_retirement import retired_ordinary_qi_ids
    from .combat_forced_retirement import (
        retired_forced_fighter_ids,
        forced_retirement_transition,
    )

    retired = (
        retired_pve_actor_ids(fight)
        | retired_ordinary_qi_ids(fight)
        | retired_forced_fighter_ids(fight)
    )
    retired_summons = retired_summon_ids(fight, registry=registry)
    seen_areas = set()
    areas = getattr(fight, "native_effect_areas", {})
    share_pv_view = _current_registry_pv_view_allowed(fight, registry)
    pv_view = None
    for slot, row in enumerate(registry.slots):
        if row is None:
            continue
        if not _current_registry_actor_row_native(row):
            pv_view = None
            share_pv_view = False
        if row["identity"][0] == "effect_area":
            # Area verification can enter native constructors. Do not carry a
            # PV validation across that callback boundary.
            pv_view = None
            share_pv_view = False
            identity = row["identity"][1]
            area = areas.get(identity)
            contract = (
                area.get("native_area_contract") if isinstance(area, dict) else None
            )
            if contract == "faW":
                obstacle = (
                    area.get("native_faw_constructor", {}).get("obstacle") is True
                )
            elif contract == "fbd":
                from .combat_wall_area import verified_wall_constructor
                from .combat_effect_area import native_effect_areas

                definition = native_effect_areas().get(str(area.get("reference")))
                try:
                    constructor = verified_wall_constructor(area, definition)
                except ValueError as exc:
                    raise ValueError(
                        "Native QI wall registration requires an actual lifecycle update"
                    ) from exc
                obstacle = constructor["obstacle"] is True
            else:
                obstacle = False
            if (
                not isinstance(area, dict)
                or area.get("native_obstacle_id") != slot
                or list(area.get("cell", ())[:2]) != list(row["position"])
                or not obstacle
                or row["radius"] != 0
            ):
                raise ValueError(
                    "Native QI area registration requires an actual lifecycle update"
                )
            seen_areas.add(identity)
            continue
        identity = row["identity"][1]
        if identity in retired or identity in retired_summons:
            raise ValueError("Retired native QK remains registered")
        actor = fight.actors.get(identity)
        actor_values_native = (
            share_pv_view
            and _current_registry_actor_row_native(row)
            and type(identity) is int
            and _current_registry_actor_values_native(actor, identity)
        )
        if not actor_values_native:
            pv_view = None
            share_pv_view = False
        life = None
        transitioning = forced_retirement_transition(fight, identity, slot)
        if actor is not None and hasattr(fight, "native_global_pv_collections"):
            from .combat_global_pv_collections import global_fighter_guards

            native_row = _current_registry_actor_row_native(row)
            if share_pv_view and native_row and actor_values_native:
                if pv_view is None:
                    pv_view = NativeGlobalPVReadView(fight)
                life = pv_view.guards(fight, identity)
            else:
                # HP-zero verification and opaque rows may read event or
                # relation providers; their later iterations must rebuild the
                # PV proof through the original callback-aware route.
                pv_view = None
                share_pv_view = False
                life = global_fighter_guards(fight, identity)
            if life["baK"] and not transitioning:
                # Native OUT_OF_PLAY H performs QI.g and M(-1), including
                # actors whose HP is positive. A remaining slot is stale.
                raise _actor_lifecycle_error(
                    identity, slot, actor, row, boundary="out_of_play"
                )
        if actor is not None and actor.hp <= 0 and not transitioning:
            from .combat_ordinary_death import registered_ordinary_death

            # OFF_PLAY changes fdy, not QI indexing or the actor's QK byte.
            # fcb.aC/B/baE has no QI.g; OUT_OF_PLAY aD/H does. Preserve
            # existing exact slots only for the owned registered transition.
            if life is None:
                raise _actor_lifecycle_error(
                    identity, slot, actor, row, boundary="missing_life"
                )
            in_play_hp_operand = False
            if life["baF"] is True and life["baG"] is False and life["baK"] is False:
                from .combat_hp_raw import hp_raw_present, hp_raw_current

                # A native PA.on setter can write effective HP0 without changing
                # fdy or QI membership. Certify the complete current operand,
                # rather than infer a death/removal from the HP scalar.
                if hp_raw_present(actor):
                    hp_raw_current(actor)
                    in_play_hp_operand = True
            protected_kill = False
            if (
                not in_play_hp_operand
                and life["baF"] is True
                and life["baG"] is False
                and life["baK"] is False
            ):
                from .combat_protected_kill import registered_protected_kill

                protected_kill = registered_protected_kill(fight, actor) is True
            ordinary_death = (
                life["baG"] is True
                and life["baK"] is False
                and registered_ordinary_death(fight, actor) is True
            )
            if not (in_play_hp_operand or protected_kill or ordinary_death):
                raise _actor_lifecycle_error(
                    identity, slot, actor, row, boundary="unproved_hp_zero"
                )
        if (
            actor is None
            or actor.native_obstacle_id != slot
            or actor.physical_radius != row["radius"]
            or list(actor.position[:2]) != list(row["position"])
        ):
            raise _actor_lifecycle_error(
                identity, slot, actor, row, boundary="physical_registration"
            )
        from .combat_carrying import carrying_relations

        relation = carrying_relations(fight, actor)
        if relation["is_carried"] and row["indexed"]:
            raise ValueError("Carried QK has stale native indexing")
        seen.add(identity)
    if seen != set(fight.actors) - retired - set(retired_summons):
        raise ValueError(
            "Owned native QI actor population changed without registration"
        )
    expected_areas = set()
    for identity, area in areas.items():
        if identity == pending_area_id:
            continue
        contract = area.get("native_area_contract")
        if (
            contract == "faW"
            and area.get("native_faw_constructor", {}).get("obstacle") is True
        ):
            expected_areas.add(identity)
        elif contract == "fbd":
            from .combat_wall_area import verified_wall_constructor
            from .combat_effect_area import native_effect_areas

            definition = native_effect_areas().get(str(area.get("reference")))
            constructor = verified_wall_constructor(area, definition)
            if constructor["obstacle"]:
                expected_areas.add(identity)
    if seen_areas != expected_areas:
        raise ValueError("Owned native QI area population changed without registration")
    return registry


def move_registered_actor(fight, actor, destination):
    """Publish an actual actor coordinate update together with QI relocation."""
    from .combat_position_mutation import move_actor_position

    move_actor_position(fight, actor, destination)


def register_effect_area_obstacle(fight, row, constructor):
    """Preflight with row=None; actual QI.f receives the created Qq row."""
    registry = current_registry(
        fight, pending_area_id=row.get("uid") if isinstance(row, dict) else None
    )
    if not any(slot is None for slot in registry.slots):
        raise ValueError("Native QI obstacle byte capacity exhausted")
    if row is None:
        if (
            not isinstance(constructor, dict)
            or constructor.get("obstacle") is not True
            or type(constructor.get("movement_blocking")) is not bool
        ):
            raise ValueError("Missing native QK obstacle constructor authority")
        return None
    if not isinstance(row, dict):
        raise ValueError("Missing created native Qq obstacle")
    identity = row.get("uid")
    position = row.get("cell")
    if type(identity) is not int or not isinstance(position, (list, tuple)):
        raise ValueError("Missing created native Qq identity/position")
    if row.get("native_area_contract") == "fbd":
        from .combat_wall_area import wall_constructor, wall_hp_state
        from .combat_effect_area import native_effect_areas

        definition = native_effect_areas().get(str(row.get("reference")))
        # QI.f is the producer that assigns native_obstacle_id, so before the
        # call this pending Qq row must still carry constructor-state -1. Check
        # its immutable fbd/Qf/HP facts here and perform full slot validation
        # after registry.register has committed the byte.
        verified = wall_constructor(definition, row.get("level"))
        if (
            row.get("native_area_contract") != "fbd"
            or row.get("native_type_id") != 7
            or row.get("native_running_effect_manager") is not True
            or row.get("native_wall_constructor") != verified
        ):
            raise ValueError("Native QK wall constructor checkpoint mismatch")
        wall_hp_state(row, verified)
        if constructor != verified:
            raise ValueError("Native QK wall constructor does not match its source")
    elif row.get("native_area_contract") != "faW":
        raise ValueError("Unsupported native QK area obstacle contract")
    if hasattr(fight, "native_pointer_checkpoint"):
        from .combat_carrying import _publish_registry

        slot = registry.register_constructor_area(row, constructor)
        if slot < 0:
            raise ValueError("Native QI obstacle byte capacity exhausted")
        _publish_registry(fight, registry)
        return slot
    descriptor = dict(
        identity=["effect_area", identity],
        position=list(position[:2]),
        radius=0,
        indexed=False,
        movement_blocking=constructor["movement_blocking"],
    )
    slot = registry.register(descriptor)
    fight.native_qi_slots = registry.serialized_slots()
    fight.native_qi_touched_cells = registry.serialized_cells()
    fight.native_qi_byte_topology = registry.serialized_byte_topology()
    return slot
