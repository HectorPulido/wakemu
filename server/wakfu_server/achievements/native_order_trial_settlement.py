"""Settle an earned order-trial result from its accepted terminal checkpoint.

The finish may be a native surrender or three-strike defeat. Team victory,
client score messages and interrupted/aborted checkpoints are not substitutes
for the frozen server-observed trial state.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class CompletionRule:
    admission_id: str
    event_reference: int
    minimum_score: int
    evidence: str

    def __post_init__(self):
        if (
            type(self.admission_id) is not str
            or not self.admission_id
            or type(self.event_reference) is not int
            or self.event_reference <= 0
            or type(self.minimum_score) is not int
            or self.minimum_score <= 0
            or type(self.evidence) is not str
            or not self.evidence.strip()
        ):
            raise ValueError(
                "Order completion needs an explicit reviewed producer rule"
            )


@lru_cache(maxsize=1)
def load_rule():
    """Bind the shipped arcade to its declared native scenario score event."""
    from wakfu_server import native_order_trial_admission

    source = Path(__file__).with_name("order_trial_profiles") / "astrub_pizzlarva.json"
    document = json.loads(source.read_text())
    if (
        document.get("schema") != 1
        or document.get("achievement") != 2149
        or document.get("objective") != 4261
        or document.get("scenario") != 1719
    ):
        raise ValueError("Order completion differs from its declared native mission")
    return CompletionRule(
        admission_id=native_order_trial_admission.document()["id"],
        event_reference=document["events"]["score_validated"],
        minimum_score=document["rules"]["hard_score_threshold"],
        evidence="Original scenario1719 score event14412; accepted server-scored hard attempt",
    )


def _deliver(db, store, fight, proof, rule):
    from . import mission_toolkit

    character = store.character(proof.account_id, proof.owner_id, db)
    if character is None:
        raise ValueError("Order completion owner no longer exists")
    identity = sha256(
        json.dumps(
            dict(
                admission_id=rule.admission_id,
                event_reference=rule.event_reference,
                minimum_score=rule.minimum_score,
                evidence=rule.evidence,
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    packets = mission_toolkit.settle(
        db,
        store,
        character,
        f"native-order-trial:{fight.id}:{identity}",
        "scenario_completed",
        rule.event_reference,
    )
    return {proof.account_id: packets} if packets else {}


def stage(db, store, fight, rule):
    """Return owner packets inside the existing terminal settlement transaction.

    The caller holds the normal account/character settlement locks and has
    written the accepted terminal checkpoint in this same transaction. The
    shared mission toolkit retains explicit quest admission and unique rewards.
    No handler or completion rule is registered merely by importing this file.
    """
    document = getattr(fight, "native_order_trial", None)
    if document is None:
        return {}
    from wakfu_server.native_order_trial_checkpoint import FIELD, validate
    from .native_order_trials import qualifies

    if not isinstance(rule, CompletionRule):
        raise ValueError("Missing reviewed order completion producer")
    if fight.phase != "finished":
        return {}
    proof, rules, state = validate(document, encounter_id=fight.id)
    if (
        proof.profile_id != rule.admission_id
        or rules.score_threshold != rule.minimum_score
    ):
        raise ValueError(
            "Order completion differs from its frozen admission or score rule"
        )
    if not qualifies(state, rules):
        return {}
    row = db.execute(
        "SELECT f.status AS fight_status,c.status AS checkpoint_status,c.snapshot "
        "FROM combat_fights f JOIN fight_checkpoints c ON c.fight_id=f.id "
        "WHERE f.id=%s FOR UPDATE OF f,c",
        (fight.id,),
    ).fetchone()
    if (
        row is None
        or row["fight_status"] != "finished"
        or row["checkpoint_status"] not in ("active", "ended")
        or not isinstance(row["snapshot"], dict)
        or row["snapshot"].get("phase") != "finished"
        or row["snapshot"].get(FIELD) != document
    ):
        raise ValueError(
            "Order completion has no matching accepted terminal checkpoint"
        )
    owner = db.execute(
        "SELECT account_id FROM combat_fight_participants "
        "WHERE fight_id=%s AND character_id=%s",
        (fight.id, proof.owner_id),
    ).fetchone()
    if owner is None or owner["account_id"] != proof.account_id:
        raise ValueError("Order completion lost its original durable participant")
    return _deliver(db, store, fight, proof, rule)


def stage_withdrawal(db, store, candidate, rule):
    """Finish a voluntary withdrawal against its accepted pre-departure score.

    Individual PvE surrender uses a durable withdrawal receipt instead of a
    winning terminal checkpoint. The caller inserts that native receipt in
    the same transaction before this hook, and supplies the real departure
    candidate. An interruption or generic aborted fight has no such authority.
    The score sidecar remains the unchanged last accepted action checkpoint.
    """
    document = getattr(candidate, "native_order_trial", None)
    if document is None:
        return {}
    from wakfu_server.native_order_trial_checkpoint import FIELD, validate

    if not isinstance(rule, CompletionRule):
        raise ValueError("Missing reviewed order withdrawal producer")
    proof, rules, state = validate(document, encounter_id=candidate.id)
    if (
        proof.profile_id != rule.admission_id
        or rules.score_threshold != rule.minimum_score
    ):
        raise ValueError("Order withdrawal differs from its frozen score rule")
    if not state.hard_mode or state.score < rules.score_threshold:
        return {}
    actor = candidate.actors.get(proof.owner_id)
    if (
        actor is None
        or actor.owner_id != proof.account_id
        or actor.controlled is not True
        or getattr(actor, "pve_withdrawn", False) is not True
        or not any(
            event.get("kind") == "withdrawn"
            and event.get("actor_id") == proof.owner_id
            and event.get("owner_id") == proof.account_id
            for event in candidate.events
        )
    ):
        raise ValueError("Order withdrawal lacks its actual native departure candidate")
    row = db.execute(
        "SELECT f.status AS fight_status,c.status AS checkpoint_status,c.snapshot,"
        "p.account_id,p.session_generation AS participant_generation,w.session_generation "
        "FROM combat_fights f JOIN fight_checkpoints c ON c.fight_id=f.id "
        "JOIN combat_fight_participants p ON p.fight_id=f.id AND p.character_id=%s "
        "JOIN combat_pve_withdrawals w ON w.fight_id=p.fight_id "
        "AND w.character_id=p.character_id AND w.account_id=p.account_id "
        "WHERE f.id=%s FOR UPDATE OF f,c,p,w",
        (proof.owner_id, candidate.id),
    ).fetchone()
    if (
        row is None
        or row["fight_status"] != "active"
        or row["checkpoint_status"] != "active"
        or row["account_id"] != proof.account_id
        or not row["participant_generation"]
        or row["session_generation"] != row["participant_generation"]
        or not isinstance(row["snapshot"], dict)
        or row["snapshot"].get("phase") != "active"
        or row["snapshot"].get(FIELD) != document
    ):
        raise ValueError(
            "Order withdrawal has no matching accepted score and native receipt"
        )
    return _deliver(db, store, candidate, proof, rule)


def stage_abandon(db, store, fight, rule, *, account_id, generation, character_id):
    """Settle a real singleton native13952 before its abort commits.

    Called only by combat_abandon.prepare after its selected-owner health CAS.
    Interrupted recovery never enters that explicit native request boundary.
    """
    document = getattr(fight, "native_order_trial", None)
    if document is None:
        return {}
    from wakfu_server.native_order_trial_checkpoint import FIELD, validate
    from wakfu_server.native_order_trial_encounter import policy_for

    if not isinstance(rule, CompletionRule):
        raise ValueError("Missing reviewed order abandonment producer")
    proof, rules, state = validate(document, encounter_id=fight.id)
    policy = policy_for(fight)
    if (
        policy is None
        or (account_id, character_id) != (proof.account_id, proof.owner_id)
        or proof.profile_id != rule.admission_id
        or rules.score_threshold != rule.minimum_score
    ):
        raise ValueError("Order abandonment differs from its original owner and rule")
    if not state.hard_mode or state.score < rules.score_threshold:
        return {}
    row = db.execute(
        "SELECT f.status AS fight_status,c.status AS checkpoint_status,c.snapshot,"
        "p.account_id,p.session_generation,h.generation AS health_generation "
        "FROM combat_fights f JOIN fight_checkpoints c ON c.fight_id=f.id "
        "JOIN combat_fight_participants p ON p.fight_id=f.id AND p.character_id=%s "
        "JOIN fight_health_exits h ON h.fight_id=p.fight_id "
        "AND h.character_id=p.character_id AND h.reason='abort' "
        "WHERE f.id=%s FOR UPDATE OF f,c,p,h",
        (proof.owner_id, fight.id),
    ).fetchone()
    if (
        row is None
        or fight.phase != "active"
        or row["fight_status"] != "active"
        or row["checkpoint_status"] != "active"
        or row["account_id"] != account_id
        or not generation
        or row["session_generation"] != generation
        or row["health_generation"] != generation
        or not isinstance(row["snapshot"], dict)
        or row["snapshot"].get("phase") != "active"
        or row["snapshot"].get(FIELD) != document
    ):
        raise ValueError(
            "Order abandonment has no accepted score and owned native exit"
        )
    return _deliver(db, store, fight, proof, rule)
