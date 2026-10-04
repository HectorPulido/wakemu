"""Native eXe421 selection over a verified complete retained-effect view."""
from .combat_retained_effects import default_dispel_eligible
from .combat_native_timing_context import native_definition_timing


def select_dispel(entries, parameters):
    if any(type(p) is not int for p in parameters):
        raise ValueError("Native evaluated dispel parameters required")
    if len(parameters) > 2:
        raise ValueError("Unaudited native dispel parameter variant")
    requested = parameters[0] if parameters else -(1 << 31)
    action_id = len(parameters) == 2
    selected = []
    for entry in entries:
        # Native exact matches precede E protection and class421 exclusion.
        identity = entry.effect_class if action_id else entry.generic_effect
        if requested == identity:
            selected.append(entry)
            continue
        if requested == -(1 << 31) and default_dispel_eligible(entry):
            selected.append(entry)
    return tuple(selected)


class NativeDispelHandler:
    def __init__(self, *, view_provider, removal_provider):
        self.view_provider = view_provider
        self.removal_provider = removal_provider

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 421:
            raise ValueError("Wrong native dispel family")
        if effect["native_effect_flags"]:
            raise ValueError("Unaudited native dispel flags")
        native_definition_timing(effect, invocation.level)
        view = self.view_provider()
        removal = self.removal_provider(view)
        if removal.view is not view:
            raise ValueError("Native dispel/removal views disagree")
        if invocation.target_id not in view.fight.actors:
            raise ValueError("Missing native dispel target")
        selected = select_dispel(
            (
                e
                for e in view.entries
                if (e.manager_id if e.manager_id is not None else e.target_id)
                == invocation.target_id
            ),
            values["parameters"],
        )
        removal.remove(e.uid for e in selected)
        return True  # eXe.c calls mu(true) even when no retained effect matches.
