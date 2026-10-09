"""eYg relative candidate lottery, after authoritative native eligibility.

This is independent sampling, not a weighted choice of one child. Candidate
selection/criteria and eVt child context remain the caller's responsibility.
"""
import math
from .combat_parameters import _float32


def _java_int(value):
    return max(-(1 << 31), min((1 << 31) - 1, math.trunc(value)))


def relative_candidates(candidates, *, draw_integer, draw_fraction):
    """Ordered (reference, native eg(level)) candidates already validated.

    RNG order matches UK.pT then UP.bt for each candidate; integral UP.bt
    consumes no random draw because GT.l(0) returns false directly.
    """
    rows = tuple(candidates)
    probabilities = []
    total = 0
    for reference, raw in rows:
        if (
            type(reference) is not int
            or reference <= 0
            or type(raw) not in (int, float)
        ):
            raise ValueError("Invalid native relative candidate")
        probability = _float32(raw)
        if not math.isfinite(probability):
            raise ValueError("Nonfinite native relative probability")
        probabilities.append(probability)
        summed = _java_int(_float32(_float32(total) + probability))
        total = ((summed + (1 << 15)) % (1 << 16)) - (1 << 15)
    selected = []
    for (reference, _), probability in zip(rows, probabilities):
        roll = draw_integer(total) if total > 0 else 1
        if type(roll) is not int or not 1 <= roll <= max(1, total):
            raise ValueError("Invalid native relative integer RNG")
        floor = math.floor(probability)
        fraction = probability - floor
        extra = False
        if fraction:
            extra = draw_fraction(fraction)
            if type(extra) is not bool:
                raise ValueError("Invalid native relative fraction RNG")
        threshold = _java_int(floor + int(extra))
        if roll <= threshold:
            selected.append(reference)
    return tuple(selected)


def relative_eligible_candidates(rows, *, level):
    """eYg pre-lottery filtering from explicitly attested native snapshots.

    amQ.hasNext is deliberately inverted by eYg: nonempty actor selections
    skip the child. A subscribed definition skips criterion evaluation here.
    """
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Unknown native relative group level")
    candidates = []
    for row in rows:
        populated = row.get("native_area_has_actor")
        if type(populated) is not bool:
            raise ValueError("Unknown native amQ candidate population")
        if populated:
            continue
        low, high = row.get("minimum_level"), row.get("maximum_level")
        if type(low) is not int or type(high) is not int or low > high:
            raise ValueError("Unknown native candidate level bounds")
        if not low <= level <= high:
            continue
        subscribed = row.get("subscribed")
        if type(subscribed) is not bool:
            raise ValueError("Unknown native candidate subscription")
        if not subscribed:
            criterion = row.get("criterion_accepts")
            if type(criterion) is not bool:
                raise ValueError("Unknown native candidate criterion")
            if not criterion:
                continue
        candidates.append((row["reference"], row["probability"]))
    return tuple(candidates)


class RelativeGroupAuthority:
    """Factory hook backed by live ordinary actor and criterion authorities.

    Parent fRR is used for eligibility/eg, before dynamic child-level override.
    The candidate's amQ population check is NOT the application resolver.
    """

    def __init__(
        self,
        *,
        effects,
        actor_authority,
        condition_context,
        draw_integer,
        draw_fraction
    ):
        if any(
            not callable(f)
            for f in (actor_authority, condition_context, draw_integer, draw_fraction)
        ):
            raise ValueError("Missing native relative group authority")
        self.effects, self.actors, self.conditions = (
            effects,
            actor_authority,
            condition_context,
        )
        self.draw_integer, self.draw_fraction = draw_integer, draw_fraction

    def __call__(self, preview, plan, effect, values, invocation, children):
        from dataclasses import replace
        from .combat_effect_targets import select_native_effect_targets
        from .combat_conditions import evaluate_condition

        caster = preview.actors.get(invocation.caster_id)
        if caster is None:
            raise ValueError("Missing native relative caster")
        actors = tuple(preview.actors.values())
        contexts = None
        rows = []
        for reference in children:
            definition = self.effects.get(str(reference))
            if definition is None:
                raise ValueError("Unknown native relative child definition")
            from .combat_native_pt import null_exclusion_references

            # Original eYg passes child.fKX to amQ, not its aZP application
            # area. amQ returns an empty iterable for a proven null fKX.
            if reference in null_exclusion_references():
                populated = False
            else:
                from .combat_casting_context import casting_root_catalog

                root = casting_root_catalog()["roots"].get(str(reference))
                if root is None or root["native_casting_collision_area"] is None:
                    raise ValueError("Missing native relative child fKX geometry")
                if contexts is None:
                    contexts = {}
                    for actor in actors:
                        # Scalar HP does not determine native bak membership.
                        # The typed authority verifies the actual PV status.
                        if actor.physical_radius != 0:
                            raise ValueError(
                                "Relative amQ requires audited point-sized roster"
                            )
                        contexts[actor.id] = self.actors(preview, actor).targeting
                shape = root["native_casting_collision_area"]
                candidate = dict(
                    definition,
                    **shape,
                    native_target_selector=root["native_target_selector"]
                )
                populated = bool(
                    select_native_effect_targets(
                        candidate,
                        caster,
                        invocation.cell,
                        actors,
                        native_context=contexts,
                    )
                )
            row = dict(
                reference=reference,
                native_area_has_actor=populated,
                minimum_level=definition["minimum_level"],
                maximum_level=definition["maximum_level"],
            )
            # eYg checks population and parent level before metadata/criteria.
            if (
                populated
                or not row["minimum_level"] <= invocation.level <= row["maximum_level"]
            ):
                rows.append(row)
                continue
            masks = definition.get("target_masks")
            if not isinstance(masks, (tuple, list)) or len(masks) != 7:
                raise ValueError("Unknown native candidate subscription masks")
            row["subscribed"] = any(masks[i] for i in (0, 1, 3, 4, 5))
            if not row["subscribed"]:
                criterion = definition.get("criteria")
                if not isinstance(criterion, str):
                    raise ValueError("Unknown native candidate criterion")
                criteria_inv = replace(invocation, reference=reference)
                trigger = invocation.native_trigger_context
                if trigger is not None:
                    if not isinstance(trigger, dict) or "caster_id" not in trigger:
                        raise ValueError("Missing native relative source caster")
                    criteria_inv = replace(criteria_inv, caster_id=trigger["caster_id"])
                row["criterion_accepts"] = (
                    True
                    if not criterion.strip()
                    else evaluate_condition(
                        criterion,
                        self.conditions(preview, plan, definition, criteria_inv),
                    )
                )
            row["probability"] = _float32(
                _float32(definition["probability_base"])
                + _float32(
                    _float32(definition["probability_per_level"]) * invocation.level
                )
            )
            rows.append(row)
        candidates = relative_eligible_candidates(rows, level=invocation.level)
        return relative_candidates(
            candidates, draw_integer=self.draw_integer, draw_fraction=self.draw_fraction
        )
