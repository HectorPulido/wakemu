"""Native eWG dependency and live-invocation proof, without executing a runner.

A spellbook is not evidence that its spells execute. Dependency witnesses must
still pass the normal complete graph capability walk before equipment admission.
No actor, UID, effect payload or temporary book is created by this module.
"""
from collections.abc import Mapping


class UnknownMorphDependency(ValueError):
    """Original profile exists, but its complete execution domain is unproven."""


def book_domain(parsed, *, profiles=None):
    """Describe every future book, preserving native order, duplicates and caps.

    Own-level books span the full signed-short actor-level domain. A slot is
    exactly min(actor level, original maximum), so endpoints plus its cap are a
    complete piecewise-function witness, not a sampled current actor snapshot.
    """
    from .combat_morph_spellbook import native_morph_profiles, build_morph_book

    profiles = native_morph_profiles() if profiles is None else profiles
    entry = profiles.get(str(parsed["profile_id"]))
    if not isinstance(entry, Mapping):
        raise UnknownMorphDependency("Missing original morph profile dependency")
    low, high = (
        (-32768, 32767)
        if parsed["own_level"]
        else (entry["minimum_level"], entry["minimum_level"])
    )
    first = build_morph_book(entry, low)
    last = build_morph_book(entry, high)
    if tuple(first) != tuple(last):
        raise UnknownMorphDependency("Native morph book identity varies by level")
    maxima = {}
    for row in entry["abilities"]:
        maxima.setdefault(row["reference"], row["maximum_level"])
    return tuple(
        dict(
            reference=reference,
            casting_uid=reference,
            level_domain=(min(low, maxima[reference]), min(high, maxima[reference])),
            maximum_level=maxima[reference],
        )
        for reference in first
    )


def dependency_witnesses(parsed):
    """Return exact original spell-root/level witnesses for the complete book.

    Current original equipment profiles use their native minimum-level books.
    Positive/dynamic levels require a separate full casting-domain source; a
    level-zero document must never stand in for that missing authority.
    """
    from .combat_morph_dependencies import effect_catalog, zero_catalog

    slots = book_domain(parsed)
    source = effect_catalog()
    zeros = zero_catalog()
    if zeros is None:
        raise UnknownMorphDependency(
            "Missing original morph zero-level casting authority"
        )
    witnesses = []
    for slot in slots:
        if slot["level_domain"] != (0, 0):
            raise UnknownMorphDependency(
                "Morph positive-level casting domain requires complete authority"
            )
        reference = slot["reference"]
        row = zeros["spells"].get(str(reference))
        casting = zeros["casting"].get(str(reference))
        if (
            not isinstance(row, (tuple, list))
            or len(row) != 3
            or not isinstance(row[2], (tuple, list))
            or not isinstance(casting, Mapping)
        ):
            raise UnknownMorphDependency(
                "Missing exact native morph spell/casting definition"
            )
        for root in row[2]:
            if type(root) is not int or str(root) not in source["effects"]:
                raise UnknownMorphDependency(
                    "Incomplete native morph root dependency closure"
                )
            witnesses.append((root, 0))
    return tuple(dict.fromkeys(witnesses))


def preflight(factory, retained_container, parsed):
    """Attest production retention wiring and actual available dependency rows.

    This does not approve the returned spell graphs or hypothetical forced-value
    contexts. Callers must separately walk dependency_witnesses and prove that
    source ancestry cannot replace the profile through native eVt fields6/9.
    """
    from .combat_equipment_retained_lifecycle import (
        preflight as retained_preflight,
        _native_factory,
    )
    from .combat_morph_dependencies import effect_catalog

    if not retained_preflight(factory, retained_container):
        return False
    runtime = _native_factory(factory)
    try:
        dependency_witnesses(parsed)
        source = effect_catalog()
    except (ValueError, KeyError, TypeError):
        return False
    # Compare original semantic fields, allowing only additive compiler metadata.
    # Do not merge absent rows here: source completeness must precede pinning.
    for reference, expected in source["effects"].items():
        actual = runtime.effects.get(reference)
        if not isinstance(actual, Mapping):
            return False
        for key, value in expected.items():
            if key not in actual or _plain(actual[key]) != _plain(value):
                return False
    states = runtime.state_catalog["states"]
    return all(
        str(reference) in states for reference in source["state_reference_closure"]
    )


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def verify_invocation(dispatcher, effect, invocation, context, parsed):
    """Check actual registered actor, native context value and inverse ownership.

    Called after native stat-context resolution, before executing the morph.
    It never invokes arbitrary callbacks or treats a prepared profile as the
    actual context-overridden value. Event amount modifiers require a separate
    complete value-domain proof and remain rejected here.
    """
    from .combat_morph_handler import NativeMorphHandler
    from .combat_stat_handler import NativeStatHandler, StatExecutionContext
    from .combat_retained_runtime import NativeRetainedRuntime
    from .combat_morph_spellbook import native_morph_profiles, build_morph_book
    from .combat_value_transfer import apply_context_value

    if not isinstance(effect, Mapping) or effect.get("effect_class") != 933:
        return False
    handlers = getattr(dispatcher, "handlers", {})
    wrapper = handlers.get(933)
    handler = getattr(wrapper, "native_wrapped_handler", None)
    retention = getattr(dispatcher, "native_retention", None)
    inverse = getattr(handlers.get(400), "native_wrapped_handler", None)
    if (
        type(handler) is not NativeMorphHandler
        or type(retention) is not NativeRetainedRuntime
        or getattr(wrapper, "native_retention_owner", None) is not retention
        or handler.fight is not retention.fight
        or type(inverse) is not NativeStatHandler
        or inverse.fight is not handler.fight
    ):
        return False
    if (
        type(context) is not StatExecutionContext
        or context.source_guards_verified is not True
        or type(context.executable) is not bool
        or type(context.retained) is not bool
    ):
        return False
    masks = effect.get("target_masks")
    if (
        not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or any(masks[index] for index in (0, 1, 3, 4, 5, 6))
    ):
        return False
    actor = handler.fight.actors.get(invocation.target_id)
    if actor is None:
        return False
    try:
        payload = (
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex)
        )
        applied = apply_context_value(parsed["calculated_value"], payload)
        if ((applied + 32768) % 65536) - 32768 != parsed["profile_id"]:
            return False
        profile = native_morph_profiles()[str(parsed["profile_id"])]
        level = (
            actor.effective_level if parsed["own_level"] else profile["minimum_level"]
        )
        build_morph_book(profile, level)
    except (ValueError, KeyError, TypeError):
        return False
    return True
