"""Shared ordered effect dispatch over authoritative runtime callbacks.

Handlers execute effect classes, not class-specific spell IDs. The resolver
owns native targeting/critical/event eligibility; the condition context must
reflect mutations made by preceding effects. Call run_effect_transaction to
keep an unsupported later effect from committing earlier damage or states.
This does not claim that every native effect class has an implemented handler.
"""
from copy import deepcopy
from contextvars import ContextVar
from contextlib import nullcontext
from dataclasses import dataclass, replace
from time import perf_counter
from .combat_diagnostics import diagnostics_enabled, effect_step
from .combat_conditions import evaluate_condition
from .combat_definitions import effect_profile
from .combat_effect_groups import decode_group_mode, execute_ordered_group


_TRIGGER_DEPTH = ContextVar("native_trigger_clone_depth", default=0)


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
    native_cast_boundary_context: dict | None = (
        None  # Explicit server cast policy; never a Qe.
    )
    native_turn_boundary_context: dict | None = None  # Owned turn policy, never a Qe.
    native_movement_boundary_context: dict | None = None  # Committed step, never a Qe.
    native_running_uid: int | None = None
    native_value_scope: object | None = (
        None  # Ephemeral identity of the PS/eVt observer.
    )
    native_retained_container: dict | None = (
        None  # Explicit PN/PL of synthetic owned applicators.
    )
    native_explicit_target: bool = False  # Native PK.a received a non-null PV argument.
    wakemu_fresh_child_selection: bool = False
    wakemu_rebound_child_selection: bool = (
        False  # Fresh server swap, never native replay.
    )
    native_preselected_target: bool = False  # Qe.g(PV), bypassing area and aZX.
    native_target_cell_argument: bool = (
        False  # Criterion received raw aBn, not selected PV.
    )


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
        random_group_children=None,
        pt_preflight=None,
        transfer_probability=None,
        transfer_skip_second=None,
        random_child_level=None,
        multiple_group_candidates=None,
        group_random=None,
        distance_group_runner=None,
        group_execution_scope=None,
        resolved_population_scope=None,
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
        self.random_group_children = random_group_children
        self.pt_preflight = pt_preflight
        self.transfer_probability = transfer_probability
        self.transfer_skip_second = transfer_skip_second
        self.random_child_level = random_child_level
        self.multiple_group_candidates = multiple_group_candidates
        self.group_random = group_random
        self.distance_group_runner = distance_group_runner
        self.group_execution_scope = group_execution_scope
        self.resolved_population_scope = resolved_population_scope
        self._active_pt = None
        self._active_ancestors = ()
        self._active_execution_keys = ()
        self._active_activation = None
        self._prepared_scopes = []

    def execute_activation(
        self, invocation, *, source, condition_context, executable, allocate_uid
    ):
        """Run one native Qe.k clone; targeting was already rebound by eZR.l/m."""
        if type(executable) is not bool:
            raise ValueError("Explicit native clone execution guard required")
        if not executable:
            return False
        depth = _TRIGGER_DEPTH.get()
        if depth >= 128:
            raise UnsupportedEffectExecution("Native trigger activation depth exceeded")
        token = _TRIGGER_DEPTH.set(depth + 1)
        previous = self._active_activation
        previous_ancestors = self._active_ancestors
        previous_keys = self._active_execution_keys
        self._active_activation = (invocation, source, condition_context, allocate_uid)
        # Qe.k creates a fresh runner tree after the shared Qj triple guard.
        # A different resolved caster/target may legally activate the same PK;
        # its children still enforce immediate-tree recursion independently.
        self._active_ancestors = ()
        self._active_execution_keys = ()
        try:
            return self.execute(invocation)
        finally:
            self._active_activation = previous
            self._active_ancestors = previous_ancestors
            self._active_execution_keys = previous_keys
            _TRIGGER_DEPTH.reset(token)

    def execute(self, invocation, *, ancestors=None, _pt_report=None):
        if ancestors is None:
            ancestors = self._active_ancestors
        previous_pt = self._active_pt
        self._active_pt = _pt_report
        previous = self._active_ancestors
        previous_keys = self._active_execution_keys
        self._active_execution_keys = (
            *previous_keys,
            (invocation.reference, invocation.state_uid),
        )
        self._active_ancestors = (*ancestors, invocation.reference)
        prepared = []
        self._prepared_scopes.append(prepared)
        tracing = diagnostics_enabled()
        started = perf_counter() if tracing else None
        try:
            result = self._execute(invocation, ancestors=ancestors)
            if tracing:
                self._diagnose(
                    invocation,
                    status="completed" if result else "no_effect",
                    elapsed_ms=round((perf_counter() - started) * 1000, 3),
                )
            return result
        except Exception as error:
            if tracing:
                self._diagnose(
                    invocation,
                    status="failed",
                    reason=str(error),
                    exception_type=type(error).__name__,
                    native_displacement_actor=getattr(
                        error, "native_displacement_actor", None
                    ),
                    elapsed_ms=round((perf_counter() - started) * 1000, 3),
                )
            raise
        finally:
            try:
                for effect, selected in reversed(prepared):
                    handler = self.handlers.get(effect["effect_class"])
                    cancel = getattr(handler, "cancel_prepared", None)
                    if callable(cancel):
                        cancel(selected)
            finally:
                self._prepared_scopes.pop()
                self._active_ancestors = previous
                self._active_execution_keys = previous_keys
                self._active_pt = previous_pt

    def _recursive_identity(self, invocation, ancestors):
        # eWu may replace an additive carrier before executing its children.
        # Distinct eZk UIDs form distinct instances even when a child reference
        # repeats. Native capped-state policy terminates bounded replacement;
        # the global ancestor-depth limit still bounds an unending UID chain.
        key = (invocation.reference, invocation.state_uid)
        return key in self._active_execution_keys[:-1] or (
            invocation.state_uid is None and invocation.reference in ancestors
        )

    def register_subscription(self, invocation):
        """Register a fresh listener without treating it as recursive execution.

        Qe.d defers n()/criteria/children for Qa.aZN. Reapplying a state while
        one of its old listeners runs can register the same PK on the new
        carrier. This is not an immediate recursive effect tree. Validate the
        deferred branch explicitly; normal execute retains its recursion guard.
        """
        effect = self.effects.get(str(invocation.reference))
        if (
            effect is None
            or self.group_retention is None
            or not self.group_retention.is_subscription(effect, invocation)
        ):
            raise UnsupportedEffectExecution(
                "State subscription registration requires native event masks"
            )
        return self.execute(invocation, ancestors=())

    def execute_pt(
        self, invocation, *, ancestors=None, fresh_relationship_policy=False
    ):
        from .combat_repeated_group import NativePtResult

        if type(fresh_relationship_policy) is not bool:
            raise ValueError("Explicit PT relationship policy required")
        # Native PT binds its supplied PV. Only the explicitly opted-in eYC
        # server reconstruction applies fresh relationship selectors instead.
        invocation = replace(
            invocation,
            wakemu_fresh_child_selection=fresh_relationship_policy,
            wakemu_rebound_child_selection=False,
        )

        if not callable(self.pt_preflight):
            raise UnsupportedEffectExecution("Missing native PT allocation preflight")
        effect = self.effects.get(str(invocation.reference))
        if effect is None:
            raise UnsupportedEffectExecution("Missing native PT effect definition")
        present = self.pt_preflight(effect, invocation)
        if type(present) is not bool:
            raise ValueError("Explicit native PT allocation decision required")
        if not present:
            return NativePtResult(False, 0, False)
        report = {"accepted_count": 0}
        applied = self.execute(invocation, ancestors=ancestors, _pt_report=report)
        return NativePtResult(True, report["accepted_count"], applied)

    def _diagnose(self, invocation, **details):
        definition = self.effects.get(str(invocation.reference))
        effect_step(
            effect_reference=invocation.reference,
            effect_class=None if definition is None else definition["effect_class"],
            level=invocation.level,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            cell=invocation.cell,
            state_uid=invocation.state_uid,
            ancestors=self._active_ancestors,
            **details,
        )

    def _execute(self, invocation, *, ancestors):
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
        population = tuple(
            (invocation,)
            if activation is not None
            else self.resolve(effect, invocation)
        )
        # Native selection holds actual PV pointers for the complete traversal,
        # including later recipients unregistered by an earlier selected runner.
        scope = (
            self.resolved_population_scope(population)
            if self.resolved_population_scope is not None
            else nullcontext()
        )
        with scope:
            return self._execute_resolved(
                invocation,
                ancestors=ancestors,
                effect=effect,
                values=values,
                activation=activation,
                population=population,
            )

    def _execute_resolved(
        self, invocation, *, ancestors, effect, values, activation, population
    ):
        success = False
        for selected in population:
            if not isinstance(selected, EffectInvocation) or (
                selected.reference != invocation.reference
                or selected.level != invocation.level
            ):
                raise ValueError("Resolver changed effect identity or evaluation level")
            if selected.native_preselected_target:
                # g(PV) binds this runner once. Its newly allocated children
                # still execute their own native target-selection contracts.
                selected = replace(selected, native_preselected_target=False)
            if (
                activation is None
                and self.group_retention is not None
                and self.group_retention.is_subscription(effect, selected)
            ):
                if self._recursive_identity(invocation, ancestors):
                    raise UnsupportedEffectExecution("Recursive immediate effect tree")
                pending = self.group_retention.begin_group(effect, values, selected)
                if pending is None:
                    raise UnsupportedEffectExecution(
                        "Subscription has no verified retained lifetime"
                    )
                self.group_retention.finish_group(pending)
                self._diagnose(selected, status="subscribed_waiting_event")
                success = True
                continue  # Native Qe.d skips n()/criteria/probability until an event.
            handler = self.handlers.get(effect["effect_class"])
            native_eligibility = getattr(handler, "native_eligibility", None)
            if callable(native_eligibility) and not native_eligibility(
                effect, selected
            ):
                self._diagnose(selected, status="skipped_native_eligibility")
                continue
            if activation is None and self.prepare_effect is not None:
                selected = self.prepare_effect(effect, values, selected)
                if self._prepared_scopes:
                    self._prepared_scopes[-1].append((effect, selected))
            candidate_filter = False
            if effect["effect_class"] == 345:
                from .combat_multiple_target_group import multiple_target_spec

                candidate_filter = multiple_target_spec(values)[1]
            elif effect["effect_class"] == 349:
                from .combat_cell_group import cell_group_mode

                candidate_filter = cell_group_mode(values).filter_cells
            condition = (
                None
                if candidate_filter
                else (
                    activation[2](effect, selected, activation[1])
                    if activation is not None
                    else self.condition_context(selected)
                )
            )
            if not candidate_filter and not evaluate_condition(
                effect["criteria"], condition
            ):
                self._diagnose(
                    selected, status="skipped_condition", criteria=effect["criteria"]
                )
                continue
            # Native state clamps may reapply their carrier and revisit the
            # same conditional root with an already bounded value. That is a
            # terminating no-op, not an executable cycle. Keep the cycle guard
            # after native eligibility/criteria and before probability or any
            # handler execution; unconditional recursive trees still fail.
            if self._recursive_identity(invocation, ancestors):
                raise UnsupportedEffectExecution("Recursive immediate effect tree")
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
                prepare_activation = getattr(handler, "prepare_activation", None)
                if callable(prepare_activation):
                    selected = prepare_activation(
                        effect, values, selected, clone_uid=clone_uid
                    )
                    if self._prepared_scopes:
                        self._prepared_scopes[-1].append((effect, selected))
                elif effect["effect_class"] in (400, 933, 1000, 1001, 1080):
                    selected = replace(selected, native_running_uid=clone_uid)
            if effect["effect_class"] == 865:
                from .combat_value_transfer_runtime import execute_runtime_transfer

                pending_group = (
                    None
                    if activation is not None or self.group_retention is None
                    else self.group_retention.begin_group(effect, values, selected)
                )
                result = execute_runtime_transfer(
                    self,
                    effect,
                    values,
                    selected,
                    ancestors=(*ancestors, invocation.reference),
                )
                if self.group_retention is not None:
                    self.group_retention.finish_group(pending_group)
                success = result or success
            elif effect["effect_class"] in (1076, 1080):
                distance_family = effect["effect_class"] == 1080
                if (
                    self.group_retention is None
                    or (not distance_family and not callable(self.random_child_level))
                    or (distance_family and self.distance_group_runner is None)
                ):
                    raise UnsupportedEffectExecution(
                        "Native eWd requires owned calculation and eVt authority"
                    )
                if distance_family:
                    selected, override = self.distance_group_runner.start(
                        effect,
                        values,
                        selected,
                        event_activation=activation is not None,
                    )
                else:
                    override = self.random_child_level(values["parameters"])
                try:
                    pending_group = (
                        None
                        if activation is not None
                        else self.group_retention.begin_group(
                            effect, values, selected, initial_value=override
                        )
                    )
                    (
                        child_level,
                        child_context,
                    ) = self.group_retention.child_level_context(
                        effect,
                        values,
                        selected,
                        default_level=selected.level,
                        event_activation=activation is not None,
                        native_override=override,
                    )
                    applied = False
                    # eWd passes the same actual bfs PV and bft cell to every child;
                    # it does not expand the parent's area or force an actor target.
                    for reference in effect["children"]:
                        result = self.execute(
                            replace(
                                selected,
                                reference=reference,
                                level=child_level,
                                native_context_hex=child_context.hex(),
                                native_value_scope=None,
                                native_explicit_target=False,
                                native_running_uid=None
                                if distance_family
                                else selected.native_running_uid,
                                base_uid=None
                                if activation is not None
                                else selected.base_uid,
                            ),
                            ancestors=(*ancestors, invocation.reference),
                        )
                        applied = result or applied
                    self.group_retention.finish_group(pending_group)
                    if distance_family:
                        self.distance_group_runner.finish(effect, selected)
                    success = applied or success
                finally:
                    if distance_family:
                        self.distance_group_runner.cancel_prepared(selected)
            elif effect["effect_class"] == 349:
                from .combat_cell_group import (
                    select_cell_group,
                    native_cell_criterion_presence,
                )

                if self.group_retention is None:
                    raise UnsupportedEffectExecution(
                        "Missing native eYk retained context authority"
                    )
                pending_group = (
                    None
                    if activation is not None
                    else self.group_retention.begin_group(effect, values, selected)
                )

                def cell_condition(cell):
                    candidate = replace(
                        selected,
                        target_id=None,
                        cell=cell,
                        native_explicit_target=False,
                        native_target_cell_argument=True,
                    )
                    context = (
                        activation[2](effect, candidate, activation[1])
                        if activation is not None
                        else self.condition_context(candidate)
                    )
                    return evaluate_condition(effect["criteria"], context)

                selection = select_cell_group(
                    values,
                    self.group_cells(effect, selected),
                    caster_position=self.actor_position(selected.caster_id),
                    condition=cell_condition,
                    rng=self.group_random,
                    criterion_present=native_cell_criterion_presence(effect, selected),
                )
                if selection.eligible_count:
                    child_level, context = self.group_retention.child_level_context(
                        effect,
                        values,
                        selected,
                        default_level=selected.level,
                        event_activation=activation is not None,
                    )
                applied = False
                # eYk orders cells first, then the native fyD child iterator.
                # The PK.a call always receives null PV; children select anew.
                for cell in selection.cells:
                    for reference in effect["children"]:
                        result = self.execute(
                            replace(
                                selected,
                                reference=reference,
                                level=child_level,
                                target_id=None,
                                cell=cell,
                                native_context_hex=context.hex(),
                                native_value_scope=None,
                                native_running_uid=None,
                                native_explicit_target=False,
                                base_uid=None
                                if activation is not None
                                else selected.base_uid,
                            ),
                            ancestors=(*ancestors, invocation.reference),
                        )
                        applied = result or applied
                # Empty eligible population invokes fRS: Qf ownership survives
                # while the runner's own PR notification is suppressed.
                self.group_retention.finish_group(
                    pending_group, notify=selection.eligible_count > 0
                )
                success = applied or success
            elif effect["effect_class"] == 345:
                from .combat_multiple_target_group import select_multiple_targets

                if self.group_retention is None or not callable(
                    self.multiple_group_candidates
                ):
                    raise UnsupportedEffectExecution(
                        "Missing native eYC target/context authority"
                    )
                pending_group = (
                    None
                    if activation is not None
                    else self.group_retention.begin_group(effect, values, selected)
                )

                def candidate_condition(candidate):
                    context = (
                        activation[2](effect, candidate, activation[1])
                        if activation is not None
                        else self.condition_context(candidate)
                    )
                    return evaluate_condition(effect["criteria"], context)

                targets = select_multiple_targets(
                    values,
                    self.multiple_group_candidates(effect, selected),
                    caster_position=self.actor_position(selected.caster_id),
                    position=self.actor_position,
                    condition=candidate_condition,
                    rng=self.group_random,
                )
                applied = False
                target_scope = (
                    self.resolved_population_scope(targets)
                    if self.resolved_population_scope is not None
                    else nullcontext()
                )
                with target_scope:
                    for target in targets:
                        child_level, context = self.group_retention.child_level_context(
                            effect,
                            values,
                            selected,
                            default_level=selected.level,
                            event_activation=activation is not None,
                        )
                        for reference in effect["children"]:
                            child = replace(
                                selected,
                                reference=reference,
                                level=child_level,
                                target_id=target.target_id,
                                cell=self.actor_position(target.target_id),
                                native_context_hex=context.hex(),
                                native_value_scope=None,
                                native_running_uid=None,
                                native_explicit_target=True,
                                # Wakemu reconstructs fresh child relationship
                                # selectors independently of the transmitted PV.
                                wakemu_fresh_child_selection=True,
                                base_uid=None
                                if activation is not None
                                else selected.base_uid,
                            )
                            applied = (
                                self.execute_pt(
                                    child,
                                    ancestors=(*ancestors, invocation.reference),
                                    fresh_relationship_policy=True,
                                ).applied
                                or applied
                            )
                self.group_retention.finish_group(pending_group, notify=False)
                success = applied or success
            elif effect["effect_class"] == 949:
                from .combat_repeated_group import (
                    repeat_specification,
                    execute_repeated_group,
                )

                if self.group_retention is None:
                    raise UnsupportedEffectExecution(
                        "Native949 requires eZM context authority"
                    )
                pending_group = (
                    None
                    if activation is not None
                    else self.group_retention.begin_group(effect, values, selected)
                )
                child_level, child_context = self.group_retention.child_level_context(
                    effect,
                    values,
                    selected,
                    default_level=selected.level,
                    event_activation=activation is not None,
                )

                def execute_repeated_child(reference):
                    return self.execute_pt(
                        replace(
                            selected,
                            reference=reference,
                            level=child_level,
                            target_id=None,
                            native_context_hex=child_context.hex(),
                            native_value_scope=None,
                            native_explicit_target=False,
                            base_uid=None
                            if activation is not None
                            else selected.base_uid,
                        ),
                        ancestors=(*ancestors, invocation.reference),
                    )

                applied, _ = execute_repeated_group(
                    repeat_specification(effect, values),
                    effect["children"],
                    execute_repeated_child,
                )
                self.group_retention.finish_group(pending_group)
                success = applied or success
            elif effect["effect_class"] in (
                330,
                341,
                352,
                844,
                910,
                912,
                913,
                999,
                1020,
                1047,
                1103,
            ):
                if effect["effect_class"] == 1103 and self.group_retention is None:
                    raise UnsupportedEffectExecution(
                        "Native1103 requires authoritative triggering-value eVt context"
                    )
                symmetry_cells = None
                if effect["effect_class"] == 352:
                    symmetry_cells = tuple(self.group_cells(effect, selected))
                    if not symmetry_cells:
                        continue  # eYA.bbH requires a valid transformed center.
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

                if effect["effect_class"] == 352:
                    from .combat_effect_groups import EffectGroupMode

                    mode = EffectGroupMode(on_target=False)
                elif effect["effect_class"] == 341:
                    from .combat_random_group import random_group_mode

                    mode = random_group_mode(effect, values)
                else:
                    mode = decode_group_mode(
                        parameters[:6]
                        if effect["effect_class"]
                        in (844, 910, 912, 913, 999, 1020, 1047, 1103)
                        else parameters,
                        raw_target_parameter=effect["parameters"][4]
                        if len(parameters) >= 3
                        else None,
                    )
                child_success = []
                children = effect["children"]
                relative = mode.relative_probability
                if effect["effect_class"] == 341:
                    if not callable(self.random_group_children):
                        raise UnsupportedEffectExecution(
                            "Missing native eXR lottery authority"
                        )
                    children = tuple(
                        self.random_group_children(
                            effect, values, selected, tuple(children)
                        )
                    )
                    if any(
                        type(child) is not int or child not in effect["children"]
                        for child in children
                    ):
                        raise ValueError(
                            "eXR authority changed native child identities"
                        )
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
                native_context_hex = None
                if self.group_retention is not None:
                    (
                        child_level,
                        native_context,
                    ) = self.group_retention.child_level_context(
                        effect,
                        values,
                        selected,
                        default_level=child_level,
                        event_activation=activation is not None,
                    )
                    native_context_hex = native_context.hex()
                elif 16 in effect.get("native_effect_flags", ()):
                    raise UnsupportedEffectExecution(
                        "Native flag16 requires authoritative container/context level"
                    )
                if relative or effect["effect_class"] == 341:
                    if native_context_hex is None:
                        raise UnsupportedEffectExecution(
                            "Native relative group requires eVt context"
                        )
                    # Native eVt.a(true,false) changes fields in its builder.
                    from .combat_random_group import probability_bypass_context

                    native_context_hex = probability_bypass_context(
                        bytes.fromhex(native_context_hex)
                    ).hex()

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
                            native_value_scope=None,
                            # eYg.a passes bfs as the explicit PV only on its
                            # actor branch with rFn (target transmission). Keep
                            # that client contract distinct from the server's
                            # fresh relationship-selector policy below.
                            native_explicit_target=(
                                mode.on_target and mode.transmit_target
                            ),
                            wakemu_fresh_child_selection=True,
                            wakemu_rebound_child_selection=(
                                activation is None
                                and mode.actor_rebind == 2
                                and selected.target_id is not None
                                and selected.caster_id is not None
                            ),
                            base_uid=None
                            if activation is not None
                            else selected.base_uid,
                        ),
                        ancestors=(*ancestors, invocation.reference),
                    )
                    child_success.append(result)
                    return result

                scope = (
                    self.group_execution_scope(selected)
                    if self.group_execution_scope is not None
                    else nullcontext()
                )
                with scope:
                    execute_ordered_group(
                        mode,
                        children,
                        caster_id=selected.caster_id,
                        target_id=selected.target_id,
                        # eYg.a actor branch passes bfs.bcz/bcA/bcB, not the
                        # original cast anchor. Cell branch preserves its anchor.
                        target_cell=(
                            self.actor_position(selected.target_id)
                            if mode.on_target and selected.target_id is not None
                            else selected.cell
                        ),
                        execute_child=execute_child,
                        cell_targets=None
                        if mode.on_target
                        else symmetry_cells
                        if symmetry_cells is not None
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
            # Qe.a(Qe,boolean) calls PT.bap after c(), independently of whether
            # c() changed anything. Deferred subscription path continued above.
            if self._active_pt is not None:
                self._active_pt["accepted_count"] += 1
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
