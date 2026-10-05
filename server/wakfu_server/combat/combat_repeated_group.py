"""eXL949 -> eXN -> eZM repeated groups, with typed native PT accounting."""
from dataclasses import dataclass


@dataclass(frozen=True)
class NativePtResult:
    present: bool
    accepted_count: int
    applied: bool

    def __post_init__(self):
        if type(self.present) is not bool or type(self.applied) is not bool:
            raise ValueError("Explicit native PT presence/result required")
        if type(self.accepted_count) is not int or self.accepted_count < 0:
            raise ValueError("Invalid native PT.bas count")
        if not self.present and (self.accepted_count or self.applied):
            raise ValueError("Null native PT cannot contain executions")


@dataclass(frozen=True)
class RepeatSpecification:
    count: int
    stop_on_empty_pt: bool


def repeat_specification(effect, values):
    if effect.get("effect_class") != 949:
        raise ValueError("Native repeat specification requires eXL949")
    parameters = values["parameters"]
    count = parameters[0] if parameters else 0
    if type(count) is not int:
        raise ValueError("Native repeat count must be int")
    stop = len(parameters) >= 2 and parameters[1] == 1
    return RepeatSpecification(min(12, count), stop)


def execute_repeated_group(specification, children, execute_child):
    """Reevaluate every child each iteration; nullPT is NOT a failed child.

    eZM.l resets its counters for each iteration. H stops only after the entire
    iteration if a nonnull PT had bas()==0. Handler booleans are not PT counts.
    """
    if not isinstance(specification, RepeatSpecification):
        raise ValueError("Native repetition specification required")
    iterations = []
    applied = False
    for _ in range(specification.count):
        created = accepted = empty = 0
        for reference in children:
            result = execute_child(reference)
            if not isinstance(result, NativePtResult):
                raise ValueError("Native repetition requires typed PT result")
            if result.present:
                created += 1
                accepted += result.accepted_count
                empty += result.accepted_count == 0
            applied = applied or result.applied
        iterations.append(dict(created=created, accepted=accepted, empty=empty))
        if specification.stop_on_empty_pt and empty:
            break
    return applied, tuple(iterations)
