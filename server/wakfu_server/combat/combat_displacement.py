"""Native eXK/eXJ/eXp displacement, eZC/eZD teleport and eXk swap.

Ordinary radius0 actors use native faz.B first-surface transitions when their
map/physical-height policy is exported. Legacy flat fixtures remain explicit.
Collision reactions use the shared synthetic resource/event executor when
actual QI provenance is complete. Native swaps retain registered footprints
and carrier partners. Large forced paths use original faz footprint checks
over authoritative physical columns rather than radius-zero terrain shortcuts.
"""
import math
import struct
from .combat_parameters import parameter_value, _float32
from .combat_effects import _integer, _varint
from .combat_native_timing_context import native_definition_timing

FAMILIES = {
    300: "push",
    301: "pull",
    302: "teleport_caster",
    340: "teleport_target",
    331: "move_away_cell",
    305: "approach_cell",
    422: "swap",
}


def _blob(field, body):
    return _varint(field << 3 | 2) + _varint(len(body)) + body


def position_payload(cell):
    if (
        len(cell) != 3
        or any(type(n) is not int for n in cell)
        or not -(1 << 31) <= cell[0] < (1 << 31)
        or not -(1 << 31) <= cell[1] < (1 << 31)
        or not -32768 <= cell[2] < 32768
    ):
        raise ValueError("Invalid native displacement coordinate")
    return b"".join(_integer(k, n) for k, n in enumerate(cell, 1))


def displacement_additional(
    effect_class,
    *,
    destination=None,
    path=None,
    source_original=None,
    target_original=None,
    accepted=True,
):
    """Native b(iP) fields: eZB15/33, eXD70, eXk15/23."""
    if effect_class in (302, 340):
        if type(accepted) is not bool:
            raise ValueError("Unknown native teleport accepted flag")
        return _blob(15, position_payload(destination)) + _integer(33, int(accepted))
    if effect_class in (300, 301, 305, 331):
        if path is None:
            raise ValueError("Missing authoritative native displacement path")
        return (
            _blob(70, b"".join(_blob(1, position_payload(cell)) for cell in path))
            if path
            else b""
        )
    if effect_class == 422:
        # Native nvt/nvu/rDe = target old; rDb/rDc/rDd = source old.
        return _blob(15, position_payload(target_original)) + _blob(
            23, position_payload(source_original)
        )
    raise ValueError("Unknown native displacement family")


def displacement_packet(
    fight_id,
    action_id,
    *,
    uid,
    generic_effect,
    effect_class,
    caster_id,
    target_id,
    value,
    additional,
    base_uid=None,
    sequence=-1,
):
    if base_uid is None:
        base_uid = uid
    if (
        effect_class not in FAMILIES
        or type(uid) is not int
        or not 0 < uid < (1 << 63)
        or type(base_uid) is not int
        or not 0 <= base_uid < (1 << 63)
    ):
        raise ValueError("Invalid native displacement identity")
    if (
        any(
            type(v) is not int or v == 0 or not -(1 << 63) <= v < (1 << 63)
            for v in (caster_id, target_id)
        )
        or type(generic_effect) is not int
        or not 0 < generic_effect < (1 << 31)
        or type(value) is not int
        or not 0 <= value < (1 << 31)
    ):
        raise ValueError("Invalid native displacement actor/value")
    proto = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, base_uid),
            (3, generic_effect),
            (4, value),
            (6, caster_id),
            (7, target_id),
        )
    ) + _blob(8, additional)
    if len(proto) > 32767:
        raise ValueError("Native displacement proto too large")
    return (
        12613,
        struct.pack(
            ">iiiBih", fight_id, action_id, sequence, 0, effect_class, len(proto)
        )
        + proto,
    )


