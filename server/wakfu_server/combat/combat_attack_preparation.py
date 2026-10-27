"""Explicit Wakemu first-attack preparation policy, using a real damage Qe.

The original event-500 publisher is unavailable. Preparation's native reverse
subscription must run before damage L1 so its damage listener observes that
same attack. Its eYv consumer requires the actual triggering spell container.
"""
from contextlib import contextmanager
from contextvars import ContextVar


_scope = ContextVar("wakemu_attack_preparation", default=None)


@contextmanager
def attack_preparation_scope(fight, actor_id):
    token = _scope.set(dict(fight=fight, actor_id=actor_id, delivered=False))
    try:
        yield
    finally:
        _scope.reset(token)


def deliver_attack_preparation(
    lifecycle, effect, invocation, *, uid, final_modifier, runner_modifier
):
    scope = _scope.get()
    if scope is None:
        return False
    if (
        lifecycle.preview is not scope["fight"]
        or invocation.caster_id != scope["actor_id"]
        or invocation.state_uid is not None
        or invocation.native_trigger_context is not None
    ):
        return False
    from .combat_ordinary_authority import ordinary_container_type

    if ordinary_container_type(lifecycle.preview, lifecycle.plan, invocation) not in (
        11,
        12,
    ):
        return False
    scope.setdefault("source_uids", set()).add(uid)
    if scope["delivered"]:
        return False
    # Mark before replay: reactive children are not another primary attack.
    scope["delivered"] = True
    scope["source_uid"] = uid
    from .combat_ordinary_events import OrdinaryHealingEvents

    OrdinaryHealingEvents.phase(
        lifecycle,
        effect,
        invocation,
        uid=uid,
        value=0,
        channel=1,
        _event_ids=(500,),
        final_modifier=final_modifier,
        runner_modifier=runner_modifier,
    )
    return True


def note_preparation_modifier(fight, invocation):
    """Record only an actual faq mutation belonging to this primary attack."""
    scope = _scope.get()
    if (
        scope is None
        or scope["fight"] is not fight
        or not scope["delivered"]
        or invocation.state_uid is None
        or invocation.native_trigger_context is None
        or invocation.native_trigger_context.get("uid")
        not in scope.get("source_uids", {scope.get("source_uid")})
    ):
        return
    from .combat_native_container import resolve_state_container

    state = resolve_state_container(fight, invocation.state_uid)
    if state.target_id != scope["actor_id"]:
        return
    scope.setdefault("modifiers", {}).setdefault(invocation.state_uid, []).append(
        invocation
    )


def completed_attack_preparation(fight, actor_id):
    """Attest a settled real primary attack inside its still-owned cast scope."""
    scope = _scope.get()
    return (
        scope is not None
        and scope["fight"] is fight
        and scope["actor_id"] == actor_id
        and scope["delivered"] is True
        and scope.get("settled") is True
        and type(scope.get("source_uid")) is int
        and scope["source_uid"] > 0
    )


def _preparation_marker(effects, root, modifier_reference, state_reference):
    """Qualify the original next-attack modifier/marker/decurse recipe."""
    import re

    def descendants(reference, seen=None):
        seen = set() if seen is None else seen
        if reference in seen:
            return seen
        seen.add(reference)
        row = effects.get(str(reference))
        if row is None:
            raise ValueError("Incomplete attack preparation source closure")
        for child in row.get("children", ()):
            descendants(child, seen)
        return seen

    branches = [effects[str(child)] for child in root.get("children", ())]
    damage = [branch for branch in branches if 2 in (branch["target_masks"][0] or ())]
    cleanup = [
        branch for branch in branches if 1025 in (branch["target_masks"][5] or ())
    ]
    if len(damage) != 1 or len(cleanup) != 1:
        return None
    damage_ids = set()
    for child in damage[0].get("children", ()):
        damage_ids.update(descendants(child))
    if modifier_reference not in damage_ids:
        return None
    markers = set()
    for child in cleanup[0].get("children", ()):
        for reference in descendants(child):
            row = effects[str(reference)]
            if (
                row["effect_class"] != 321
                or row.get("parameters", [None])[0] != state_reference
            ):
                continue
            match = re.fullmatch(
                r'\s*HasEffectWithSpecificId\(\s*"caster"\s*,\s*(\d+)\s*\)\s*',
                row.get("criteria", ""),
            )
            if match:
                marker = int(match.group(1))
                if marker in damage_ids and effects[str(marker)]["effect_class"] == 400:
                    markers.add(marker)
    if len(markers) != 1:
        return None
    marker = next(iter(markers))

    def marker_path(reference, ancestors=()):
        if reference in ancestors:
            return None
        row = effects[str(reference)]
        if (
            row.get("probability_base", 100) != 100
            or row.get("probability_per_level", 0) != 0
        ):
            return None  # No policy-created substitute for a probabilistic branch.
        if reference == marker:
            return (reference,)
        for child in row.get("children", ()):
            path = marker_path(child, (*ancestors, reference))
            if path is not None:
                return (reference, *path)
        return None

    for child in damage[0].get("children", ()):
        path = marker_path(child)
        if path is not None:
            return marker, path
    return None


def settle_attack_preparation(dispatcher):
    """Wakemu policy: materialize the declared consumed marker on its carrier.

    Original 500 publication is unavailable. Native child PV transmission can
    put the deferred marker subscription on an attack recipient. After a real
    modifier application, complete that source recipe on its actual state
    carrier before the existing 1025 criterion/decurse path. No event is forged.
    """
    from dataclasses import replace
    from .combat_native_container import resolve_state_container

    scope = _scope.get()
    if (
        scope is None
        or scope.get("settled")
        or dispatcher.native_retention.fight is not scope["fight"]
    ):
        return
    scope["settled"] = True
    fight = scope["fight"]
    for state_uid, invocations in scope.get("modifiers", {}).items():
        owner = fight.actors[scope["actor_id"]]
        if not any(entry.uid == state_uid for entry in owner.state_ledger.entries):
            continue  # Native children already removed/replaced this carrier.
        state = resolve_state_container(fight, state_uid)
        if state.target_id != scope["actor_id"]:
            continue
        for invocation in invocations:
            for row in tuple(fight.native_owned_group_effects.values()):
                original = row.get("invocation", {})
                if original.get("state_uid") != state_uid:
                    continue
                root = dispatcher.effects[str(original["reference"])]
                if 500 not in (root["target_masks"][0] or ()):
                    continue
                recipe = _preparation_marker(
                    dispatcher.effects, root, invocation.reference, state.reference
                )
                if recipe is None:
                    continue
                marker, path = recipe
                selected = replace(
                    invocation,
                    reference=marker,
                    caster_id=state.target_id,
                    target_id=state.target_id,
                    cell=fight.actors[state.target_id].position,
                    base_uid=None,
                    native_running_uid=None,
                    native_context_hex=None,
                    native_value_scope=None,
                    native_explicit_target=True,
                )
                from .combat_conditions import evaluate_condition

                with dispatcher.native_retention.container_scope(selected):
                    if not all(
                        evaluate_condition(
                            dispatcher.effects[str(reference)].get("criteria", ""),
                            dispatcher.condition_context(
                                replace(selected, reference=reference)
                            ),
                        )
                        for reference in path
                    ):
                        continue
                    dispatcher.execute(selected)
                break
            else:
                continue
            break  # One consumed marker per carrier and complete attack.
