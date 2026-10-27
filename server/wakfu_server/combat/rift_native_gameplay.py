"""Faithful shared rift producer reconstruction, on accepted combat previews.

Native Current Wave owns original scaling and death-orb subscriptions. The
missing server caller is reconstructed; no damage, probability or area effect
is replaced with a local formula.
"""

from wakfu_server.combat_definitions import state_profile
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state_handler import StateCarrierContext
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.rift_native_gameplay_policy import POLICY


def policy(fight):
    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return None
    document = state.get("policy", {}).get("native_gameplay")
    if document is None or document.get("enabled") is not True:
        return None
    if document.get("policy") != POLICY:
        raise ValueError("Unreviewed native rift producer policy")
    kinds = document.get("enabled_types")
    if (
        not isinstance(kinds, list)
        or not kinds
        or any(
            kind not in ("INFINITE_WAVE", "ULTIMATE_INFINITE_WAVE") for kind in kinds
        )
        or len(set(kinds)) != len(kinds)
    ):
        raise ValueError("Native rift gameplay requires its explicit type scope")
    if state.get("catalog", {}).get("type") not in kinds:
        return None
    return document


def apply_native_carrier(dispatcher, *, actor_id, reference, grade):
    """Apply an original indefinite state through the common retained runtime.

    Receipts and once-only admission belong to the caller's unpublished preview.
    This helper shares the existing native carrier construction, not stat math.
    """
    fight = dispatcher.native_retention.fight
    actor = fight.actors.get(actor_id)
    handler = dispatcher.native_state_handler
    definition = handler.catalog["states"].get(str(reference))
    if (
        actor is None
        or type(grade) is not int
        or grade < 1
        or definition is None
        or grade > definition["maximum_level"]
    ):
        raise ValueError("Native rift carrier requires its original actor and grade")
    profile = state_profile(handler.catalog, reference, grade)
    if profile["duration"] != -1 or profile["realtime_duration"] != 0:
        raise ValueError("Native rift carrier requires its original indefinite clock")
    if any(entry.reference == reference for entry in actor.state_ledger.entries):
        raise ValueError("Unattested native rift carrier already exists")
    invocation = EffectInvocation(
        2226,
        grade,
        actor_id,
        actor_id,
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
        reference,
        grade,
        carrier_context=context,
    ):
        raise ValueError("Native rift carrier was not installed")


def install_wave_state(dispatcher, *, actor_ids, wave):
    """Install the native wave carrier once on each newly admitted original NPC.

    The owner discards the entire preview/outbox on failure. Existing actors'
    states are never reinitialized when admitting later waves.
    """
    fight = dispatcher.native_retention.fight
    document = policy(fight)
    if document is None:
        return False
    from wakfu_server.combat_encounter_roles import assigned_roles

    state = fight.rift_wave_state
    npc_team = assigned_roles(fight).npc_team
    ids = tuple(actor_ids)
    receipts = state.setdefault("native_wave_entries", {})
    if wave == state["wave"]:
        expected = set(state["wave_actor_ids"])
    elif (
        isinstance(state.get("pending_wave"), dict)
        and wave == state["wave"] + 1
        and state["pending_wave"]["completed_wave"] == state["wave"]
    ):
        # The ordinary birth path registered the complete next roster before
        # acknowledgement updates wave_actor_ids. Every older original already
        # has an immutable entry receipt; summons never enter rift_monsters.
        expected = set(getattr(fight, "rift_monsters", {})) - {
            int(uid) for uid, entry in receipts.items() if entry["wave"] < wave
        }
    else:
        expected = set()
    if (
        type(wave) is not int
        or wave < 1
        or not ids
        or len(set(ids)) != len(ids)
        or set(ids) != expected
        or any(
            uid not in fight.actors
            or fight.actors[uid].controlled
            or fight.actors[uid].team != npc_team
            for uid in ids
        )
    ):
        raise ValueError("Native rift wave entry differs from its accepted roster")
    reference = document["wave_state"]
    if reference != 6807:
        raise ValueError("Native wave policy differs from original state6807")
    handler = dispatcher.native_state_handler
    definition = handler.catalog["states"].get(str(reference))
    if definition is None:
        raise ValueError("Missing original native rift wave state")
    grade = min(wave, definition["maximum_level"])
    profile = state_profile(handler.catalog, reference, grade)
    if profile["duration"] != -1 or profile["realtime_duration"] != 0:
        raise ValueError("Native wave carrier requires its original indefinite clock")
    changed = False
    for uid in ids:
        receipt = dict(reference=reference, level=grade, wave=wave, policy=POLICY)
        previous = receipts.get(str(uid))
        if previous is not None:
            if previous != receipt:
                raise ValueError(
                    "Native rift wave entry replay changed its original grade"
                )
            continue
        apply_native_carrier(
            dispatcher,
            actor_id=uid,
            reference=reference,
            grade=grade,
        )
        receipts[str(uid)] = receipt
        changed = True
    return changed