def cardinal_vector(dx, dy):
    """aBA.bXz -> aBz.bp uses float32 -atan2 and four native sectors."""
    if dx == 0 and dy == 0:
        return (0, 0)
    angle = _float32(-_float32(math.atan2(_float32(dy), _float32(dx))))
    quarter = _float32(math.pi / 4)
    three = _float32(3 * math.pi / 4)
    if quarter <= angle < three:
        return (0, -1)
    if -quarter <= angle < quarter:
        return (1, 0)
    if -three <= angle < -quarter:
        return (0, 1)
    return (-1, 0)


def _facing_vector(actor, *, forced=False, reverse=False):
    """eGj.bcy/baA, aAS.bWo/bWj, then faz.bcy cardinalization.

    pGJ is a separate override: absence of its snapshot is not evidence of null.
    """
    direction = getattr(actor, "direction", None)
    if forced:
        if not hasattr(actor, "native_forced_direction"):
            raise ValueError("Missing native eGj.pGJ forced-direction snapshot")
        override = actor.native_forced_direction
        if override is not None:
            direction = override
    if type(direction) is not int or direction not in range(8):
        raise ValueError("Missing native planar actor orientation")
    dx, dy = ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1))[
        direction
    ]
    return cardinal_vector(-dx if reverse else dx, -dy if reverse else dy)


def displacement_geometry(
    effect, level, *, source, target, cell, teleport_recipient_is_fighter=None
):
    """Pure eXD.C/eXK/eXJ fOu/faz.bcy geometry; no actor IDs select behavior."""
    kind = FAMILIES[effect["effect_class"]]
    raw = effect["parameters"]
    count = len(raw) // 2
    values = [parameter_value(raw, n, level) for n in range(count)]
    if kind in ("push", "pull", "move_away_cell", "approach_cell"):
        if (kind == "approach_cell" and count not in (0, 1, 2)) or (
            kind != "approach_cell"
            and (not 1 <= count <= 3 or (kind == "move_away_cell" and count != 1))
        ):
            raise ValueError("Unsupported native displacement parameter count")
        distance = (
            (abs(source.position[0] - cell[0]) + abs(source.position[1] - cell[1]))
            if kind == "approach_cell" and not count
            else values[0]
        )
        if not 0 <= distance <= 6552:
            raise ValueError("Unsupported native displacement distance")
        loss_ap = values[1] > 0 if count >= 2 else kind != "pull"
        mode = ((values[2] + 128) % 256) - 128 if count >= 3 else -1
        actor = source if kind in ("move_away_cell", "approach_cell") else target
        if actor is None:
            raise ValueError("Native displacement target absent")
        if kind == "approach_cell":
            vector = cardinal_vector(
                cell[0] - actor.position[0], cell[1] - actor.position[1]
            )
            stop = cell[:2]
            loss_ap = False  # eXq.fOs=false regardless of inherited rDX.
        elif kind == "move_away_cell":
            vector = cardinal_vector(
                actor.position[0] - cell[0], actor.position[1] - cell[1]
            )
            stop = None
        elif kind == "push":
            if mode in (0, 1, 2, 3):
                vector = ((0, -1), (1, 0), (-1, 0), (0, 1))[mode]
            elif mode == 5:
                vector = cardinal_vector(
                    actor.position[0] - cell[0], actor.position[1] - cell[1]
                )
            elif mode == 4:
                vector = _facing_vector(actor, forced=True, reverse=True)
            elif mode == 7:
                vector = _facing_vector(source)
            elif mode == -1 or mode not in range(8):
                vector = cardinal_vector(
                    actor.position[0] - source.position[0],
                    actor.position[1] - source.position[1],
                )
            else:
                raise ValueError(
                    "Displacement direction requires native forced-direction/random context"
                )
            stop = None
        else:
            if count < 3:
                toward = cardinal_vector(
                    target.position[0] - source.position[0],
                    target.position[1] - source.position[1],
                )
                stop = (source.position[0] + toward[0], source.position[1] + toward[1])
                vector = cardinal_vector(
                    stop[0] - actor.position[0], stop[1] - actor.position[1]
                )
            elif mode == 5:
                vector = cardinal_vector(
                    cell[0] - actor.position[0], cell[1] - actor.position[1]
                )
                stop = None
            elif mode in (0, 1, 2, 3):
                vector = ((0, -1), (1, 0), (-1, 0), (0, 1))[mode]
                stop = None
            elif mode == 4:
                vector = _facing_vector(actor, forced=True, reverse=True)
                stop = None
            else:
                raise ValueError("Unsupported native pull direction context")
        return dict(
            actor=actor,
            distance=distance,
            vector=vector,
            stop=stop,
            loss_ap=loss_ap,
            collision_reactions=kind in ("push", "pull"),
        )
    if kind.startswith("teleport"):
        if count > 4:
            raise ValueError("Unsupported native teleport parameters")
        if count and values[0] == 1 and teleport_recipient_is_fighter is not True:
            raise ValueError("Qq owner teleport requires wrapped actor context")
        return dict(
            actor=source if kind == "teleport_caster" else target,
            force=count >= 3 and values[2] == 1,
            carried=count >= 2 and values[1] == 1,
            check_cells=count < 4 or values[3] == 1,
            destination=tuple(cell),
        )
    if kind == "swap":
        if count > 1:
            raise ValueError("Unsupported native swap parameters")
        return dict(source=source, target=target, force=count == 1 and values[0] == 1)
    raise ValueError("Unsupported native displacement family")


