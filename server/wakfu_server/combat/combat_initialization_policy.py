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

    text = "".join(c if c.isprintable() else " " for c in str(error))
    return "Acción rechazada: " + html.escape(text[:480], quote=False)