def register_artifact_group(fight, *, wave, area_uids):
    """Pin a real native choice group; never manufacture its areas or rewards."""
    document = policy(fight)
    if document is None or document.get("artifacts", {}).get("enabled") is not True:
        raise ValueError("Rift artifact production is not enabled")
    state = fight.rift_wave_state
    settings = document["artifacts"]
    count = settings[
        "ultimate_count"
        if state["catalog"]["type"] == "ULTIMATE_INFINITE_WAVE"
        else "classic_count"
    ]
    ids = tuple(area_uids)
    areas = getattr(fight, "native_effect_areas", {})
    allowed = {ref for pool in settings["pools"].values() for ref in pool}
    if (
        type(wave) is not int
        or wave < 1
        or type(count) is not int
        or count < 2
        or count % 2
        or len(ids) != count
        or len(set(ids)) != count
        or any(
            type(uid) is not int
            or uid <= 0
            or uid not in areas
            or areas[uid].get("native_area_contract") != "faM"
            or areas[uid]["reference"] not in allowed
            for uid in ids
        )
    ):
        raise ValueError("Missing actual native rift artifact choice group")
    groups = state.setdefault("native_artifact_groups", {})
    original = {str(uid): areas[uid]["reference"] for uid in ids}
    previous = groups.get(str(wave))
    if previous is not None:
        if previous["original"] != original:
            raise ValueError("Rift artifact group replay changed native identities")
        return previous
    if any(str(uid) in group["original"] for uid in ids for group in groups.values()):
        raise ValueError("Native rift artifact belongs to another choice group")
    group = dict(
        wave=wave,
        original=original,
        remaining=list(ids),
        assignments=[],
        choices_allowed=count // 2,
        choices_made=0,
    )
    groups[str(wave)] = group
    return group


def _artifact_group(fight, uid):
    groups = [
        group
        for group in fight.rift_wave_state.get("native_artifact_groups", {}).values()
        if str(uid) in group["original"]
    ]
    if len(groups) > 1:
        raise ValueError("Ambiguous native rift artifact choice group")
    return groups[0] if groups else None


def artifact_contact_eligible(fight, *, area_row, actor_id, criterion_probe=None):
    """Restrict only this producer's actual choices, before original contact."""
    document = policy(fight)
    if document is None or document.get("artifacts", {}).get("enabled") is not True:
        return True
    group = _artifact_group(fight, area_row["uid"])
    if group is None:
        return True  # Another native artifact producer retains its own rules.
    from wakfu_server.combat_encounter_roles import assigned_roles
    from wakfu_server.combat_carrying import carrying_relations

    actor = fight.actors.get(actor_id)
    eligible = bool(
        actor is not None
        and actor.controlled
        and fight._in_play(actor)
        and actor.team == assigned_roles(fight).player_team
        and actor_id not in getattr(fight, "native_summon_registrations", {})
        and not carrying_relations(fight, actor)["is_carried"]
        and area_row["uid"] in group["remaining"]
        and group["original"][str(area_row["uid"])] == area_row["reference"]
        and group["choices_made"] < group["choices_allowed"]
    )
    if not eligible or criterion_probe is None:
        return eligible
    if not callable(criterion_probe):
        raise ValueError("Native Rift contact criterion probe must be callable")
    permitted = criterion_probe()
    if type(permitted) is not bool:
        raise ValueError("Native Rift contact criterion probe must return bool")
    return permitted


def _artifact_representative(fight, team, *, area_uid, area_events):
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
    raise ValueError(
        "Native artifact team assignment requires an eligible living original fighter"
    )