class NativeDisplacementHandler:
    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        authority,
        selected_surface=None,
    ):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.authority = allocate_uid, authority
        self.event_lifecycle = None
        self.selected_surface = selected_surface
        self.collision_executor = None
        self.carry_release_executor = None
        self.prepared_teleports = {}

    def _selected_surface(self, cell):
        """eZB.C requires QI.i even when rIy disables occupancy checks."""
        if self.selected_surface is not None:
            return self.selected_surface(self.fight, cell)
        from .combat_qi_snapshot import NativeQISnapshot
        from .combat_qi_surface_catalog import (
            native_qi_surfaces,
            native_qi_surface_provenance,
        )

        provenance = getattr(self.fight, "native_qi_surface_provenance", None)
        if not isinstance(provenance, dict):
            raise ValueError(
                "Teleport requires actual native selected-surface provenance"
            )
        map_id = provenance.get("map_id")
        if provenance != native_qi_surface_provenance(map_id):
            raise ValueError("Teleport native selected-surface provenance mismatch")
        qi = NativeQISnapshot(getattr(self.fight, "native_qi_snapshot", None))
        return native_qi_surfaces(map_id).i(qi, *cell)

    def native_eligibility(self, effect, invocation):
        # eZB/eZC/eZD inherit eZR.i. Reject an actual corpse before n/C
        # computes teleport acceptance or emits the preparation lifecycle.
        if effect["effect_class"] not in (302, 340):
            return True
        recipient = self.fight.actors.get(invocation.target_id)
        if recipient is None:
            return True
        from .combat_runner_target_life import runner_target_life_eligible

        return runner_target_life_eligible(
            self.fight, recipient, effect, invocation=invocation
        )

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        from dataclasses import replace

        invocation = replace(invocation, native_running_uid=self.allocate_uid())
        self.event_lifecycle.phase(
            effect, invocation, uid=invocation.native_running_uid, value=0, channel=1
        )
        if FAMILIES[effect["effect_class"]].startswith("teleport"):
            self.prepared_teleports[
                invocation.native_running_uid
            ] = self._calculate_teleport(effect, invocation)
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared_teleports.pop(invocation.native_running_uid, None)

    def _calculate_teleport(self, effect, invocation):
        source = self.fight.actors[invocation.caster_id]
        target = self.fight.actors.get(invocation.target_id)
        recipient = source if effect["effect_class"] == 302 else target
        # eZC/eZD.fRz redirects operand-zero=1 only for an actual Qq.
        # The ordinary eGj path returns the original fighter unchanged.
        recipient_is_fighter = None
        parameters = effect.get("parameters")
        if (
            recipient is not None
            and parameters
            and parameter_value(parameters, 0, invocation.level) == 1
        ):
            recipient_is_fighter = self.authority(self.fight, recipient).targeting.get(
                "is_eGj"
            )
        geometry = displacement_geometry(
            effect,
            invocation.level,
            source=source,
            target=target,
            cell=invocation.cell,
            teleport_recipient_is_fighter=recipient_is_fighter,
        )
        accepted = self._teleport_accepted(
            geometry, source, set(effect["native_effect_flags"])
        )
        return geometry, accepted

    def _finish_events(self, effect, invocation, uid, value):
        if self.event_lifecycle is not None:
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect, invocation, uid=uid, value=value, channel=channel
                )

    def _ordinary(self, actor, *, allow_radius=False, allow_carrying=False):
        authority = self.authority(self.fight, actor)
        unsupported_life = actor.hp <= 0
        if unsupported_life:
            from .combat_hp_raw import hp_raw_present, hp_raw_current

            life = authority.targeting
            if (
                life.get("baF") is True
                and life.get("baG") is False
                and life.get("baK") is False
                and hp_raw_present(actor)
            ):
                # QK/fax participation follows fdy, not the HP scalar. During
                # an owned effect chain PA can reach0 before death settlement.
                hp_raw_current(actor)
                unsupported_life = False
        if (
            unsupported_life
            or not allow_radius
            and actor.physical_radius != 0
            or authority.is_carried
            or authority.is_carrying is not False
            and not (allow_carrying and authority.is_carrying is True)
        ):
            error = ValueError(
                "Native displacement requires a living ordinary radius0 actor with empty carry relations"
            )
            error.native_displacement_actor = dict(
                actor_id=actor.id,
                hp=actor.hp,
                physical_radius=actor.physical_radius,
                is_carried=authority.is_carried,
                is_carrying=authority.is_carrying,
                baF=authority.targeting.get("baF"),
                baG=authority.targeting.get("baG"),
                baK=authority.targeting.get("baK"),
                native_hp_operand_verified=not unsupported_life
                if actor.hp <= 0
                else None,
            )
            raise error
        return self.authority.properties(self.fight, actor)

    def _free(self, actor, cell, *, ignore=()):
        if cell not in self.fight.walkable:
            return False
        obstacles = getattr(self.fight, "native_obstacle_cells", None)
        if obstacles is not None and cell in obstacles:
            return False
        return not any(
            other.id not in {actor.id, *ignore}
            and other.hp > 0
            and other.position[:2] == cell[:2]
            for other in self.fight.actors.values()
        )

    def _teleport_free(self, actor, cell):
        """QI.a(amP,aBn) for the verified ordinary radius-zero QK."""
        from .combat_qi_fight import current_registry

        registry = current_registry(self.fight)
        qi = registry.snapshot()
        if not qi.aK(*cell[:2]):
            return False
        index = (cell[1] - qi.y) * qi.width + cell[0] - qi.x
        if qi.masks[index] & 768:
            return False
        override = getattr(self.fight, "native_qi_movement_override", None)
        if type(override) is not bool:
            raise ValueError("Missing actual QI movement override")
        if override:
            return True
        ignored = getattr(self.fight, "native_qi_ignored_slots", None)
        if not isinstance(ignored, (list, tuple)) or any(
            type(slot) is not int or not 0 <= slot <= 126 for slot in ignored
        ):
            raise ValueError("Missing actual QI temporarily ignored obstacle IDs")
        own_slot = actor.native_obstacle_id
        if (
            type(own_slot) is not int
            or not 0 <= own_slot <= 126
            or registry.slots[own_slot]["identity"] != ["actor", actor.id]
        ):
            raise ValueError("Missing actual teleport QK registration")
        return not any(
            slot != own_slot
            and slot not in ignored
            and registry.slots[slot]["movement_blocking"]
            for slot in (qi.U(*cell[:2]) or ())
        )

    def _forced_obstruction(self, actor, cell):
        """faz's QI.g and QI.V, with actual registered QK population.

        QI.V selects the first QL byte-set iterator element, independently of
        the QK that made QI.g true. Larger sets consume the persisted native
        Trove insertion/deletion topology; singleton order is unambiguous.
        """
        from .combat_qi_fight import current_registry

        registry = current_registry(self.fight)
        qi = registry.snapshot()
        own = registry._owned(actor.native_obstacle_id, ("actor", actor.id))
        if not own["movement_blocking"]:
            return False, None
        x, y = cell[:2]
        index = qi._int32(
            qi._int32(qi._int32(y - qi.y) * qi.width) + qi._int32(x - qi.x)
        )
        slots = qi.U(x, y) or ()
        if not 0 <= index < len(qi.masks):
            obstructed = True
        elif qi.masks[index] & 768:
            obstructed = True
        else:
            override = getattr(self.fight, "native_qi_movement_override", None)
            ignored = getattr(self.fight, "native_qi_ignored_slots", None)
            if type(override) is not bool:
                raise ValueError("Missing actual QI movement override")
            if not isinstance(ignored, (list, tuple)) or any(
                type(slot) is not int or not 0 <= slot <= 126 for slot in ignored
            ):
                raise ValueError("Missing actual QI temporarily ignored obstacle IDs")
            obstructed = not override and any(
                slot not in ignored and registry.slots[slot]["movement_blocking"]
                for slot in slots
            )
        if not obstructed:
            return False, None
        if not slots:
            return True, None
        order = registry.ordered_U(x, y) if len(slots) > 1 else tuple(slots)
        row = registry.slots[order[0]]
        kind, identity = row["identity"]
        if kind == "actor":
            # faz.c ignores its own QK returned by QI.V, including footprint
            # cells that overlap the actor's current registered square.
            return (False, None) if identity == actor.id else (True, identity)
        from .combat_state_managers import registered_area_pv

        area = registered_area_pv(self.fight, identity)
        if area is None:
            raise ValueError("Missing actual registered collision Qq PV")
        return True, area.id

    def _teleport_accepted(self, geometry, source, flags):
        """eZB.C captures acceptance before mutable level-two reactions."""
        actor = geometry["actor"]
        if actor is None:
            # eZB.C sets rIw=false when fRz() is not an eGj PV. Its later c()
            # path then returns without applying the teleport.
            return False
        props = self.authority.properties(self.fight, actor)
        destination = geometry["destination"]
        if self._selected_surface(destination) is None:
            return False
        if not geometry["force"] and (
            57 in props
            or (
                36 not in flags
                and (
                    11 in props
                    or 110 in props
                    and source.team != actor.team
                    or 111 in props
                    and source.team == actor.team
                    and self.authority(self.fight, actor).is_carried
                )
            )
        ):
            return False
        # eZB writes PV.b(IIS) directly; unlike eXD it does not uncarry.
        self._ordinary(actor, allow_carrying=True)
        return not geometry["check_cells"] or self._teleport_free(actor, destination)

    def __call__(self, effect, values, invocation):
        if self.fight.phase != "active" or self.fight.current is None:
            raise ValueError("Displacement requires active combat")
        # eZR.i rejects an actual corpse before invoking eXD.c/eXk.c. A proven
        # rejection skips this runner; it does not reject its parent spell.
        if effect["effect_class"] in (300, 301, 422):
            recipient = self.fight.actors.get(invocation.target_id)
            if recipient is not None:
                from .combat_runner_target_life import runner_target_life_eligible

                if not runner_target_life_eligible(
                    self.fight, recipient, effect, invocation=invocation
                ):
                    return False
        flags = set(effect["native_effect_flags"])
        # eVl.rwA(3) suppresses aJs client zone preview only; preserve it
        # in the native definition without changing forced path/codec.
        # eVl.rwK/rwW are consumed only by faK target ordering, already
        # applied by the common resolver before each displacement invocation.
        # Flag5 suppresses level-one reactions through the existing event
        # lifecycle (eZR.aZB); it does not prevent native displacement.
        # Flag37 skips eXD.fOQ uncarry. Its only native consumer returns
        # before the flag check when the ordinary actor's frA() is false.
        if flags - {3, 5, 13, 14, 17, 26, 36, 37}:
            raise ValueError(
                f"Unhandled native displacement flags: {sorted(flags-{3,5,13,14,17,26,36,37})}"
            )
        native_definition_timing(effect, invocation.level)
        uid = invocation.native_running_uid
        kind = FAMILIES[effect["effect_class"]]
        if self.event_lifecycle is not None:
            if uid is None:
                # Direct/clone execution has no dispatcher prepare hook here.
                invocation = self.prepare(effect, values, invocation)
                uid = invocation.native_running_uid
        # eZB.C performs its surface/property/occupancy acceptance before L2.
        # eXD.c instead computes the forced path after L2 through fOZ; do not
        # move that family's calculation across the shared phase boundary.
        teleport_geometry = None
        teleport_accepted = None
        if kind.startswith("teleport"):
            if self.event_lifecycle is not None:
                if uid not in self.prepared_teleports:
                    raise ValueError("Missing prepared native teleport calculation")
                teleport_geometry, teleport_accepted = self.prepared_teleports.pop(uid)
            else:
                teleport_geometry, teleport_accepted = self._calculate_teleport(
                    effect, invocation
                )
            if not teleport_accepted:
                # eZB.c returns without movement when C set rIw=false.
                # Qe.bbJ still emits L2, and eZR.a continues into Qe.a's
                # L3/L4 completion after that ordinary return.
                if self.event_lifecycle is not None:
                    self.event_lifecycle.phase(
                        effect, invocation, uid=uid, value=0, channel=2
                    )
                    self._finish_events(effect, invocation, uid, 0)
                return False
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(effect, invocation, uid=uid, value=0, channel=2)
        if kind in ("push", "pull"):
            recipient = self.fight.actors.get(invocation.target_id)
            if recipient is None:
                if (
                    invocation.target_id is not None
                    and invocation.target_id
                    not in getattr(self.fight, "native_effect_areas", {})
                ):
                    raise ValueError("Unknown native displacement target PV")
                if invocation.target_id is not None:
                    from .combat_area_authority import area_guards

                    area_guards(self.fight, invocation.target_id)
                # eXD.c resolves fOt first; eXJ/eXK return null for null/Qq.
                # Native cancels this runner before geometry/caster guards.
                self._finish_events(effect, invocation, uid, 0)
                return False
            if self.authority(self.fight, recipient).is_carried:
                self._finish_events(effect, invocation, uid, 0)
                return False
        source = self.fight.actors.get(invocation.caster_id)
        if source is None and kind in ("push", "pull"):
            from .combat_area_authority import area_guards
            from .combat_effect_area_targets import area_targets

            area_guards(self.fight, invocation.caster_id)
            source = next(
                (
                    area
                    for area in area_targets(self.fight)
                    if area.id == invocation.caster_id
                ),
                None,
            )
        if source is None:
            raise ValueError("Missing native displacement source PV")
        # eXp/eXq.fOr -> eXD.fOS reads caster fax.buX before path calculation.
        if (
            kind in ("move_away_cell", "approach_cell")
            and self.authority(self.fight, source).is_carried
        ):
            self._finish_events(effect, invocation, uid, 0)
            return False
        # eXD only tests mobility of fOt(), not its possibly carried caster.
        source_props = (
            self.authority.properties(self.fight, source)
            if source.id in self.fight.actors
            else ()
        )
        target = self.fight.actors.get(invocation.target_id)
        geometry = teleport_geometry or displacement_geometry(
            effect, invocation.level, source=source, target=target, cell=invocation.cell
        )
        changed = []
        path = None
        additional = None
        value = 0
        collision = None
        if kind == "swap":
            if target is None:
                raise ValueError("Swap requires native actor target")
            # eXk.c rejects buX on either actual eHH before coordinates change.
            if any(
                self.authority(self.fight, actor).is_carried
                for actor in (source, target)
            ):
                self._finish_events(effect, invocation, uid, 0)
                return False
            target_props = self.authority.properties(self.fight, target)
            if target.id == source.id:
                self._finish_events(effect, invocation, uid, 0)
                return True
            if not geometry["force"] and 36 not in flags:
                if (
                    {11, 55} & source_props
                    or {11, 55} & target_props
                    or (
                        (110 in source_props or 110 in target_props)
                        and source.team != target.team
                    )
                    or (
                        (111 in source_props or 111 in target_props)
                        and source.team == target.team
                    )
                ):
                    self._finish_events(effect, invocation, uid, 0)
                    return False
            # eXk exchanges actual PV coordinates without QI.a/free-cell or
            # radius-zero checks. Shared eGj relocation retains each QK's
            # complete footprint and recursively moves its carried partner.
            self._ordinary(source, allow_radius=True, allow_carrying=True)
            self._ordinary(target, allow_radius=True, allow_carrying=True)
            a, b = source.position, target.position
            additional = displacement_additional(
                effect["effect_class"], source_original=a, target_original=b
            )
            changed = [(source, b), (target, a)]
        elif kind.startswith("teleport"):
            actor = geometry["actor"]
            destination = geometry["destination"]
            additional = displacement_additional(
                effect["effect_class"], destination=destination
            )
            changed = [(actor, destination)]
            target = actor
        else:
            actor = geometry["actor"]
            props = self.authority.properties(self.fight, actor)
            blocked_property = (
                71
                if kind == "approach_cell"
                else 83
                if kind == "move_away_cell"
                else 56
            )
            if 3 in props or blocked_property in props:
                self._finish_events(effect, invocation, uid, 0)
                return False
            if (
                13 not in flags
                and 36 not in flags
                and (
                    11 in props
                    or 110 in props
                    and source.team != actor.id
                    or 111 in props
                    and source.team == actor.id
                )
            ):
                self._finish_events(effect, invocation, uid, 0)
                return False
            # Native flag37 returns from fOQ before looking up an uncarry
            # definition. Base eGj movement then retains its carried partner.
            self._ordinary(
                actor,
                allow_radius=True,
                allow_carrying=37 in flags or callable(self.carry_release_executor),
            )
            vector = geometry["vector"]
            path = []
            position = actor.position
            forced_source_index = None
            for step in range(geometry["distance"]):
                if vector == (0, 0) or geometry["stop"] == position[:2]:
                    break
                xy = (position[0] + vector[0], position[1] + vector[1])
                native_registry = (
                    getattr(self.fight, "native_qi_slots", None) is not None
                )
                terrain_valid = True
                if native_registry:
                    from .combat_qi_fight import current_registry

                    terrain_valid = current_registry(self.fight).terrain.R(*xy)
                metadata = self.authority(self.fight, actor)
                map_id = metadata.native_instance_id
                if actor.physical_radius:
                    if not native_registry or map_id is None:
                        raise ValueError(
                            "Large forced footprint requires actual QI and physical map columns"
                        )
                    from .combat_forced_footprint import (
                        forced_footprint_step,
                        forced_physical_columns,
                    )

                    step_result = forced_footprint_step(
                        position,
                        xy,
                        radius=actor.physical_radius,
                        height=actor.native_los_height,
                        physical_column=forced_physical_columns(map_id).column,
                        terrain_valid=current_registry(self.fight).terrain.R,
                        obstruction=lambda cell: self._forced_obstruction(actor, cell),
                        source_index=forced_source_index,
                    )
                    if step_result.destination is None:
                        if step_result.collision and geometry["collision_reactions"]:
                            if not callable(self.collision_executor):
                                raise ValueError(
                                    "Native displacement collision requires AP-loss/events executor"
                                )
                            collision = (
                                actor.id,
                                step_result.collider_id,
                                geometry["loss_ap"],
                            )
                        break
                    path.append(step_result.destination)
                    position = step_result.destination
                    forced_source_index = step_result.destination_index
                    continue
                if not terrain_valid:
                    destination = None
                elif map_id is not None:
                    # eGj.bvz() is 4 for the audited ordinary actor creation
                    # path; faz uses bcK (breed height), not walking Sm(3,0,2).
                    from .combat_forced_terrain import next_surface

                    destination = next_surface(
                        map_id,
                        actor.native_los_height,
                        position,
                        xy,
                        radius=actor.physical_radius,
                        jump=4,
                    )
                else:
                    # Explicit legacy fixture geometry cannot attest height
                    # changes. Production authorities carry their map identity.
                    candidates = [
                        cell
                        for cell in self.fight.walkable
                        if cell[:2] == xy and cell[2] == position[2]
                    ]
                    destination = candidates[0] if len(candidates) == 1 else None
                    if (
                        destination is not None
                        and self.fight.edges is not None
                        and (position, destination) not in self.fight.edges
                    ):
                        raise ValueError(
                            "Native forced terrain transition requires verified edge"
                        )
                obstructed, collider = (False, None)
                if destination is not None:
                    if native_registry:
                        obstructed, collider = self._forced_obstruction(
                            actor, (xy[0], xy[1], position[2])
                        )
                    else:
                        obstructed = not self._free(actor, destination)
                if destination is None or obstructed:
                    if not geometry["collision_reactions"]:
                        # eXp/eXq.fOs=false: truncate without fPa AP/event204.
                        break
                    if not native_registry or not callable(self.collision_executor):
                        raise ValueError(
                            "Native displacement collision requires AP-loss/events executor"
                        )
                    collision = (actor.id, collider, geometry["loss_ap"])
                    break
                path.append(destination)
                position = destination
            value = len(path)
            additional = displacement_additional(effect["effect_class"], path=path)
            changed = [(actor, position)]
            target = actor
        uid = self.allocate_uid() if uid is None else uid
        packet = displacement_packet(
            self.fight.id,
            self.action_id,
            uid=uid,
            generic_effect=invocation.reference,
            effect_class=effect["effect_class"],
            caster_id=source.id,
            target_id=target.id,
            value=value,
            additional=additional,
            base_uid=invocation.base_uid,
        )
        moved = [
            (actor.id, actor.position, position)
            for actor, position in changed
            if actor.position != position
        ]
        for actor, position in changed:
            if (
                kind in ("push", "pull", "move_away_cell", "approach_cell")
                and actor.position != position
                and 37 not in flags
                and self.authority(self.fight, actor).is_carrying
            ):
                self.carry_release_executor(effect, invocation, actor)
            from .combat_qi_fight import move_registered_actor

            move_registered_actor(self.fight, actor, position)
        self.packets.append(packet)
        if collision is not None:
            displaced, collider, loss_ap = collision
            self.collision_executor(
                effect,
                invocation,
                uid=uid,
                value=value,
                displaced_id=displaced,
                collider_id=collider,
                loss_ap=loss_ap,
            )
        self._finish_events(effect, invocation, uid, value)
        if moved and self.event_lifecycle is not None:
            self.event_lifecycle.displacement_completed(
                effect, invocation, uid=uid, value=value, moved=moved
            )
        self.fight._event(
            "effect_displacement",
            effect_class=effect["effect_class"],
            caster_id=source.id,
            actors=tuple((actor.id, position) for actor, position in changed),
            path=path,
        )
        return True
