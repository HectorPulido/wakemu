"""Native eXe421 selection over a verified complete retained-effect view."""
from .combat_retained_effects import default_dispel_eligible
from .combat_native_timing_context import native_definition_timing
from dataclasses import replace
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_runner_callbacks import notify_runner_value

# Source eVl IDs, not enum ordinals. eXe.c/E do not read guild or damage style.
# The two trigger flags remain owned by the actual shared Qe event lifecycle.
FLAG_SEMANTICS = {
    3: "client_zone_display_only",
    5: "generic_level_one_suppression",
    6: "generic_level_two_suppression",
    # eVl.rwN is BUFF_BYPASS_OUT_FIGHT_MAX (ID17, not ordinal15).
    # eXe.c/E only select/remove retained effects; neither reads PA maxima
    # or this buff-application flag. Generic Qe trigger flags stay separate.
    17: "out_of_fight_buff_cap_not_read_by_eXe",
    20: "guild_metadata_not_read_by_eXe",
    24: "damage_distance_tag_not_read_by_eXe",
}


def dispel_flags(effect, *, event_lifecycle):
    flags = effect.get("native_effect_flags")
    if (
        not isinstance(flags, (list, tuple))
        or any(type(flag) is not int for flag in flags)
        or len(set(flags)) != len(flags)
    ):
        raise ValueError("Missing exact native dispel flag set")
    unknown = set(flags) - FLAG_SEMANTICS.keys()
    if unknown:
        raise ValueError(f"Unaudited native dispel flags: {sorted(unknown)}")
    if set(flags) & {5, 6} and event_lifecycle is None:
        raise ValueError("Native dispel trigger flags require actual Qe lifecycle")
    return tuple(flags)


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
    def __init__(
        self,
        *,
        view_provider,
        removal_provider,
        allocate_uid=None,
        rng=None,
        event_lifecycle=None,
    ):
        self.view_provider = view_provider
        self.removal_provider = removal_provider
        self.allocate_uid, self.rng, self.event_lifecycle = (
            allocate_uid,
            rng,
            event_lifecycle,
        )
        self.prepared = {}
        self.activated = set()

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                runner_modifier=runner,
                _nullable_target=True,
                _event_ids=tuple(sorted({0, *(effect["target_masks"][6] or ())})),
            )

    def prepare(self, effect, values, invocation):
        if effect["effect_class"] != 421:
            raise ValueError("Wrong native dispel preparation family")
        dispel_flags(effect, event_lifecycle=self.event_lifecycle)
        if self.event_lifecycle is None:
            return invocation
        if not callable(self.allocate_uid) or not callable(self.rng):
            raise ValueError("Missing actual fresh dispel runner allocation")
        if invocation.native_running_uid is not None:
            raise ValueError("Unaudited restored dispel source runner")
        runner = NativeRunnerAmount(self.allocate_uid(), 421, rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        self._phase(effect, invocation, runner, 1)
        # eXe inherits no-op eZR.C and Qe value mutation; its fresh amount stays zero.
        self.prepared[runner.uid] = runner
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.activated.discard(invocation.native_running_uid)

    def prepare_activation(self, effect, values, invocation, *, clone_uid):
        if effect["effect_class"] != 421 or invocation.native_running_uid is not None:
            raise ValueError("Invalid native dispel activation identity")
        dispel_flags(effect, event_lifecycle=self.event_lifecycle)
        if self.event_lifecycle is None or not callable(self.rng):
            raise ValueError("Missing native dispel activation lifecycle")
        runner = NativeRunnerAmount(clone_uid, 421, rng=self.rng)
        if clone_uid in self.prepared:
            raise ValueError("Duplicate native dispel clone identity")
        # Qe.k runs n(source), then dr([1,2]); inherited C leaves amount zero.
        invocation = replace(invocation, native_running_uid=clone_uid)
        self.prepared[clone_uid] = runner
        self.activated.add(clone_uid)
        return invocation

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 421:
            raise ValueError("Wrong native dispel family")
        dispel_flags(effect, event_lifecycle=self.event_lifecycle)
        native_definition_timing(effect, invocation.level)
        runner = self.prepared.pop(invocation.native_running_uid, None)
        activated = invocation.native_running_uid in self.activated
        self.activated.discard(invocation.native_running_uid)
        if self.event_lifecycle is not None and runner is None:
            raise ValueError("Missing actual prepared dispel runner")
        if runner is not None and not activated:
            self._phase(effect, invocation, runner, 2)
        self._apply(values, invocation)
        if runner is not None:
            runner.finish_application()
            self._phase(effect, invocation, runner, 3)
            self._phase(effect, invocation, runner, 4)
            notify_runner_value(invocation, runner.value)
        return True  # eXe.c calls mu(true) even when no retained effect matches.

    def _apply(self, values, invocation):
        if invocation.target_id is None:
            return  # Exact eXe.c null-PV early return, with mu(true) already set.
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
