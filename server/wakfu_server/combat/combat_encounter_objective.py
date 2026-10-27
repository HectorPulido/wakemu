"""World-owned objective boundaries and authenticated terminal intent receipts.

Receipts are plain checkpoint data; typed values cross the actor-retirement
adapter. A stored root is executable only under a complete reviewed policy.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json

from .combat_encounter_objective_policy import (
    objective_policy,
    require_admitted_policy,
)

RECEIPT_SCHEMA = "wakemu-scene-terminal-event-v1"


def _digest(record):
    from .fight_checkpoint_store import _plain

    return hashlib.sha256(
        json.dumps(
            _plain(record), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class SceneTerminalEventReceipt:
    schema: str
    policy: str
    version: int
    fight_id: int
    map_id: int
    boss_actor_id: int
    boss_reference: int
    objective_key: str
    boundary_actor_id: int
    boundary: str
    table: int
    score: int
    terminal_root: int
    terminal_kind: str
    result: str
    source: str
    scene_contract_policy: str | None
    admission_digest: str
    catalog_revision: str | None
    boundary_receipt_digest: str | None = None

    def to_record(self):
        return asdict(self)

    @classmethod
    def from_record(cls, record):
        try:
            value = cls(**record)
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid scene terminal receipt") from error
        if (
            value.schema != RECEIPT_SCHEMA
            or value.version != 1
            or value.result != "success"
            or value.terminal_kind
            not in (
                "native_boss_defeated",
                "owned_native_exit",
                "earned_scene_completion",
            )
            or type(value.fight_id) is not int
            or type(value.score) is not int
            or value.score < 0
            or type(value.admission_digest) is not str
            or len(value.admission_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in value.admission_digest)
            or any(
                type(getattr(value, key)) is not int
                for key in (
                    "version",
                    "map_id",
                    "boss_actor_id",
                    "boss_reference",
                    "boundary_actor_id",
                    "table",
                    "terminal_root",
                )
            )
            or value.fight_id <= 0
            or value.table <= 0
            or value.boss_actor_id == 0
            or value.boundary_actor_id == 0
            or value.boss_reference <= 0
            or value.terminal_root < 0
            or (value.terminal_root == 0)
            != (value.terminal_kind == "earned_scene_completion")
            or any(
                type(getattr(value, key)) is not str or not getattr(value, key)
                for key in ("policy", "objective_key", "boundary", "source")
            )
        ):
            raise ValueError("Invalid scene terminal receipt authority")
        return value


def _score_scope(fight, policy, *, profile_override=None):
    from wakfu_server.maps.boss_score import POLICY

    profile = (
        profile_override
        if profile_override is not None
        else getattr(fight, "boss_score_profile", None)
    )
    if not isinstance(profile, dict) or profile.get("policy") != POLICY:
        raise ValueError("Scenario objective lacks the existing paid score ledger")
    bosses = profile.get("bosses", {})
    if len(bosses) != 1:
        raise ValueError("Scenario objective requires an exact original boss role")
    identity, row = next(iter(bosses.items()))
    boss = fight.actors.get(int(identity))
    if boss is None or row.get("reference") != policy.reference or boss.controlled:
        raise ValueError("Scenario objective original boss role changed")
    initialized = getattr(fight, "native_npc_initialization_receipts", {}).get(boss.id)
    if (
        not isinstance(initialized, dict)
        or initialized.get("ref") != policy.reference
        or initialized.get("initialized") is not True
        or not any(
            state.get("state_id") == policy.constructor_state
            for state in initialized.get("resolved_states", ())
        )
    ):
        raise ValueError("Scenario objective lacks its original native constructor")
    players = profile.get("player_ids", ())
    if not players or any(
        type(identity) is not int
        or identity not in fight.actors
        or fight.actors[identity].controlled is not True
        or fight.actors[identity].team != profile.get("player_team")
        for identity in players
    ):
        raise ValueError("Scenario objective owned player roles changed")
    return profile, boss


def _new_score_profile(fight, policy):
    """Use the existing paid ledger without registering generic survival."""
    from wakfu_server.maps.boss_score import POLICY
    from .combat_companions import registered_companion_ids
    from .combat_terminal_metadata import registered_summon_actor_ids

    receipts = getattr(fight, "native_npc_initialization_receipts", {})
    bosses = [
        identity
        for identity, row in receipts.items()
        if row.get("ref") == policy.reference
        and row.get("initialized") is True
        and identity in fight.actors
        and not fight.actors[identity].controlled
    ]
    if (
        len(bosses) != 1
        or getattr(fight, "native_start_event_delivered", False) is not True
    ):
        raise ValueError("Objective score profile lacks its completed exact opening")
    boss = fight.actors[bosses[0]]
    dependants = registered_companion_ids(fight) | registered_summon_actor_ids(fight)
    players = sorted(
        identity
        for identity, actor in fight.actors.items()
        if actor.controlled and identity not in dependants and actor.team != boss.team
    )
    if not players or len({fight.actors[i].team for i in players}) != 1:
        raise ValueError("Objective score requires one actual owned player team")
    profile = dict(
        policy=POLICY,
        encounter_controller=policy.policy,
        bosses={
            str(boss.id): dict(
                reference=policy.reference,
                round_limit=policy.last_table,
                allow_early_boss_defeat=False,
            )
        },
        player_ids=players,
        player_team=fight.actors[players[0]].team,
        round_limit=policy.last_table,
        minimum_score=policy.minimum_score,
        includes_armor=True,
        includes_owned_summons=True,
        allow_early_boss_defeat=False,
    )
    if policy.reference == 5848:
        from .combat_encounter_objective_spirit import spirit_admission

        scene = spirit_admission(fight)
        contract = fight.native_encounter_actor_contract
        manifest = fight.native_scene_helper_manifest
        from .combat_quest_scene_authority import canonical_digest

        profile["scene_helper_score_scope"] = dict(
            fight_id=fight.id,
            manifest=deepcopy(manifest),
            ready_digest=scene["ready_participants"]["source_digest"],
            ready_owners={
                str(row["actor_id"]): row["account_id"]
                for row in scene["ready_participants"]["source"]["players"]
            },
            catalog_revision=contract["catalog_revision"],
            births={
                str(row["actor_id"]): canonical_digest(
                    fight.native_npc_initialization_receipts[row["actor_id"]]
                )
                for row in manifest["source"]["helpers"]
            },
        )
    return profile


def _admission(fight, policy):
    contract = getattr(fight, "native_encounter_actor_contract", None)
    if contract is not None:
        from .combat_encounter_actor_contract import actor_contract_admission_digest

        digest = actor_contract_admission_digest(fight)
        if contract["map_id"] != policy.map_id:
            raise ValueError("Objective and actor contract maps disagree")
        if (
            policy.scene_contract_policy is not None
            and contract["policy"] != policy.scene_contract_policy
        ):
            raise ValueError("Objective lacks its reviewed source scene contract")
        if policy.policy not in contract["declaration"]["terminal_policies"]:
            raise ValueError(
                "Actor scene has not admitted this objective result policy"
            )
        if policy.reference == 5848:
            from .combat_encounter_objective_spirit import spirit_admission

            scene = spirit_admission(fight)
            if scene is None or scene["status"] not in ("granted", "cleaned"):
                raise ValueError(
                    "Spirit objective lacks its earned player scene program"
                )
            ready = scene.get("ready_participants")
            if ready is None or set(scene["carrier_uids"]) != {
                str(row["actor_id"]) for row in ready["source"]["players"]
            }:
                raise ValueError(
                    "Spirit objective player carrier provenance is incomplete"
                )
        return contract["policy"], digest, contract["catalog_revision"]
    if not policy.observe_existing_exit:
        raise ValueError("Scenario objective requires an admitted actor contract")
    # The old qualified Ogrest controller predates the actor sidecar. Preserve
    # its exact scene/score identity instead of inventing new admission data.
    layout = getattr(fight, "native_encounter_scene_layout", None)
    if not isinstance(layout, dict) or layout.get("map_id") != policy.map_id:
        raise ValueError("Existing exit lacks its original scene admission")
    profile, _ = _score_scope(fight, policy)
    return (
        None,
        _digest(dict(fight_id=fight.id, layout=layout, score_profile=profile)),
        None,
    )


def install_objective_policy(fight, policy_record, *, objective_player_id=None):
    """Freeze a complete published descriptor before any objective damage."""
    policy = require_admitted_policy(policy_record)
    if fight.phase != "active" or fight.turn_id != 1:
        raise ValueError("Scenario objective requires its original opening admission")
    _admission(fight, policy)
    previous_score = getattr(fight, "boss_score_profile", None)
    profile = (
        previous_score
        if previous_score is not None
        else _new_score_profile(fight, policy)
    )
    _score_scope(fight, policy, profile_override=profile)
    if getattr(fight, "boss_score_events", {}):
        raise ValueError("Scenario objective must be admitted before damage")
    previous = getattr(fight, "native_encounter_objective_policy", None)
    if previous is not None and previous != policy_record:
        raise ValueError("Scenario objective admission changed")
    roles = (
        policy.terminal_caster_role,
        policy.terminal_target_role,
        policy.marker_role,
    )
    if "objective_player" in roles:
        if objective_player_id is None and len(profile["player_ids"]) == 1:
            objective_player_id = profile["player_ids"][0]
        if objective_player_id not in profile["player_ids"]:
            raise ValueError(
                "Scenario objective lacks its authenticated principal player"
            )
        old_player = getattr(fight, "native_encounter_objective_player_id", None)
        if old_player is not None and old_player != objective_player_id:
            raise ValueError("Scenario objective principal player changed")
        fight.native_encounter_objective_player_id = objective_player_id
    fight.native_encounter_objective_policy = deepcopy(policy_record)
    if previous_score is None:
        fight.boss_score_profile = profile
    if not hasattr(fight, "boss_score_events"):
        fight.boss_score_events = {}
    return policy


def _record(fight, policy, *, actor_id, table, root, kind, source):
    from wakfu_server.maps.boss_score_runtime import staged_score

    _, boss = _score_scope(fight, policy)
    contract, digest, revision = _admission(fight, policy)
    receipt = SceneTerminalEventReceipt(
        RECEIPT_SCHEMA,
        policy.policy,
        1,
        fight.id,
        policy.map_id,
        boss.id,
        policy.reference,
        policy.objective_key,
        actor_id,
        policy.boundary,
        table,
        staged_score(fight),
        root,
        kind,
        "success",
        source,
        contract,
        digest,
        revision,
        _digest(fight.native_equipment_completed_rounds[str(table)])
        if policy.boundary == "completed_round"
        else None,
    )
    SceneTerminalEventReceipt.from_record(receipt.to_record())
    journal = getattr(fight, "native_encounter_objective_results", {})
    previous = journal.get(policy.policy)
    if previous is not None and previous != receipt.to_record():
        raise ValueError("Scenario objective terminal replay changed")
    fight.native_encounter_objective_results = {
        **journal,
        policy.policy: receipt.to_record(),
    }
    return receipt


def _terminal_actor(fight, profile, boss, boundary_actor_id, role):
    if role == "boundary_actor":
        return fight.actors[boundary_actor_id]
    if role == "boss":
        return boss
    if role == "sole_player" and len(profile["player_ids"]) == 1:
        return fight.actors[profile["player_ids"][0]]
    if role == "objective_player":
        if (
            boss.id in fight.actors
            and profile["bosses"][str(boss.id)]["reference"] == 5848
        ):
            from .combat_encounter_objective_spirit import spirit_result_player

            actor = spirit_result_player(fight)
            if actor is not None:
                return actor
            raise ValueError("Spirit result has no live owned original player carrier")
        identity = getattr(fight, "native_encounter_objective_player_id", None)
        if identity in profile["player_ids"]:
            return fight.actors[identity]
    if isinstance(role, str) and role.startswith("actor:"):
        from .combat_encounter_actor_contract import validate_actor_bindings

        bindings = validate_actor_bindings(fight)
        binding = bindings.get(role[len("actor:") :])
        if binding is not None:
            return fight.actors[binding["actor_id"]]
    raise ValueError("Objective terminal actor lacks its reviewed role binding")


def _retirement_authority(fight, policy, boss):
    """Require the original boss among explicitly admitted native934 roles."""
    from .combat_encounter_actor_contract import (
        contract_from_record,
        validate_actor_bindings,
    )

    bindings = validate_actor_bindings(fight)
    contract = fight.native_encounter_actor_contract
    spec = contract_from_record(contract["declaration"])
    matching = [
        role
        for role in spec.roles
        if role.retire_on_success
        and role.reference == policy.reference
        and bindings.get(role.role, {}).get("actor_id") == boss.id
    ]
    if policy.policy not in spec.terminal_policies or len(matching) != 1:
        raise ValueError("Scene completion lacks its exact native boss retirement role")


def _completed_round(fight):
    from .combat_equipment_external_events import ROUND_POLICY

    number = fight.native_timeline_round - 1
    receipt = getattr(fight, "native_equipment_completed_rounds", {}).get(str(number))
    if receipt is None:
        return None
    if (
        receipt.get("policy") != ROUND_POLICY
        or receipt.get("completed_round") != number
        or receipt.get("ending_turn") != fight.turn_id - 1
        or receipt.get("ending_actor") not in fight.actors
        or receipt.get("delivered") is not True
    ):
        raise ValueError("Objective lacks its actual delivered completed-round receipt")
    return number


def _enter_objective_marker(dispatcher, policy, actor):
    """Reviewed director entry through the original direct-eWu state carrier.

    Called only after paid quota, admission and the real boundary are proven.
    The native definition and children execute; no state ledger is edited.
    """
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    if any(
        entry.reference == policy.success_marker for entry in actor.state_ledger.entries
    ):
        return
    handler = dispatcher.native_state_handler
    native = state_profile(handler.catalog, policy.success_marker, 1)
    if (
        native["duration"] != -1
        or native["realtime_duration"] != 0
        or native["level"] != 1
    ):
        raise ValueError("Objective marker lacks its original indefinite carrier")
    invocation = EffectInvocation(
        2226,
        1,
        actor.id,
        actor.id,
        actor.position,
        native_retained_container={"present": False},
    )
    context = StateCarrierContext(
        -1,
        0,
        False,
        None,
        None,
        False,
        False,
        False,
        0,
        native_time_payload(realtime_remaining=0),
    )
    if not dispatcher.native_retention.apply_state_reference(
        handler,
        invocation,
        policy.success_marker,
        1,
        carrier_context=context,
    ):
        raise ValueError("Original objective result marker did not enter")


def deliver_objective_score_marker(
    dispatcher, *, actor_id, allow_delivered_round=False
):
    """Qualify score before the original player's timed native producer fires."""
    fight = dispatcher.native_retention.fight
    frozen = getattr(fight, "native_encounter_objective_policy", None)
    if frozen is None:
        return False
    policy = require_admitted_policy(frozen)
    if not policy.observe_native_producer or policy.success_marker is None:
        return False
    if fight.phase != "active" or fight.current is None or fight.current.id != actor_id:
        raise ValueError("Objective score marker requires a real owned boundary")
    profile, boss = _score_scope(fight, policy)
    _admission(fight, policy)
    from wakfu_server.maps.boss_score_runtime import staged_score

    score = staged_score(fight)
    if score < policy.minimum_score:
        return False
    if policy.boundary == "completed_round":
        from .combat_equipment_external_events import ROUND_POLICY

        number = fight.native_timeline_round - 1
        pending = getattr(fight, "native_equipment_completed_rounds", {}).get(
            str(number)
        )
        if (
            not policy.first_table <= number <= policy.last_table
            or not isinstance(pending, dict)
            or pending.get("policy") != ROUND_POLICY
            or pending.get("completed_round") != number
            or pending.get("ending_turn") != fight.turn_id - 1
            or pending.get("ending_actor") not in fight.actors
            or pending.get("delivered")
            not in ((False, True) if allow_delivered_round else (False,))
        ):
            return False
    if policy.reference == 5848:
        from .combat_encounter_objective_spirit import spirit_result_player

        player = spirit_result_player(fight)
        if player is None:
            return False
    else:
        player = _terminal_actor(fight, profile, boss, actor_id, policy.marker_role)
    carriers = [
        entry
        for entry in player.state_ledger.entries
        if entry.reference == policy.native_player_state
    ]
    if len(carriers) != 1 or not fight._in_play(player):
        return False
    if policy.reference == 5848:
        from .combat_encounter_objective_spirit import spirit_admission

        scene = spirit_admission(fight)
        if scene["carrier_uids"].get(str(player.id)) != carriers[0].uid:
            raise ValueError("Spirit score marker does not own its original9145 source")
    journal = getattr(fight, "native_encounter_objective_markers", {})
    old = journal.get(policy.policy)
    if old is not None:
        if old["actor_id"] == player.id and old["carrier_uid"] == carriers[0].uid:
            return False
        history = getattr(fight, "native_spirit_result_leadership", {}).get(
            "handoffs", ()
        )
        if (
            policy.reference != 5848
            or not history
            or history[-1].get("from_actor_id") != old["actor_id"]
            or history[-1].get("actor_id") != player.id
            or old.get("source") != "actual_owned_paid_score_boundary"
            or not policy.minimum_score <= old.get("score", -1) <= score
        ):
            raise ValueError(
                "Objective player source carrier changed without an earned handoff"
            )
    existing = {
        entry.uid
        for entry in player.state_ledger.entries
        if entry.reference == policy.success_marker
    }
    _enter_objective_marker(dispatcher, policy, player)
    markers = [
        entry
        for entry in player.state_ledger.entries
        if entry.reference == policy.success_marker
    ]
    if len(markers) != 1:
        raise ValueError("Objective marker source identity is ambiguous")
    previous = (
        []
        if old is None
        else [
            *old.get("previous_markers", ()),
            {k: v for k, v in old.items() if k != "previous_markers"},
        ]
    )
    fight.native_encounter_objective_markers = {
        **journal,
        policy.policy: dict(
            actor_id=player.id,
            carrier_uid=carriers[0].uid,
            marker=policy.success_marker,
            minimum_score=policy.minimum_score,
            score=score,
            marker_uid=markers[0].uid,
            owns_marker=markers[0].uid not in existing,
            previous_markers=previous,
            source="actual_owned_paid_score_boundary",
        ),
    }
    return True


