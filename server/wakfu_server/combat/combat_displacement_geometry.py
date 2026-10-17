"""Pure native displacement geometry, independent of catalogs and combat services."""
import math
from .combat_parameters import parameter_value, _float32

FAMILIES = {
    300: "push",
    301: "pull",
    302: "teleport_caster",
    340: "teleport_target",
    331: "move_away_cell",
    305: "approach_cell",
    422: "swap",
}


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
    effect,
    level,
    *,
    source,
    target,
    cell,
    teleport_recipient_is_fighter=None,
    draw_direction=None,
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
            elif mode == 6:
                # eXK.fOu -> UK.al(1,4): the native ordering differs from
                # explicit modes0..3. Consume one transaction-owned draw.
                if not callable(draw_direction):
                    raise ValueError(
                        "Random displacement requires transaction-owned direction RNG"
                    )
                draw = draw_direction()
                if type(draw) is not int or not 1 <= draw <= 4:
                    raise ValueError(
                        "Invalid native random displacement direction draw"
                    )
                vector = ((0, -1), (-1, 0), (1, 0), (0, 1))[draw - 1]
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
                # eXJ.fOu has explicit cases0..5 only. Every other byte,
                # including6, uses the source-to-target direction (no draw).
                # fPi maps equal XY to aAS.NONE, also represented by (0,0).
                vector = cardinal_vector(
                    actor.position[0] - source.position[0],
                    actor.position[1] - source.position[1],
                )
                stop = None
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
