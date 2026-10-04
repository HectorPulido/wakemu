"""eXL949/eXN/eZM repeated children with native PT-result distinction.

PT null is not failure: eZM counts failures only for created PT.bas()==0.
No bool-to-PT guess is allowed. Children execute in native order at parent cell,
without forcing the parent's actor target (eXL.bbA=false,bbB=true).
"""
from dataclasses import dataclass, replace
from .combat_parameters import parameter_value


@dataclass(frozen=True)
class RepeatChildOutcome:
    pt_created: bool
    applications: int | None


def repeat_parameters(effect, level):
    if effect["effect_class"] != 949 or len(effect["parameters"]) not in (2, 4):
        raise ValueError("Unsupported native eXL repeat variant")
    count = min(12, parameter_value(effect["parameters"], 0, level))
    stop = (
        len(effect["parameters"]) >= 4
        and parameter_value(effect["parameters"], 1, level) == 1
    )
    return count, stop


def execute_repeated_group(effect, invocation, *, execute_child):
    count, stop = repeat_parameters(effect, invocation.level)
    reports = []
    for iteration in range(max(0, count)):
        created = failed = applications = 0
        for reference in effect["children"]:
            # Native bbB path passes null target and the parent's cell; selection
            # belongs to native child targeting, not the repeat scheduler.
            outcome = execute_child(
                reference, replace(invocation, target_id=None), iteration
            )
            if (
                not isinstance(outcome, RepeatChildOutcome)
                or type(outcome.pt_created) is not bool
            ):
                raise ValueError("Native repeat requires explicit PT creation/result")
            if not outcome.pt_created:
                if outcome.applications is not None:
                    raise ValueError("Absent PT cannot supply application count")
            else:
                if type(
                    outcome.applications
                ) is not int or not 0 <= outcome.applications < (1 << 31):
                    raise ValueError("Missing native PT.bas application count")
                created += 1
                applications += outcome.applications
                if outcome.applications == 0:
                    failed += 1
        reports.append(dict(created=created, failed=failed, applications=applications))
        if stop and failed > 0:
            break
    return reports
