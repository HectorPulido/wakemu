"""Reconcile producer references against native artifact lifetime and receipts.

Native removal is authoritative: never resurrect a consumed Qq, fabricate a
grant, or discard earned states. A temporarily unavailable recipient postpones
only its assignment, not the player's action or the next wave.
"""


def reconcile_artifact_group(fight, group):
    """Remove stale choice references without rewriting accepted grant history."""
    areas = fight.native_effect_areas
    remaining = []
    changed = False
    for uid in group["remaining"]:
        row = areas.get(uid)
        if row is None:
            retired = group.setdefault("retired", {})
            retired.setdefault(str(uid), "native_area_absent")
            changed = True
            continue
        if row.get("native_area_contract") != "faM" or row.get("reference") != group[
            "original"
        ].get(str(uid)):
            raise ValueError("Rift artifact live identity changed its original group")
        if uid not in remaining:
            remaining.append(uid)
        else:
            changed = True
    if changed:
        group["remaining"] = remaining
    return changed


def eligible_representative(fight, team, *, area_uid, area_events):
    """Return a real eligible original fighter, or leave the choice pending."""
    actors = sorted(
        (
            actor
            for actor in fight.actors.values()
            if actor.team == team
            and fight._in_play(actor)
            and actor.id not in getattr(fight, "native_summon_registrations", {})
        ),
        key=lambda actor: actor.id,
    )
    for actor in actors:
        if area_events.artifact_assignment_eligible(area_uid, actor.id):
            return actor.id
    return None


def finish_pending_pairs(dispatcher, group, *, npc_team, before_wave=None):
    """Retry unfulfilled opponent choices through actual native activation."""
    fight = dispatcher.native_retention.fight
    changed = reconcile_artifact_group(fight, group)
    pending = group.get("pending_pairs", [])
    for request in tuple(pending):
        candidates = []
        for uid in group["remaining"]:
            recipient = eligible_representative(
                fight,
                npc_team,
                area_uid=uid,
                area_events=dispatcher.native_area_events,
            )
            if recipient is not None:
                candidates.append((uid, recipient))
        if not candidates:
            continue
        rng = dispatcher.rift_artifact_rng
        paired, recipient = candidates[rng.randrange(len(candidates))]
        if not dispatcher.native_area_events.assign_artifact(paired, recipient):
            changed |= reconcile_artifact_group(fight, group)
            continue
        group["remaining"] = [uid for uid in group["remaining"] if uid != paired]
        assignment = dict(request, opponent=paired, recipient=recipient)
        if before_wave is not None:
            assignment["before_wave"] = before_wave
        group["assignments"].append(assignment)
        pending.remove(request)
        changed = True
    if not pending:
        group.pop("pending_pairs", None)
    return changed
