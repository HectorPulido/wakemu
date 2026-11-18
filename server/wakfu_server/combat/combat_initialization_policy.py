"""Explicit development fallback for unevaluated owned equipment effects.

Equipment bonuses evaluates these branches without mutating a fighter. Skipping
one therefore preserves supported bonuses and never retains partial effects.
Validation failures, unknown item templates and aptitude failures remain fatal.
"""

from copy import deepcopy


def partition_unsupported_equipment(effects, *, enabled):
    if type(enabled) is not bool:
        raise ValueError("Development initialization fallback must be boolean")
    rejected, skipped = [], []
    for effect in effects:
        permitted = (
            isinstance(effect, dict)
            and effect.get("reason") == "unsupported-native-effect"
            and all(
                type(effect.get(key)) is int
                for key in ("uid", "reference", "effect_id", "generic")
            )
            and effect["uid"] > 0
            and effect["reference"] > 0
        )
        (skipped if enabled and permitted else rejected).append(deepcopy(effect))
    return rejected, skipped


def initialization_warning(actor_id, effect):
    return dict(actor_id=actor_id, stage="owned-equipment-snapshot", **effect)


def warning_text(warning):
    return (
        "Modo desarrollo: efecto de equipo omitido "
        f"(objeto {warning['reference']}, UID {warning['uid']}, "
        f"efecto {warning['effect_id']}, familia {warning['generic']}: "
        f"{warning['reason']}). Los demás efectos siguen activos."
    )


def safe_rejection_text(error):
    """Bound and escape native diagnostic text for a client chat label."""
    import html

    message = _line_of_sight_rejection(error) or str(error)
    text = "".join(c if c.isprintable() else " " for c in message)
    return "Acción rechazada: " + html.escape(text[:480], quote=False)


def _line_of_sight_rejection(error):
    """Explain the actual native LOS decision without changing its authority."""
    if getattr(error, "native_casting_result", None) != "twG":
        return None
    diagnostic = getattr(error, "native_casting_diagnostic", None)
    if not isinstance(diagnostic, dict):
        return None
    flags = diagnostic.get("selected_casting_flags")
    if not isinstance(flags, dict) or flags.get("line_of_sight") is not True:
        return None
    trace = diagnostic.get("trace")
    if not isinstance(trace, list):
        return None
    for entry in trace:
        if not isinstance(entry, dict) or entry.get("stage") != "native_los_detail":
            continue
        detail = entry.get("value")
        if not isinstance(detail, dict) or detail.get("result") is not False:
            continue
        rays = detail.get("rays")
        if not isinstance(rays, list):
            continue
        for ray in rays:
            cell = ray.get("blocked_probe") if isinstance(ray, dict) else None
            if (
                isinstance(cell, (list, tuple))
                and len(cell) == 2
                and all(
                    type(value) is int and -(2**31) <= value < 2**31
                    for value in cell
                )
            ):
                return (
                    "Línea de visión bloqueada por un obstáculo en "
                    f"({cell[0]}, {cell[1]}). Cambia de posición."
                )
        return "No tienes línea de visión hacia esa casilla. Cambia de posición."
    return None
