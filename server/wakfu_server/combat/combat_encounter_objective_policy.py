"""Reviewed scenario objective declarations, independent of tactical AI.

Partial source declarations are discoverable but cannot admit a fight. Missing
publisher parameters are never replaced with generic survival or guide quotas.
"""
from dataclasses import asdict, dataclass, replace
import json


SCHEMA = "wakemu-encounter-objective-v1"


@dataclass(frozen=True)
class EncounterObjectivePolicy:
    policy: str
    reference: int
    constructor_state: int
    source: str
    map_id: int | None = None
    map_from_admission: bool = False
    scene_contract_policy: str | None = None
    minimum_score: int | None = None
    first_table: int | None = None
    last_table: int | None = None
    boundary: str | None = None
    success_root: int | None = None
    terminal_caster_role: str | None = None
    terminal_target_role: str | None = None
    success_marker: int | None = None
    marker_role: str | None = None
    objective_key: str | None = None
    observe_existing_exit: bool = False
    observe_native_producer: bool = False
    native_player_state: int | None = None
    retirement_only: bool = False
    unresolved: tuple[str, ...] = ()

    def record(self):
        record = dict(schema=SCHEMA, version=1, **asdict(self))
        record["unresolved"] = list(self.unresolved)
        return record

    @property
    def admitted(self):
        if self.unresolved:
            return False
        return (
            type(self.observe_existing_exit) is bool
            and type(self.observe_native_producer) is bool
            and type(self.retirement_only) is bool
            and sum(
                (
                    self.observe_existing_exit,
                    self.observe_native_producer,
                    self.retirement_only,
                )
            )
            <= 1
            and (
                not self.observe_native_producer
                or type(self.native_player_state) is int
            )
            and not (
                self.retirement_only
                and (self.success_root is not None or self.success_marker is not None)
            )
            and (
                type(self.map_id) is int
                or (self.map_from_admission and self.map_id is None)
            )
            and type(self.minimum_score) is int
            and self.minimum_score >= 0
            and type(self.first_table) is int
            and type(self.last_table) is int
            and 1 <= self.first_table <= self.last_table
            and self.boundary
            in ("owned_player_end", "owned_boss_start", "completed_round")
            and bool(self.objective_key)
            and (
                self.success_marker is None
                or (
                    type(self.success_marker) is int
                    and self.success_marker > 0
                    and bool(self.marker_role)
                )
            )
            and (
                self.observe_existing_exit
                or (self.retirement_only and self.success_root is None)
                or (
                    type(self.success_root) is int
                    and bool(self.terminal_caster_role)
                    and bool(self.terminal_target_role)
                )
            )
        )


_MISSING = (
    "durable admission and actor roles",
    "owned player challenge context",
    "authoritative quota and calendar",
    "earned result dispatcher and quest binding",
)
POLICIES = {
    reference: EncounterObjectivePolicy(
        policy=f"wakemu-scripted-objective-{reference}-v1",
        reference=reference,
        constructor_state=constructor,
        source="original native constructor and terminal source audit",
        success_root=root,
        unresolved=_MISSING,
    )
    for reference, constructor, root in (
        (5516, 7910, None),
        (5612, 8576, None),
        (5595, 8523, None),
        (5848, 9150, 411013),
        (5888, 9300, 415814),
    )
}
# This observer reuses the already qualified original exit director. It does
# not apply a new threshold, dispatch a synthetic kill or change its winner.
POLICIES[4378] = EncounterObjectivePolicy(
    policy="wakemu-ogrest-six-phases-v1",
    reference=4378,
    constructor_state=4979,
    source="existing owned Ogrest phase/exit director",
    map_id=1156,
    minimum_score=0,
    first_table=19,
    last_table=20,
    boundary="owned_player_end",
    success_root=238861,
    objective_key="ogrest-owned-native-exit",
    observe_existing_exit=True,
)
# Original guide175 explicitly contains paragraph478: survive thirteen rounds
# and inflict 200,000 damage to win. This is separate from higher achievement
# tiers. Its authenticated admission/player/helper context is an explicit
# reconstruction in combat_encounter_objective_spirit, on actual entry terrain.
POLICIES[5848] = EncounterObjectivePolicy(
    policy="wakemu-spirit-thirteen-rounds-v1",
    reference=5848,
    constructor_state=9150,
    source="original native guide175 pages478/492; scenario2710; root411013; reconstructed completed-round director",
    minimum_score=200000,
    first_table=13,
    last_table=13,
    boundary="completed_round",
    success_root=411013,
    terminal_caster_role="objective_player",
    terminal_target_role="boss",
    success_marker=9178,
    marker_role="objective_player",
    observe_native_producer=True,
    native_player_state=9145,
    map_from_admission=True,
    scene_contract_policy="wakemu-spirit-scenario2710-v1",
    objective_key="spirit-native-result",
    unresolved=(),
)


def objective_policy(reference):
    return POLICIES.get(reference)


def bound_objective_policy(reference, map_id):
    policy = objective_policy(reference)
    if policy is None or type(map_id) is not int:
        raise ValueError("Objective requires its actual admitted terrain")
    if policy.map_from_admission:
        return replace(policy, map_id=map_id)
    if policy.map_id != map_id:
        raise ValueError("Objective map differs from its reviewed scene")
    return policy


def require_admitted_policy(record):
    if not isinstance(record, dict):
        raise ValueError("Scenario objective requires a frozen policy record")
    policy = objective_policy(record.get("reference"))
    if policy is not None and policy.map_from_admission:
        policy = bound_objective_policy(policy.reference, record.get("map_id"))
    try:
        same = policy is not None and json.dumps(
            record, sort_keys=True, allow_nan=False
        ) == json.dumps(policy.record(), sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid frozen objective policy metadata") from error
    if policy is None or not policy.admitted or not same:
        raise ValueError("Scenario objective policy is incomplete or changed")
    return policy