def apply_artifact_collection(dispatcher, *, area_row, actor_id):
    """Pair a committed native contact with one real random opponent artifact.

    Native2243 applies its original team selector and304 effects. This callback
    neither grants statistics nor re-enters contact for automatic assignments.
    The caller owns preview rollback, including this receipt and transaction RNG.
    """
    fight = dispatcher.native_retention.fight
    document = policy(fight)
    if document is None or document.get("artifacts", {}).get("enabled") is not True:
        return False
    uid = area_row["uid"]
    group = _artifact_group(fight, uid)
    if group is None or uid not in group["remaining"]:
        return False
    # Admission ran before the original roots. Their damage may legitimately
    # retire the collector; authenticate their consumed receipt, not survival.
    receipt = getattr(fight, "native_artifact_activation_receipts", {}).get(str(uid))
    if (
        not isinstance(receipt, dict)
        or receipt.get("origin") != "contact"
        or receipt.get("complete") is not False
        or receipt.get("source_kind") != "observed_original_artifact_activation"
        or receipt.get("area_uid") != uid
        or receipt.get("area_level") != area_row["level"]
        or receipt.get("actor_id") != actor_id
        or receipt.get("reference") != area_row["reference"]
        or receipt.get("owner_id") != area_row["owner_id"]
        or group["original"].get(str(uid)) != area_row["reference"]
        or group["choices_made"] >= group["choices_allowed"]
        or uid in fight.native_effect_areas
    ):
        raise ValueError(
            "Rift choice requires the actual consumed native contact receipt"
        )
    remaining = [value for value in group["remaining"] if value != uid]
    if not remaining:
        raise ValueError("Rift artifact pair lost its remaining opponent choice")
    rng = getattr(dispatcher, "rift_artifact_rng", None)
    if not callable(getattr(rng, "randrange", None)):
        raise ValueError(
            "Rift artifact assignment requires the accepted transaction RNG"
        )
    from wakfu_server.combat_encounter_roles import assigned_roles

    paired = remaining[rng.randrange(len(remaining))]
    recipient = _artifact_representative(
        fight,
        assigned_roles(fight).npc_team,
        area_uid=paired,
        area_events=dispatcher.native_area_events,
    )
    group["remaining"] = [value for value in remaining if value != paired]
    group["choices_made"] += 1
    if not dispatcher.native_area_events.assign_artifact(paired, recipient):
        raise ValueError("Paired native rift artifact was not assigned")
    group["assignments"].append(
        dict(
            kind="contact_pair",
            collected=uid,
            collector=actor_id,
            opponent=paired,
            recipient=recipient,
        )
    )
    return True


def distribute_unclaimed_artifacts(dispatcher, *, before_wave):
    """Divide previous unchosen pairs across actual living teams, once.

    Invoke after successor NPC registration and before its first turn, so the
    opponent recipient is a real living native fighter rather than dead history.
    """
    fight = dispatcher.native_retention.fight
    document = policy(fight)
    if document is None or document.get("artifacts", {}).get("enabled") is not True:
        return False
    if type(before_wave) is not int or before_wave < 1:
        raise ValueError("Actual successor wave required for artifact distribution")
    from wakfu_server.combat_encounter_roles import assigned_roles

    roles = assigned_roles(fight)
    rng = getattr(dispatcher, "rift_artifact_rng", None)
    if not callable(getattr(rng, "randrange", None)):
        raise ValueError(
            "Rift artifact distribution requires the accepted transaction RNG"
        )
    changed = False
    for key, group in sorted(
        fight.rift_wave_state.get("native_artifact_groups", {}).items(),
        key=lambda item: int(item[0]),
    ):
        if int(key) >= before_wave or not group["remaining"]:
            continue
        if len(group["remaining"]) % 2:
            raise ValueError(
                "Unclaimed native rift artifacts lost their complete pairs"
            )
        while group["remaining"]:
            remaining = group["remaining"]
            selected = remaining.pop(rng.randrange(len(remaining)))
            paired = remaining.pop(rng.randrange(len(remaining)))
            player = _artifact_representative(
                fight,
                roles.player_team,
                area_uid=selected,
                area_events=dispatcher.native_area_events,
            )
            enemy = _artifact_representative(
                fight,
                roles.npc_team,
                area_uid=paired,
                area_events=dispatcher.native_area_events,
            )
            for uid, recipient in ((selected, player), (paired, enemy)):
                if not dispatcher.native_area_events.assign_artifact(uid, recipient):
                    raise ValueError(
                        "Unclaimed native rift artifact assignment was rejected"
                    )
            group["assignments"].append(
                dict(
                    kind="automatic_pair",
                    collected=selected,
                    collector=player,
                    opponent=paired,
                    recipient=enemy,
                    before_wave=before_wave,
                )
            )
            changed = True
    return changed
