"""Native eXK/eXJ/eXp displacement, eZC/eZD teleport and eXk swap.

Ordinary actors, radius0, flat terrain and collision-free paths are audited.
Collision AP loss/events, footprint/altitude mechanics and wrapped actors need
additional native machinery and reject before any preview mutation.
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
    if effect_class in (300, 301, 331):
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


def displacement_geometry(effect, level, *, source, target, cell):
    """Pure eXD.C/eXK/eXJ fOu/faz.bcy geometry; no actor IDs select behavior."""
    kind = FAMILIES[effect["effect_class"]]
    raw = effect["parameters"]
    count = len(raw) // 2
    values = [parameter_value(raw, n, level) for n in range(count)]
    if kind in ("push", "pull", "move_away_cell"):
        if not 1 <= count <= 3 or (kind == "move_away_cell" and count != 1):
            raise ValueError("Unsupported native displacement parameter count")
        distance = values[0]
        if not 0 <= distance <= 6552:
            raise ValueError("Unsupported native displacement distance")
        loss_ap = values[1] > 0 if count >= 2 else kind != "pull"
        mode = ((values[2] + 128) % 256) - 128 if count >= 3 else -1
        actor = source if kind == "move_away_cell" else target
        if actor is None:
            raise ValueError("Native displacement target absent")
        if kind == "move_away_cell":
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
            actor=actor, distance=distance, vector=vector, stop=stop, loss_ap=loss_ap
        )
    if kind.startswith("teleport"):
        if count > 4:
            raise ValueError("Unsupported native teleport parameters")
        if count and values[0] == 1:
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
    def __init__(self, fight, packets, *, action_id, allocate_uid, authority):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.authority = allocate_uid, authority

    def _ordinary(self, actor):
        authority = self.authority(self.fight, actor)
        if actor.hp <= 0 or actor.physical_radius != 0 or authority.is_carried:
            raise ValueError(
                "Native displacement requires a living ordinary radius0 uncarried actor"
            )
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

    def __call__(self, effect, values, invocation):
        if self.fight.phase != "active" or self.fight.current is None:
            raise ValueError("Displacement requires active combat")
        flags = set(effect["native_effect_flags"])
        if flags - {13, 17, 36}:
            raise ValueError(
                f"Unhandled native displacement flags: {sorted(flags-{13,17,36})}"
            )
        native_definition_timing(effect, invocation.level)
        source = self.fight.actors[invocation.caster_id]
        source_props = self._ordinary(source)
        target = self.fight.actors.get(invocation.target_id)
        kind = FAMILIES[effect["effect_class"]]
        geometry = displacement_geometry(
            effect, invocation.level, source=source, target=target, cell=invocation.cell
        )
        changed = []
        path = None
        additional = None
        value = 0
        if kind == "swap":
            if target is None:
                raise ValueError("Swap requires native actor target")
            target_props = self._ordinary(target)
            if target.id == source.id:
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
                    return False
            a, b = source.position, target.position
            if not self._free(source, b, ignore=(target.id,)) or not self._free(
                target, a, ignore=(source.id,)
            ):
                return False
            additional = displacement_additional(
                effect["effect_class"], source_original=a, target_original=b
            )
            changed = [(source, b), (target, a)]
        elif kind.startswith("teleport"):
            actor = geometry["actor"]
            if actor is None:
                raise ValueError("Teleport requires native actor")
            props = self._ordinary(actor)
            if not geometry["force"] and (
                57 in props
                or (
                    36 not in flags
                    and (11 in props or 110 in props and source.team != actor.team)
                )
            ):
                return False
            destination = geometry["destination"]
            if not geometry["check_cells"]:
                raise ValueError(
                    "Teleport bypass of blocking cells requires native terrain policy"
                )
            if not self._free(actor, destination):
                return False
            additional = displacement_additional(
                effect["effect_class"], destination=destination
            )
            changed = [(actor, destination)]
            target = actor
        else:
            actor = geometry["actor"]
            props = self._ordinary(actor)
            if 3 in props or (83 if kind == "move_away_cell" else 56) in props:
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
                return False
            vector = geometry["vector"]
            path = []
            position = actor.position
            for step in range(geometry["distance"]):
                if vector == (0, 0) or geometry["stop"] == position[:2]:
                    break
                xy = (position[0] + vector[0], position[1] + vector[1])
                candidates = [
                    cell
                    for cell in self.fight.walkable
                    if cell[:2] == xy and cell[2] == position[2]
                ]
                if len(candidates) != 1 or not self._free(actor, candidates[0]):
                    raise ValueError(
                        "Native displacement collision requires AP-loss/events executor"
                    )
                destination = candidates[0]
                if (
                    self.fight.edges is not None
                    and (position, destination) not in self.fight.edges
                ):
                    raise ValueError(
                        "Native forced terrain transition requires verified edge"
                    )
                path.append(destination)
                position = destination
            value = len(path)
            additional = displacement_additional(effect["effect_class"], path=path)
            changed = [(actor, position)]
            target = actor
        packet = displacement_packet(
            self.fight.id,
            self.action_id,
            uid=self.allocate_uid(),
            generic_effect=invocation.reference,
            effect_class=effect["effect_class"],
            caster_id=source.id,
            target_id=target.id,
            value=value,
            additional=additional,
            base_uid=invocation.base_uid,
        )
        for actor, position in changed:
            actor.position = position
        self.packets.append(packet)
        self.fight._event(
            "effect_displacement",
            effect_class=effect["effect_class"],
            caster_id=source.id,
            actors=tuple((actor.id, position) for actor, position in changed),
            path=path,
        )
        return True