def observe_native_terminal(fight):
    """Observe a real existing exit without assigning a winner or killing HP."""
    from .combat_boss_score_policy import OGREST_SCORE, native_score_policy
    from .combat_ogrest_phase_controller import ogrest_terminal_authority

    frozen = getattr(fight, "native_encounter_objective_policy", None)
    if frozen is None:
        return None
    policy = require_admitted_policy(frozen)
    if not policy.observe_existing_exit:
        return None
    if native_score_policy(getattr(fight, "boss_score_profile", None)) != OGREST_SCORE:
        return None
    authority = ogrest_terminal_authority(fight)
    if authority is None or fight.phase != "finished":
        return None
    return _record(
        fight,
        policy,
        actor_id=authority["actor_id"],
        table=authority["table"],
        root=authority["effect_reference"],
        kind="owned_native_exit",
        source=authority["source"],
    )


def deliver_objective_boundary(dispatcher, *, actor_id, boundary):
    """Evaluate the paid objective and execute its original native terminal.

    This is a caller-owned preview operation. Five incomplete declarations
    currently cannot pass admission; recovered authoring enables this same path.
    """
    fight = dispatcher.native_retention.fight
    record = getattr(fight, "native_encounter_objective_policy", None)
    if record is None:
        return None
    policy = require_admitted_policy(record)
    if policy.observe_existing_exit:
        return observe_native_terminal(fight)
    previous = getattr(fight, "native_encounter_objective_results", {}).get(
        policy.policy
    )
    if previous is not None:
        return verify_scene_terminal_intent(fight, previous)
    profile, boss = _score_scope(fight, policy)
    _admission(fight, policy)
    if (
        boundary != policy.boundary
        or actor_id not in fight.actors
        or (
            not (policy.observe_native_producer and fight.phase == "finished")
            and (
                fight.phase != "active"
                or fight.current is None
                or fight.current.id != actor_id
            )
        )
    ):
        raise ValueError("Objective terminal requires its actual owned boundary")
    table = (
        _completed_round(fight)
        if boundary == "completed_round"
        else getattr(fight, "native_table_turn", None)
    )
    if type(table) is not int or not policy.first_table <= table <= policy.last_table:
        return None
    from wakfu_server.maps.boss_score_runtime import staged_score

    if staged_score(fight) < policy.minimum_score:
        return None
    if boundary == "owned_boss_start" and actor_id != boss.id:
        raise ValueError("Objective boundary does not belong to its original boss")
    if boundary == "owned_player_end" and actor_id not in profile["player_ids"]:
        raise ValueError("Objective boundary does not belong to an owned player")
    if not any(fight._in_play(fight.actors[i]) for i in profile["player_ids"]):
        return None
    if policy.retirement_only:
        _retirement_authority(fight, policy, boss)
        return _record(
            fight,
            policy,
            actor_id=actor_id,
            table=table,
            root=0,
            kind="earned_scene_completion",
            source=(
                "actual_completed_objective_round"
                if boundary == "completed_round"
                else "actual_owned_objective_boundary"
            ),
        )
    if policy.observe_native_producer:
        marker = getattr(fight, "native_encounter_objective_markers", {}).get(
            policy.policy
        )
        leader = getattr(fight, "native_spirit_result_leadership", {}).get("actor_id")
        if (
            boss.hp > 0
            or not isinstance(marker, dict)
            or marker.get("score", -1) < policy.minimum_score
            or marker.get("marker") != policy.success_marker
        ):
            return None
        return _record(
            fight,
            policy,
            actor_id=actor_id,
            table=table,
            root=policy.success_root,
            kind="native_boss_defeated",
            source="actual_completed_objective_round",
        )
    if boss.hp <= 0:
        raise ValueError("Objective terminal cannot claim an earlier boss death")
    from .combat_effect_dispatch import EffectInvocation

    caster = _terminal_actor(
        fight, profile, boss, actor_id, policy.terminal_caster_role
    )
    target = _terminal_actor(
        fight, profile, boss, actor_id, policy.terminal_target_role
    )
    if policy.success_marker is not None:
        marked = _terminal_actor(fight, profile, boss, actor_id, policy.marker_role)
        if not fight._in_play(marked):
            return None
        _enter_objective_marker(dispatcher, policy, marked)
    dispatcher.execute(
        EffectInvocation(
            policy.success_root,
            caster.effective_level,
            caster.id,
            target.id,
            target.position,
            native_retained_container={"present": False},
        )
    )
    # Successful registration of a conditional group is not terminal proof.
    # An actual original kill is required before helper retirement can follow.
    if boss.hp > 0 or not any(
        fight._in_play(fight.actors[i]) for i in profile["player_ids"]
    ):
        return None
    if fight.phase == "finished" and fight.winner != profile["player_team"]:
        return None
    return _record(
        fight,
        policy,
        actor_id=actor_id,
        table=table,
        root=policy.success_root,
        kind="native_boss_defeated",
        source=(
            "actual_completed_objective_round"
            if boundary == "completed_round"
            else "actual_owned_objective_boundary"
        ),
    )


