"""DB-scoped reconstructed controller population, separate from native Qe.g.

Only admitted policies can reselect the population of their original immediate
criterion groups. Chosen-PV replay, event recipients and leaf effects retain
their native contracts. Original selectors and criteria are never rewritten.
"""
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class GroupPopulationPolicy:
    policy: str
    authority: str
    map_id: int
    monster_references: tuple
    effects: tuple

    def record(self):
        return dict(
            policy=self.policy,
            authority=self.authority,
            map_id=self.map_id,
            monster_references=list(self.monster_references),
            effects=[[*row[:-1], list(row[-1])] for row in self.effects],
        )


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=64)
def _version(identity):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_group_population_versions WHERE policy=%s",
            (identity,),
        ).fetchone()
        effects = db.execute(
            "SELECT effect_reference,effect_family,selector_mask,parameter_count,criterion,native_parameters "
            "FROM encounter_group_population_effects WHERE policy=%s ORDER BY effect_reference",
            (identity,),
        ).fetchall()
    if row is None or not effects:
        raise ValueError("Unknown frozen encounter group population policy")
    rules = tuple(
        tuple(
            tuple(effect[key]) if key == "native_parameters" else effect[key]
            for key in (
                "effect_reference",
                "effect_family",
                "selector_mask",
                "parameter_count",
                "criterion",
                "native_parameters",
            )
        )
        for effect in effects
    )
    if tuple(rule[0] for rule in rules) != tuple(row["effect_references"]):
        raise ValueError("Incomplete immutable encounter group population inventory")
    policy = GroupPopulationPolicy(
        row["policy"],
        row["authority"],
        row["map_id"],
        tuple(row["monster_references"]),
        rules,
    )
    if (
        not policy.policy
        or not policy.authority
        or type(policy.map_id) is not int
        or not policy.monster_references
        or tuple(sorted(set(policy.monster_references))) != policy.monster_references
        or any(
            type(value) is not int or value <= 0 for value in policy.monster_references
        )
        or any(
            type(ref) is not int
            or ref <= 0
            or family not in (304, 321, 330)
            or type(mask) is not int
            or mask < 0
            or mask & 1
            or type(count) is not int
            or count < 0
            or len(parameters) != count * 2
            or not isinstance(criterion, str)
            or not criterion.strip()
            for ref, family, mask, count, criterion, parameters in rules
        )
    ):
        raise ValueError("Unreviewed encounter group population contract")
    return policy


def freeze_group_population_policy(fight, *, roles):
    if hasattr(fight, "native_encounter_group_population"):
        record = fight.native_encounter_group_population
        if record is None:
            return None
        policy = _version(record["policy"])
        if record != policy.record() or (policy.map_id, policy.monster_references) != (
            roles.map_id,
            roles.monster_references,
        ):
            raise ValueError("Frozen encounter group population scope drifted")
        return policy
    with _database().connection() as db:
        row = db.execute(
            "SELECT policy FROM encounter_group_population_active "
            "WHERE map_id=%s AND monster_references=%s::integer[]",
            (roles.map_id, list(roles.monster_references)),
        ).fetchone()
    if row is None:
        fight.native_encounter_group_population = None
        return None
    policy = _version(row["policy"])
    if (policy.map_id, policy.monster_references) != (
        roles.map_id,
        roles.monster_references,
    ):
        raise ValueError("Active group population policy belongs to another scope")
    fight.native_encounter_group_population = policy.record()
    return policy


def permits_fresh_group_population(fight, effect, invocation):
    record = getattr(fight, "native_encounter_group_population", None)
    if record is None:
        return False
    if not isinstance(record, dict) or not isinstance(record.get("policy"), str):
        raise ValueError("Missing frozen group population authority")
    policy = _version(record["policy"])
    if record != policy.record():
        raise ValueError("Frozen group population contract drifted")
    from wakfu_server.combat_encounter_roles import frozen_roles

    roles = frozen_roles(fight)
    if roles is None or (roles.map_id, roles.monster_references) != (
        policy.map_id,
        policy.monster_references,
    ):
        raise ValueError("Group population escaped its frozen encounter scope")
    rule = next((row for row in policy.effects if row[0] == invocation.reference), None)
    if rule is None:
        return False
    _, family, mask, count, criterion, parameters = rule
    if (
        effect.get("effect_class") != family
        or effect.get("parameter_count") != count
        or tuple(effect.get("parameters", ())) != parameters
        or effect.get("criteria") != criterion
        or effect.get("area_class") != "anD"
        or effect.get("native_target_selector") != {"class": "fcE", "mask": mask}
    ):
        raise ValueError("Original reconstructed group descriptor changed")
    from .combat_effect_groups import native_group_route

    return (
        invocation.wakemu_fresh_child_selection is True
        and invocation.native_preselected_target is False
        and invocation.native_explicit_target is True
        and invocation.native_trigger_context is None
        and (family != 330 or native_group_route(effect) == "actors")
    )
