"""Lossless recycling observations across native-equivalent equipment models.

These nullable observations do not install sockets or identify an item. The
original fnR.ghe uses the template gjv flag and the carried fpI state; gjH uses
the installed references. Equal flags plus unchanged socket state retain the
same observation domain. No animal or random-use identity is reinterpreted.
"""


def validate_target(reference, observation):
    from .recycling import CATALOG

    template = CATALOG.get(str(reference))
    if template is None or type(template.get("template_gjv")) is not bool:
        raise ValueError("Missing native recycling observation authority")
    if (
        not isinstance(observation, dict)
        or set(observation) != {"unidentified", "socketed"}
        or any(
            value is not None and type(value) is not bool
            for value in observation.values()
        )
        or all(value is None for value in observation.values())
    ):
        raise ValueError("Invalid native recycling observation")
    return dict(observation)


def validate_pair(source_reference, target_reference, observation):
    from .recycling import CATALOG
    from .equipment import RULES

    result = validate_target(source_reference, observation)
    validate_target(target_reference, observation)
    source, target = RULES.get(source_reference), RULES.get(target_reference)
    if (
        source is None
        or target is None
        or not source.get("slots")
        or any(
            source.get(key) != target.get(key) for key in ("slots", "occupied_slots")
        )
        or CATALOG[str(source_reference)]["template_gjv"]
        != CATALOG[str(target_reference)]["template_gjv"]
    ):
        raise ValueError("Native recycling observation domains differ")
    return result
