"""Pure state replacement decisions matching native eWu.fMY.

Each existing instance supplies its own fyW flags. The client iterates all
instances of the same state, regardless of caster. Removal is committed only
after the complete decision succeeds; a later rejection cancels earlier ones.
guN prevents replacement of nonadditive states; guV allows additive refresh
at the maximum. Duration and effect execution belong to the state runtime.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ExistingState:
    level: int
    maximum_level: int
    additive: bool
    replace: bool
    refresh: bool
    protected: bool


@dataclass(frozen=True)
class StateApplication:
    accepted: bool
    level: int
    remove_indices: tuple[int, ...]


def existing_state_from_definition(definition, level):
    """Build an instance policy from the native exported definition.

    Missing flags raise KeyError rather than silently adopting a default.
    The running instance's actual level must be supplied by the state ledger.
    """
    return ExistingState(
        level=level,
        maximum_level=definition["maximum_level"],
        additive=definition["additive"],
        replace=definition["replace"],
        refresh=definition["refresh"],
        protected=definition["protected"],
    )


def plan_state_application(requested_level, maximum_level, existing):
    """Plan one state ID's application without mutating its collection.

    The caller must filter existing instances to the requested state ID and
    preserve their native iteration order. Levels use Java signed short addition."""
    if (
        type(requested_level) is not int
        or not -32768 <= requested_level <= 32767
        or type(maximum_level) is not int
        or not 0 <= maximum_level <= 32767
    ):
        raise ValueError("Invalid requested state level or maximum")
    level, removals = requested_level, []
    for index, old in enumerate(existing):
        if not isinstance(old, ExistingState):
            raise ValueError("Authoritative state flags required")
        if any(
            type(n) is not int or not -32768 <= n <= 32767
            for n in (old.level, old.maximum_level)
        ):
            raise ValueError("Invalid native existing state level")
        if any(
            type(flag) is not bool
            for flag in (old.additive, old.replace, old.refresh, old.protected)
        ):
            raise ValueError("Invalid native state policy")
        if old.protected and not old.additive:
            return StateApplication(False, requested_level, ())
        if old.additive and (old.level < old.maximum_level or old.refresh):
            level = (level + old.level + 32768) % 65536 - 32768
            removals.append(index)
        elif old.replace and level >= old.level:
            removals.append(index)
        else:
            return StateApplication(False, requested_level, ())
    return StateApplication(True, min(level, maximum_level), tuple(removals))
