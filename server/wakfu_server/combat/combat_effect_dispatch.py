"""Shared ordered effect dispatch over authoritative runtime callbacks.

Handlers execute effect classes, not class-specific spell IDs. The resolver
owns native targeting/critical/event eligibility; the condition context must
reflect mutations made by preceding effects. Call run_effect_transaction to
keep an unsupported later effect from committing earlier damage or states.
This does not claim that every native effect class has an implemented handler.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from time import perf_counter
from .combat_diagnostics import diagnostics_enabled, effect_step
from .combat_conditions import evaluate_condition
from .combat_definitions import effect_profile
from .combat_effect_groups import decode_group_mode, execute_ordered_group


class UnsupportedEffectExecution(ValueError):
    pass


@dataclass(frozen=True)
class EffectInvocation:
    reference: int
    level: int
    caster_id: int
    target_id: int | None
    cell: tuple[int, int, int]
    base_uid: int | None = (
        None  # Native fresh effect: base UID is its newly allocated UID.
    )
    state_uid: int | None = None
    native_context_hex: str | None = None
    native_trigger_context: dict | None = None
    native_running_uid: int | None = None


class EffectDispatcher:
    def __init__(
        self,
        effects,
        handlers,
        *,
        resolve,
        condition_context,
        probability_accepts,
        group_cells,
        actor_position,
        group_level=None,
        group_retention=None,
        prepare_effect=None,
        relative_group_children=None,
    ):
        self.effects = effects
        self.handlers = handlers
        self.resolve = resolve
        self.condition_context = condition_context
        self.probability_accepts = probability_accepts
        self.group_cells = group_cells
        self.actor_position = actor_position
        self.group_level = group_level
        self.group_retention = group_retention
        self.prepare_effect = prepare_effect
        self.relative_group_children = relative_group_children
        self._active_ancestors = ()
        self._active_activation = None

    def execute_activation(
        self, invocation, *, source, condition_context, executable, allocate_uid
    ):
        """Run one native Qe.k clone; targeting was already rebound by eZR.l/m."""
        if type(executable) is not bool:
            raise ValueError("Explicit native clone execution guard required")
        if not executable:
            return False
        previous = self._active_activation
        self._active_activation = (invocation, source, condition_context, allocate_uid)
        try:
            return self.execute(invocation)
        finally:
            self._active_activation = previous

    def execute(self, invocation, *, ancestors=None):
        if ancestors is None:
            ancestors = self._active_ancestors
        previous = self._active_ancestors
        self._active_ancestors = (*ancestors, invocation.reference)
        tracing = diagnostics_enabled()
        started = perf_counter() if tracing else None
        try:
            result = self._execute(invocation, ancestors=ancestors)
            if tracing:
                self._diagnose(invocation, status="completed" if result else "no_effect",
                               elapsed_ms=round((perf_counter() - started) * 1000, 3))
            return result
        except Exception as error:
            if tracing:
                self._diagnose(invocation, status="failed", reason=str(error),
                               exception_type=type(error).__name__,
                               elapsed_ms=round((perf_counter() - started) * 1000, 3))
            raise
        finally:
            self._active_ancestors = previous

    def _diagnose(self, invocation, **details):
        definition = self.effects.get(str(invocation.reference))
        effect_step(effect_reference=invocation.reference,
                    effect_class=None if definition is None else definition["effect_class"],
                    level=invocation.level, caster_id=invocation.caster_id,
                    target_id=invocation.target_id, cell=invocation.cell,
                    state_uid=invocation.state_uid, ancestors=self._active_ancestors,
                    **details)

    def _execute(self, invocation, *, ancestors):
        if invocation.reference in ancestors:
            raise UnsupportedEffectExecution("Recursive immediate effect tree")
        if len(ancestors) >= 128:
            raise UnsupportedEffectExecution("Effect recursion limit exceeded")
        effect = self.effects.get(str(invocation.reference))
        if effect is None:
            raise UnsupportedEffectExecution("Missing native effect definition")
        if not effect["minimum_level"] <= invocation.level <= effect["maximum_level"]:
            self._diagnose(invocation, status="skipped_level")
            return False
        values = effect_profile(effect, invocation.level)
        activation = (
            self._active_activation
            if self._active_activation is not None
            and self._active_activation[0] is invocation
            else None
        )
        # Resolving per effect also supplies native eligibility for critical
        # branches, event triggers and target overrides. Never default to all.
        success = False
        for selected in (
            (invocation,)
            if activation is not None
            else self.resolve(effect, invocation)
        ):
            if not isinstance(selected, EffectInvocation) or (
                selected.reference != invocation.reference
                or selected.level != invocation.level
            ):
                raise ValueError("Resolver changed effect identity or evaluation level")
            if (
                activation is None
                and self.group_retention is not None
                and self.group_retention.is_subscription(effect, selected)
            ):
                pending = self.group_retention.begin_group(effect, values, selected)
                if pending is None:
                    raise UnsupportedEffectExecution(
                        "Subscription has no verified retained lifetime"
                    )
                self.group_retention.finish_group(pending)
                self._diagnose(selected, status="subscribed_waiting_event")
                success = True
                continue  # Native Qe.d skips n()/criteria/probability until an event.
            if activation is None and self.prepare_effect is not None:
                selected = self.prepare_effect(effect, values, selected)
            condition = (
                activation[2](effect, selected, activation[1])
                if activation is not None
                else self.condition_context(selected)
            )
            if not evaluate_condition(effect["criteria"], condition):
                self._diagnose(selected, status="skipped_condition", criteria=effect["criteria"])
                continue
            accepted = (
                True
                if activation is None
                and self.group_retention is not None
                and self.group_retention.probability_bypassed(selected)
                else self.probability_accepts(values["probability"], selected)
            )
            if type(accepted) is not bool:
                raise ValueError(
                    "Probability evaluator must return an authoritative decision"
                )
            if not accepted:
                self._diagnose(selected, status="skipped_probability")
                continue
            if activation is not None:
                clone_uid = activation[3]()  # Qe.k allocates after i(source).
                if effect["effect_class"] == 400:
                    selected = replace(selected, native_running_uid=clone_uid)
            if effect["effect_class"] in (330, 844, 910, 912, 913, 999, 1020, 1047):
                pending_group = (
                    None
                    if activation is not None or self.group_retention is None
                    else self.group_retention.begin_group(effect, values, selected)
                )
                parameters = values["parameters"]
                child_level = selected.level
                if effect["effect_class"] in (844, 910, 912, 913, 999, 1020, 1047):
                    if not callable(self.group_level):
                        raise UnsupportedEffectExecution(
                            "Missing native dynamic group level context"
                        )
                    child_level = self.group_level(effect, values, selected)
                    if (
                        type(child_level) is not int
                        or not -32768 <= child_level <= 32767
                    ):
                        raise ValueError("Native child level must be signed short")

                mode = decode_group_mode(
                    parameters[:6]
                    if effect["effect_class"] in (844, 910, 912, 913, 999, 1020, 1047)
                    else parameters,
                    raw_target_parameter=effect["parameters"][4]
                    if len(parameters) >= 3
                    else None,
                )
                child_success = []
                children = effect["children"]
                relative = mode.relative_probability
                if relative:
                    if not callable(self.relative_group_children):
                        raise UnsupportedEffectExecution(
                            "Missing native relative group candidate authority"
                        )
                    children = tuple(
                        self.relative_group_children(
                            effect, values, selected, tuple(children)
                        )
                    )
                    if any(
                        type(child) is not int or child not in effect["children"]
                        for child in children
                    ):
                        raise ValueError(
                            "Relative authority changed native child identities"
                        )
                    mode = replace(mode, relative_probability=False)
                native_context_hex = (
                    None
                    if self.group_retention is None
                    else self.group_retention.child_context(
                        effect,
                        values,
                        selected,
                        event_activation=activation is not None,
                    ).hex()
                )
                if relative:
                    if native_context_hex is None:
                        raise UnsupportedEffectExecution(
                            "Native relative group requires eVt context"
                        )
                    # Protobuf last field wins: native eVt.a(true,false).
                    native_context_hex += "08011000"

                def execute_child(child):
                    result = self.execute(
                        replace(
                            selected,
                            reference=child.child_id,
                            level=child_level,
                            caster_id=child.caster_id,
                            target_id=child.target_id,
                            cell=child.cell,
                            native_context_hex=native_context_hex,
                            base_uid=None
                            if activation is not None
                            else selected.base_uid,
                        ),
                        ancestors=(*ancestors, invocation.reference),
                    )
                    child_success.append(result)
                    return result

                execute_ordered_group(
                    mode,
                    children,
                    caster_id=selected.caster_id,
                    target_id=selected.target_id,
                    target_cell=selected.cell,
                    execute_child=execute_child,
                    cell_targets=None
                    if mode.on_target
                    else self.group_cells(effect, selected),
                    caster_cell=self.actor_position(selected.caster_id),
                )
                if self.group_retention is not None:
                    self.group_retention.finish_group(pending_group)
                success = any(child_success) or success
            else:
                handler = self.handlers.get(effect["effect_class"])
                if handler is None:
                    raise UnsupportedEffectExecution(
                        f"No handler for native effect class {effect['effect_class']}"
                    )
                result = handler(effect, values, selected)
                if type(result) is not bool:
                    raise ValueError(
                        "Effect handler must report native application success"
                    )
                success = result or success
        return success


def run_effect_transaction(fight, invocations, dispatcher_factory):
    """Return a successful preview; caller commits and emits its packets.

    Factory callbacks must refer exclusively to the preview. Packet emission
    and other external mutations belong after successful transaction return.
    """
    preview = deepcopy(fight)
    dispatcher = dispatcher_factory(preview)
    with preview.effect_resolution():
        outcomes = tuple(dispatcher.execute(invocation) for invocation in invocations)
    return preview, outcomes