def deliver_owned_objective_boundary(dispatcher, *, actor_id, boundary):
    """Optional production hook; other actors and unbound fights are no-ops."""
    fight = dispatcher.native_retention.fight
    record = getattr(fight, "native_encounter_objective_policy", None)
    if record is None:
        return None
    policy = require_admitted_policy(record)
    if policy.boundary != boundary:
        return None
    profile, boss = _score_scope(fight, policy)
    if boundary == "owned_player_end" and actor_id not in profile["player_ids"]:
        return None
    if boundary == "owned_boss_start" and actor_id != boss.id:
        return None
    if fight.phase != "active" and not (
        policy.observe_existing_exit or policy.observe_native_producer
    ):
        return None
    intent = deliver_objective_boundary(
        dispatcher, actor_id=actor_id, boundary=boundary
    )
    if (
        intent is not None
        and getattr(fight, "native_encounter_actor_contract", None) is not None
    ):
        from .combat_encounter_actor_contract_terminal import (
            deliver_actor_objective_cleanup,
        )

        deliver_actor_objective_cleanup(dispatcher, intent)
    return intent


def verify_scene_terminal_intent(fight, receipt):
    """Authenticate active-fight terminal intent before scoped helper cleanup."""
    if isinstance(receipt, dict):
        receipt = SceneTerminalEventReceipt.from_record(receipt)
    if not isinstance(receipt, SceneTerminalEventReceipt):
        raise ValueError("Typed scene terminal intent required")
    policy = require_admitted_policy(
        getattr(fight, "native_encounter_objective_policy", None)
    )
    if receipt.boss_reference != policy.reference or receipt.policy != policy.policy:
        raise ValueError("Unadmitted scene terminal policy")
    if getattr(fight, "native_encounter_objective_policy", None) != policy.record():
        raise ValueError("Scene terminal lost its frozen objective admission")
    if receipt.fight_id != fight.id or receipt.map_id != policy.map_id:
        raise ValueError("Scene terminal intent belongs to another admission")
    if (
        receipt.objective_key != policy.objective_key
        or receipt.boundary != policy.boundary
    ):
        raise ValueError("Scene terminal objective binding changed")
    if policy.boundary == "completed_round":
        from .combat_equipment_external_events import ROUND_POLICY

        completed = getattr(fight, "native_equipment_completed_rounds", {}).get(
            str(receipt.table)
        )
        if (
            not isinstance(completed, dict)
            or completed.get("policy") != ROUND_POLICY
            or completed.get("completed_round") != receipt.table
            or completed.get("delivered") is not True
            or receipt.boundary_receipt_digest != _digest(completed)
        ):
            raise ValueError("Scene terminal completed-round evidence changed")
    journal = getattr(fight, "native_encounter_objective_results", {})
    if journal.get(policy.policy) != receipt.to_record():
        raise ValueError("Scene terminal intent lacks its original journal")
    contract, digest, revision = _admission(fight, policy)
    if (contract, digest, revision) != (
        receipt.scene_contract_policy,
        receipt.admission_digest,
        receipt.catalog_revision,
    ):
        raise ValueError("Scene terminal actor contract changed")
    from wakfu_server.maps.boss_score_runtime import staged_score

    profile, boss = _score_scope(fight, policy)
    if boss.id != receipt.boss_actor_id or staged_score(fight) != receipt.score:
        raise ValueError("Scene terminal paid ledger or boss changed")
    if receipt.score < policy.minimum_score:
        raise ValueError("Scene terminal objective is not earned")
    if receipt.terminal_kind == "owned_native_exit":
        from .combat_ogrest_phase_controller import ogrest_terminal_authority

        authority = ogrest_terminal_authority(fight)
        if (
            not policy.observe_existing_exit
            or authority is None
            or fight.phase != "finished"
            or fight.winner != profile["player_team"]
            or authority["actor_id"] != receipt.boundary_actor_id
            or authority["table"] != receipt.table
            or authority["effect_reference"] != receipt.terminal_root
            or authority["source"] != receipt.source
        ):
            raise ValueError("Scene terminal lost its actual owned native exit")
    elif receipt.terminal_kind == "earned_scene_completion":
        if not policy.retirement_only or policy.success_root is not None:
            raise ValueError("Scene retirement result belongs to another terminal mode")
        _retirement_authority(fight, policy, boss)
        if (
            receipt.source
            != (
                "actual_completed_objective_round"
                if policy.boundary == "completed_round"
                else "actual_owned_objective_boundary"
            )
            or not policy.first_table <= receipt.table <= policy.last_table
            or not any(fight._in_play(fight.actors[i]) for i in profile["player_ids"])
            or (fight.phase == "finished" and fight.winner != profile["player_team"])
        ):
            raise ValueError("Scene retirement lost its earned objective evidence")
    elif (
        policy.observe_existing_exit
        or boss.hp > 0
        or receipt.terminal_root != policy.success_root
        or receipt.boundary != policy.boundary
        or receipt.source
        != (
            "actual_completed_objective_round"
            if policy.boundary == "completed_round"
            else "actual_owned_objective_boundary"
        )
        or not policy.first_table <= receipt.table <= policy.last_table
        or not any(fight._in_play(fight.actors[i]) for i in profile["player_ids"])
        or (fight.phase == "finished" and fight.winner != profile["player_team"])
    ):
        raise ValueError("Scene terminal lost its actual native boss defeat")
    if policy.observe_native_producer:
        marker = getattr(fight, "native_encounter_objective_markers", {}).get(
            policy.policy
        )
        if (
            not isinstance(marker, dict)
            or marker.get("marker") != policy.success_marker
            or marker.get("source") != "actual_owned_paid_score_boundary"
            or marker.get("minimum_score") != policy.minimum_score
            or not policy.minimum_score <= marker.get("score", -1) <= receipt.score
            or marker.get("actor_id")
            != (
                leader
                if policy.reference == 5848
                else getattr(fight, "native_encounter_objective_player_id", None)
            )
        ):
            raise ValueError("Scene terminal lost its earned native producer marker")
    return receipt
