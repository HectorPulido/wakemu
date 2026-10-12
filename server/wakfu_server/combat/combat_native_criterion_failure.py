"""Source-proven native criterion exceptions at the eZR.I effect boundary."""


class NativeCriterionRuntimeFailure(Exception):
    """Known native evaluator exception, distinct from missing server authority."""


def evaluate_native_effect_condition(criteria, context):
    from .combat_conditions import evaluate_condition

    try:
        return evaluate_condition(criteria, context)
    except NativeCriterionRuntimeFailure:
        # eZR.I catches Exception from amb.b and rejects the complete criterion.
        # Do not turn failed numeric queries into zero: not/OR would change it.
        return False
