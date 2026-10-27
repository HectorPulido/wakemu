"""Explicit DB-backed encounter publisher, separate from native Qq registration.

Native Qq.bcH does not produce10006. This reconstructed publisher delivers the
existing event only to real living occupants of a newly registered scoped area.
Policy and deduplication live on the transactional fight, not on the factory.
"""
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class EncounterAreaActivation:
    policy: str
    authority: str
    map_id: int
    monster_references: tuple
    area_references: tuple
    event_id: int
    timing: str

    def record(self):
        return dict(
            policy=self.policy,
            authority=self.authority,
            map_id=self.map_id,
            monster_references=list(self.monster_references),
            area_references=list(self.area_references),
            event_id=self.event_id,
            timing=self.timing,
        )


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=64)
def _version(policy):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_area_activation_versions WHERE policy=%s",
            (policy,),
        ).fetchone()
    if row is None:
        raise ValueError("Unknown frozen encounter area activation policy")
    result = EncounterAreaActivation(
        row["policy"],
        row["authority"],
        row["map_id"],
        tuple(row["monster_references"]),
        tuple(row["area_references"]),
        row["event_id"],
        row["timing"],
    )
    if (
        not result.policy
        or not result.authority
        or result.event_id != 10006
        or result.timing != "post_registration"
        or type(result.map_id) is not int
        or any(
            not values
            or tuple(sorted(set(values))) != values
            or any(type(value) is not int or value <= 0 for value in values)
            for values in (result.monster_references, result.area_references)
        )
    ):
        raise ValueError("Unreviewed encounter area activation contract")
    return result


def freeze_encounter_area_policy(fight, *, roles):
    """Pin separately authorized activation data at actual encounter admission."""
    if hasattr(fight, "native_encounter_area_activation"):
        context = fight.native_encounter_area_activation
        if context is None:
            return None
        record = context["policy"]
        policy = _version(record["policy"])
        if record != policy.record() or (policy.map_id, policy.monster_references) != (
            roles.map_id,
            roles.monster_references,
        ):
            raise ValueError("Frozen encounter area activation scope drifted")
        return policy
    with _database().connection() as db:
        row = db.execute(
            "SELECT policy FROM encounter_area_activation_active "
            "WHERE map_id=%s AND monster_references=%s::integer[]",
            (roles.map_id, list(roles.monster_references)),
        ).fetchone()
    if row is None:
        fight.native_encounter_area_activation = None
        return None
    policy = _version(row["policy"])
    if (policy.map_id, policy.monster_references) != (
        roles.map_id,
        roles.monster_references,
    ):
        raise ValueError("Active encounter activation policy belongs to another scope")
    fight.native_encounter_area_activation = dict(policy=policy.record(), delivered=[])
    return policy


def post_registration_activation(dispatcher, row):
    """Publish10006 once per actual areaUID/occupant after native created()."""
    fight = dispatcher.native_retention.fight
    context = getattr(fight, "native_encounter_area_activation", None)
    if context is None:
        return ()
    record = context.get("policy")
    if not isinstance(record, dict) or not isinstance(record.get("policy"), str):
        raise ValueError("Missing frozen encounter area activation authority")
    policy = _version(record["policy"])
    if record != policy.record():
        raise ValueError("Frozen encounter area activation policy drifted")
    from wakfu_server.combat_encounter_roles import frozen_roles

    roles = frozen_roles(fight)
    if roles is None or (roles.map_id, roles.monster_references) != (
        policy.map_id,
        policy.monster_references,
    ):
        raise ValueError("Encounter area activation escaped its frozen scope")
    if row.get("reference") not in policy.area_references:
        return ()
    areas = getattr(fight, "native_effect_areas", {})
    uid = row.get("uid")
    if areas.get(uid) is not row:
        return ()
    from .combat_state_managers import registered_area_pv

    if registered_area_pv(fight, uid) is None:
        raise ValueError(
            "Encounter activation requires an actual registered native area"
        )
    runtime = dispatcher.native_area_events
    definition = runtime._definition(row)
    if policy.event_id not in definition["entry_masks"]:
        raise ValueError("Encounter activation lacks its original subscription")
    from .combat_effect_area_geometry import contains_area_cell

    identities = tuple(
        actor.id
        for actor in fight.actors.values()
        if actor.hp > 0
        and fight._in_play(actor)
        and contains_area_cell(row, actor.position)
    )
    delivered = context["delivered"]
    pending = context.setdefault("pending", [])
    for identity in identities:
        # A previous callback can unregister this area or kill/move a recipient.
        if getattr(fight, "native_effect_areas", {}).get(uid) is not row:
            break
        actor = fight.actors.get(identity)
        key = [uid, identity]
        if (
            key in delivered
            or actor is None
            or actor.hp <= 0
            or not fight._in_play(actor)
            or not contains_area_cell(row, actor.position)
        ):
            continue
        delivered.append(key)  # Reentrant children see this committed-preview mark.
        pending.append([uid, identity, row["reference"], row.get("effect_uid")])
    if context.get("draining", False):
        return ()
    context["draining"] = True
    outcomes, activations = [], 0
    try:
        while pending:
            queued_uid, identity, reference, effect_uid = pending.pop(0)
            selected = getattr(fight, "native_effect_areas", {}).get(queued_uid)
            actor = fight.actors.get(identity)
            if selected is None:
                continue
            if (
                selected.get("reference") != reference
                or selected.get("effect_uid") != effect_uid
                or registered_area_pv(fight, queued_uid) is None
            ):
                raise ValueError(
                    "Queued encounter activation lost its original area identity"
                )
            if (
                actor is None
                or actor.hp <= 0
                or not fight._in_play(actor)
                or not contains_area_cell(selected, actor.position)
            ):
                continue
            # Match the existing immediate-tree/trigger safety budget. FIFO
            # must reject an unbounded stream of fresh areaUIDs atomically.
            if activations >= 128:
                from .combat_effect_dispatch import UnsupportedEffectExecution

                raise UnsupportedEffectExecution(
                    "Encounter area activation budget exceeded"
                )
            activations += 1
            outcomes.extend(
                runtime.event(policy.event_id, identity, area_uid=queued_uid)
            )
    finally:
        context["draining"] = False
    return tuple(outcomes)
