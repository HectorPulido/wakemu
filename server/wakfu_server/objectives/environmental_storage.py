"""Durable environmental instances, authenticated facts and atomic rewards.

The caller owns session/account/character locks and the transaction. Event rows
serialize contributions; a catalog row never creates an enabled gameplay policy.
"""
from hashlib import sha256
import json

from psycopg.pq import TransactionStatus

from . import environmental_runtime as rules
from . import environmental_presence as presence


def _transaction(db):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Environmental operations require an owned transaction")


def _scope_lock(db, map_id, world_instance_id):
    # Owner locks precede this scope lock everywhere. It orders multi-profile
    # admission, expiry, roster binding and contribution across player owners.
    digest = sha256(f"environmental:{map_id}:{world_instance_id}".encode()).digest()
    db.execute(
        "SELECT pg_advisory_xact_lock(%s)",
        (int.from_bytes(digest[:8], "big", signed=True),),
    )


def _objectives(db, profile):
    from .environmental_evaluation import attach_policy

    attach_policy(db, profile)
    rows = db.execute(
        "SELECT * FROM environmental_profile_objectives WHERE profile_key=%s AND version=%s "
        "ORDER BY objective_key",
        (profile["profile_key"], profile["version"]),
    ).fetchall()
    from .environmental_collaborative_goal import target as collaborative_target

    shared_target = collaborative_target(db, profile)
    if shared_target is not None:
        if len(rows) != 1:
            raise ValueError("Collaborative minimum requires one shared objective")
        rows = [dict(rows[0], required_quantity=shared_target)]
    elif (
        profile.get("_event_instance_id") is not None
        and profile["mode"] == "collaborative"
        and profile["family"] in ("monster_defeat", "group_defeat", "monster_destroy")
    ):
        from .environmental_random_rosters import frozen_birth_count

        entity = "group" if profile["family"] == "group_defeat" else "monster"
        quantity = frozen_birth_count(
            db, {"instance_id": profile["_event_instance_id"]}, entity
        )
        if quantity is not None:
            if len(rows) != 1:
                raise ValueError(
                    "Random environmental population requires one shared objective"
                )
            rows = [dict(rows[0], required_quantity=quantity)]
    return rules.validate_profile(profile, rows)


def _event_profile(db, event):
    row = db.execute(
        "SELECT * FROM environmental_runtime_profiles WHERE profile_key=%s AND version=%s",
        (event["profile_key"], event["version"]),
    ).fetchone()
    if row is None or not row["sealed"]:
        raise ValueError("Missing frozen environmental profile")
    return dict(row, _event_instance_id=event["instance_id"])


def _outbox(db, event, participant, kind, now_ms):
    key = f"environmental:{event['instance_id']}:{participant['character_id']}:{kind}:{event['revision']}"
    db.execute(
        "INSERT INTO environmental_publication_outbox "
        "(delivery_key,instance_id,character_id,account_id,kind,revision,created_at_ms) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(delivery_key) DO NOTHING",
        (
            key,
            event["instance_id"],
            participant["character_id"],
            participant["account_id"],
            kind,
            event["revision"],
            now_ms,
        ),
    )


def register_memberships(db, instance_id, memberships):
    """Bind exact server-spawned identities; templates/breeds alone never join."""
    _transaction(db)
    scope = db.execute(
        "SELECT map_id,world_instance_id FROM environmental_event_instances WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if scope is None:
        raise ValueError("Missing environmental roster instance")
    occupied = presence.capture(scope["map_id"], scope["world_instance_id"])
    if occupied is None:
        return False
    _scope_lock(db, scope["map_id"], scope["world_instance_id"])
    if not presence.current(occupied, scope["map_id"], scope["world_instance_id"]):
        return False
    event = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if event is None or event["state"] not in ("proposed", "active"):
        raise ValueError("Environmental roster requires an admitted event")
    for row in memberships:
        if (
            type(row) is not dict
            or row.get("entity_kind") not in ("monster", "group", "resource")
            or type(row.get("entity_id")) is not int
            or row["entity_id"] == 0
            or not -(2**63) <= row["entity_id"] < 2**63
            or type(row.get("reference")) is not int
            or row["reference"] <= 0
            or type(row.get("source_key")) is not str
            or not 1 <= len(row["source_key"]) <= 200
            or type(row.get("spawn_owned", False)) is not bool
        ):
            raise ValueError("Invalid qualified environmental membership")
        values = (
            instance_id,
            row["entity_kind"],
            row["entity_id"],
            row["reference"],
            row["source_key"],
            row.get("spawn_owned", False),
        )
        db.execute(
            "INSERT INTO environmental_event_memberships(instance_id,entity_kind,entity_id,reference,source_key,spawn_owned) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            values,
        )
        previous = db.execute(
            "SELECT reference,source_key,spawn_owned FROM environmental_event_memberships "
            "WHERE instance_id=%s AND entity_kind=%s AND entity_id=%s",
            values[:3],
        ).fetchone()
        if (
            previous["reference"],
            previous["source_key"],
            previous["spawn_owned"],
        ) != values[3:]:
            raise ValueError("Frozen environmental membership changed")


def _queue_cleanup(db, event, now_ms):
    # Membership in an event does not mean the event owns the wild entity.
    db.execute(
        "INSERT INTO environmental_cleanup_outbox "
        "(instance_id,entity_kind,entity_id,reference,source_key,action,requested_at_ms) "
        "SELECT instance_id,entity_kind,entity_id,reference,source_key,"
        "CASE WHEN spawn_owned THEN 'despawn_owned' ELSE 'release_membership' END,%s "
        "FROM environmental_event_memberships WHERE instance_id=%s ON CONFLICT DO NOTHING",
        (now_ms, event["instance_id"]),
    )


def cancel(db, instance_id, *, reason, now_ms):
    """A server controller cancels its event; earned entitlements are retained."""
    _transaction(db)
    rules.integer(now_ms, "cancellation clock")
    if type(reason) is not str or not 1 <= len(reason) <= 200:
        raise ValueError("Missing environmental cancellation reason")
    scope = db.execute(
        "SELECT map_id,world_instance_id FROM environmental_event_instances WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if scope is None:
        raise ValueError("Missing environmental cancellation instance")
    occupied = presence.capture(scope["map_id"], scope["world_instance_id"])
    if occupied is None:
        return False
    _scope_lock(db, scope["map_id"], scope["world_instance_id"])
    if not presence.current(occupied, scope["map_id"], scope["world_instance_id"]):
        return False
    event = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if event["state"] == "cancelled":
        if event["cancel_reason"] != reason:
            raise ValueError("Environmental cancellation source changed on replay")
        return False
    if event["state"] not in ("proposed", "active"):
        return False
    event = db.execute(
        "UPDATE environmental_event_instances SET state='cancelled',cancel_reason=%s,"
        "terminal_at_ms=%s,revision=revision+1 WHERE instance_id=%s RETURNING *",
        (reason, now_ms, instance_id),
    ).fetchone()
    _queue_cleanup(db, event, now_ms)
    for participant in db.execute(
        "SELECT * FROM environmental_participants WHERE instance_id=%s", (instance_id,)
    ).fetchall():
        _outbox(db, event, participant, "expired", now_ms)
    return True


def _progress(db, event, character_id=None):
    if character_id is None:
        return {
            row["objective_key"]: row["quantity"]
            for row in db.execute(
                "SELECT objective_key,sum(quantity)::bigint AS quantity FROM environmental_shared_actions "
                "WHERE instance_id=%s GROUP BY objective_key",
                (event["instance_id"],),
            ).fetchall()
        }
    suffix, args = (
        ("", ()) if character_id is None else (" AND character_id=%s", (character_id,))
    )
    return {
        row["objective_key"]: row["quantity"]
        for row in db.execute(
            "SELECT objective_key,sum(quantity)::bigint AS quantity FROM environmental_progress "
            "WHERE instance_id=%s" + suffix + " GROUP BY objective_key",
            (event["instance_id"], *args),
        ).fetchall()
    }


def _entitle(db, event, participant, now_ms):
    from . import environmental_companion_rewards

    row = db.execute(
        "INSERT INTO environmental_reward_entitlements(instance_id,character_id,account_id,earned_at_ms) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT(instance_id,character_id) DO NOTHING RETURNING entitlement_id",
        (
            event["instance_id"],
            participant["character_id"],
            participant["account_id"],
            now_ms,
        ),
    ).fetchone()
    if row is None:
        return
    from .environmental_reward_bands import reward_components

    ranked = reward_components(db, event, _event_profile(db, event), participant)
    if ranked is None:
        db.execute(
            "INSERT INTO environmental_reward_components "
            "(entitlement_id,ordinal,kind,reference,quantity,source_authority) "
            "SELECT %s,ordinal,kind,reference,quantity,source_authority FROM environmental_profile_rewards "
            "WHERE profile_key=%s AND version=%s ORDER BY ordinal",
            (row["entitlement_id"], event["profile_key"], event["version"]),
        )
    else:
        if not ranked:
            raise ValueError("Environmental entitlement lacks its ranked reward")
        for component in ranked:
            db.execute(
                "INSERT INTO environmental_reward_components "
                "(entitlement_id,ordinal,kind,reference,quantity,source_authority) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    row["entitlement_id"],
                    component["ordinal"],
                    component["kind"],
                    component["reference"],
                    component["quantity"],
                    component["source_authority"],
                ),
            )
    from .environmental_xp import freeze as freeze_xp

    freeze_xp(db, row["entitlement_id"])
    environmental_companion_rewards.freeze(
        db,
        entitlement_id=row["entitlement_id"],
        account_id=participant["account_id"],
        character_id=participant["character_id"],
        completed_at_ms=now_ms,
    )
    db.execute(
        "UPDATE environmental_participants SET completed_at_ms=%s "
        "WHERE instance_id=%s AND character_id=%s",
        (now_ms, event["instance_id"], participant["character_id"]),
    )
    _outbox(db, event, participant, "completed", now_ms)


def contribute(db, fact, *, shared_completions=None, record_entities_only=False):
    """Consume one committed fact in the gameplay transaction, exactly once."""
    from .environmental_gameplay import GameplayFact

    _transaction(db)
    if type(fact) is not GameplayFact:
        raise ValueError(
            "Environmental progress requires an authenticated gameplay fact"
        )
    occupied = presence.capture(fact.map_id, fact.instance_id)
    if occupied is None:
        return ()
    values = rules.fact_values(fact)
    digest = sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    _scope_lock(db, fact.map_id, fact.instance_id)
    if not presence.current(occupied, fact.map_id, fact.instance_id):
        return ()
    candidates = db.execute(
        "SELECT e.* FROM environmental_event_instances e JOIN environmental_participants p "
        "ON p.instance_id=e.instance_id WHERE e.map_id=%s AND e.world_instance_id=%s "
        "AND e.region_id IS NOT DISTINCT FROM %s AND e.state='active' AND p.eligible "
        "AND p.account_id=%s AND p.character_id=%s AND p.completed_at_ms IS NULL "
        "AND p.joined_at_ms<=%s AND e.started_at_ms<=%s AND e.deadline_ms>%s "
        "ORDER BY e.instance_id FOR UPDATE OF e",
        (
            fact.map_id,
            fact.instance_id,
            fact.region_id,
            fact.account_id,
            fact.character_id,
            fact.occurred_at_ms,
            fact.occurred_at_ms,
            fact.occurred_at_ms,
        ),
    ).fetchall()
    changes = []
    for event in candidates:
        profile = _event_profile(db, event)
        if record_entities_only and profile["family"] not in (
            "monster_defeat",
            "group_defeat",
            "monster_destroy",
        ):
            continue
        membership = db.execute(
            "SELECT * FROM environmental_event_memberships WHERE instance_id=%s AND entity_kind=%s AND entity_id=%s",
            (event["instance_id"], fact.entity_kind, fact.entity_id),
        ).fetchone()
        entity_changed = False
        if profile["family"] in ("monster_defeat", "group_defeat"):
            from .environmental_group_progress import record

            entity_changed = record(db, event, profile, fact, membership)
        elif profile["family"] == "monster_destroy":
            from .environmental_monster_destroy import record

            entity_changed = record(db, event, profile, fact, membership)
        if record_entities_only:
            if entity_changed:
                event = db.execute(
                    "UPDATE environmental_event_instances SET revision=revision+1 "
                    "WHERE instance_id=%s RETURNING *",
                    (event["instance_id"],),
                ).fetchone()
                for participant in db.execute(
                    "SELECT * FROM environmental_participants WHERE instance_id=%s ORDER BY character_id",
                    (event["instance_id"],),
                ).fetchall():
                    _outbox(db, event, participant, "progress", fact.occurred_at_ms)
            continue
        objectives = _objectives(db, profile)
        personal = _progress(db, event, fact.character_id)
        progress = (
            _progress(db, event) if profile["mode"] == "collaborative" else personal
        )
        changed = entity_changed
        for objective in objectives:
            increment = rules.objective_increment(
                objective, fact, membership=membership
            )
            if increment == 0:
                continue
            identity = (
                event["instance_id"],
                fact.character_id,
                objective["objective_key"],
                fact.receipt_key,
                fact.entity_kind,
                fact.entity_id,
            )
            previous = db.execute(
                "SELECT fact_digest FROM environmental_fact_receipts WHERE instance_id=%s "
                "AND character_id=%s AND objective_key=%s AND receipt_key=%s AND entity_kind=%s AND entity_id=%s",
                identity,
            ).fetchone()
            if previous is not None:
                if previous["fact_digest"] != digest:
                    raise ValueError("Committed environmental fact changed on replay")
                continue
            current = progress.get(objective["objective_key"], 0)
            # Shared completion has a target, but a participant's actual
            # contribution can exceed its remaining gap in one committed
            # action. Truncating that action could wrongly deny eligibility.
            actual = (
                increment
                if profile["mode"] in ("collaborative", "competitive")
                else rules.advance_progress(
                    current, increment, objective["required_quantity"]
                )
                - current
            )
            rules.integer(current + actual, "accumulated contribution")
            if actual == 0:
                continue
            db.execute(
                "INSERT INTO environmental_fact_receipts "
                "(instance_id,character_id,objective_key,receipt_key,entity_kind,entity_id,fact_digest,quantity,occurred_at_ms) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (*identity, digest, actual, fact.occurred_at_ms),
            )
            db.execute(
                "INSERT INTO environmental_progress(instance_id,character_id,objective_key,quantity) "
                "VALUES(%s,%s,%s,%s) ON CONFLICT(instance_id,character_id,objective_key) "
                "DO UPDATE SET quantity=environmental_progress.quantity+EXCLUDED.quantity",
                (
                    event["instance_id"],
                    fact.character_id,
                    objective["objective_key"],
                    actual,
                ),
            )
            # Each winning owner has its own authenticated receipt. The
            # physical encounter/action advances the shared objective once.
            shared_values = {
                key: value
                for key, value in values.items()
                if key not in ("account_id", "character_id", "occurred_at_ms")
            }
            shared_digest = sha256(
                json.dumps(
                    shared_values, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            shared_identity = (
                event["instance_id"],
                objective["objective_key"],
                fact.receipt_key,
                fact.entity_kind,
                fact.entity_id,
            )
            inserted = db.execute(
                "INSERT INTO environmental_shared_actions "
                "(instance_id,objective_key,receipt_key,entity_kind,entity_id,fact_digest,quantity,occurred_at_ms) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING quantity",
                (*shared_identity, shared_digest, increment, fact.occurred_at_ms),
            ).fetchone()
            previous_shared = db.execute(
                "SELECT fact_digest,quantity FROM environmental_shared_actions WHERE instance_id=%s "
                "AND objective_key=%s AND receipt_key=%s AND entity_kind=%s AND entity_id=%s",
                shared_identity,
            ).fetchone()
            if (previous_shared["fact_digest"], previous_shared["quantity"]) != (
                shared_digest,
                increment,
            ):
                raise ValueError(
                    "Shared environmental action changed between participants"
                )
            if profile["mode"] == "collaborative":
                progress[objective["objective_key"]] = current + (
                    increment if inserted is not None else 0
                )
            else:
                progress[objective["objective_key"]] = current + actual
            changed = True
        if not changed:
            continue
        event = db.execute(
            "UPDATE environmental_event_instances SET revision=revision+1 WHERE instance_id=%s RETURNING *",
            (event["instance_id"],),
        ).fetchone()
        if profile["mode"] == "collaborative":
            if shared_completions is None:
                finish_shared(db, event["instance_id"], now_ms=fact.occurred_at_ms)
            else:
                shared_completions[event["instance_id"]] = max(
                    shared_completions.get(event["instance_id"], 0), fact.occurred_at_ms
                )
            changes.append(
                dict(
                    instance_id=event["instance_id"],
                    revision=event["revision"],
                    progress=progress,
                )
            )
            continue
        participants = db.execute(
            "SELECT * FROM environmental_participants WHERE instance_id=%s ORDER BY character_id",
            (event["instance_id"],),
        ).fetchall()
        if profile["mode"] != "competitive" and rules.complete(objectives, progress):
            for participant in participants:
                if (
                    not participant["eligible"]
                    or participant["completed_at_ms"] is not None
                ):
                    continue
                if (
                    profile["mode"] in ("solo", "race")
                    and participant["character_id"] != fact.character_id
                ):
                    continue
                earned = sum(_progress(db, event, participant["character_id"]).values())
                if earned >= profile["minimum_contribution"]:
                    if profile["mode"] == "race":
                        from .environmental_evaluation import race_finish

                        event = race_finish(
                            db, event, profile, participant, earned, fact.occurred_at_ms
                        )
                    else:
                        _entitle(db, event, participant, fact.occurred_at_ms)
        for participant in participants:
            _outbox(db, event, participant, "progress", fact.occurred_at_ms)
        changes.append(
            dict(
                instance_id=event["instance_id"],
                revision=event["revision"],
                progress=progress,
            )
        )
    return tuple(changes)


def finish_shared(db, instance_id, *, now_ms):
    """Finalize after every owner in one settled action has received credit."""
    _transaction(db)
    scope = db.execute(
        "SELECT map_id,world_instance_id FROM environmental_event_instances WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    if scope is None:
        raise ValueError("Missing shared environmental event")
    occupied = presence.capture(scope["map_id"], scope["world_instance_id"])
    if occupied is None:
        return
    _scope_lock(db, scope["map_id"], scope["world_instance_id"])
    if not presence.current(occupied, scope["map_id"], scope["world_instance_id"]):
        return
    event = db.execute(
        "SELECT * FROM environmental_event_instances WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    if event["state"] != "active":
        return
    profile = _event_profile(db, event)
    if profile["mode"] != "collaborative":
        return
    objectives = _objectives(db, profile)
    participants = db.execute(
        "SELECT * FROM environmental_participants WHERE instance_id=%s ORDER BY character_id",
        (instance_id,),
    ).fetchall()
    if rules.complete(objectives, _progress(db, event)):
        event = db.execute(
            "UPDATE environmental_event_instances SET state='completed',terminal_at_ms=%s "
            "WHERE instance_id=%s RETURNING *",
            (now_ms, instance_id),
        ).fetchone()
        _queue_cleanup(db, event, now_ms)
        for participant in participants:
            if (
                participant["eligible"]
                and participant["completed_at_ms"] is None
                and sum(_progress(db, event, participant["character_id"]).values())
                >= profile["minimum_contribution"]
            ):
                _entitle(db, event, participant, now_ms)
    for participant in participants:
        _outbox(db, event, participant, "progress", now_ms)


def _view(db, event, profile, participant, now_ms):
    progress = _progress(
        db,
        event,
        None if profile["mode"] == "collaborative" else participant["character_id"],
    )
    state = (
        "completed" if participant["completed_at_ms"] is not None else event["state"]
    )
    countdown = event["started_at_ms"] if state == "proposed" else event["deadline_ms"]
    publication = db.execute(
        "SELECT * FROM environmental_profile_publication WHERE profile_key=%s AND version=%s",
        (profile["profile_key"], profile["version"]),
    ).fetchone()
    variables = []
    if publication is not None:
        status = db.execute(
            "SELECT state_ordinal FROM environmental_profile_publication_states "
            "WHERE profile_key=%s AND version=%s AND lifecycle_state=%s",
            (profile["profile_key"], profile["version"], state),
        ).fetchone()
        if status is None:
            raise ValueError("Missing qualified environmental publication state")
        rows = db.execute(
            "SELECT * FROM environmental_profile_variables WHERE profile_key=%s AND version=%s ORDER BY variable_index",
            (profile["profile_key"], profile["version"]),
        ).fetchall()
        publication = dict(
            publication,
            state_ordinal=status["state_ordinal"],
            variable_names=[row["name"] for row in rows],
            native_time=publication["native_time"]
            if publication["time_mode"] == "constant"
            else rules.remaining_ms(countdown, now_ms),
        )
        variables = [
            dict(
                variable_index=row["variable_index"],
                value=row["constant_value"]
                if row["objective_key"] is None
                else progress.get(row["objective_key"], 0),
            )
            for row in rows
        ]
        from .environmental_native_variables import project

        projected = project(db, event, profile, participant, now_ms)
        if projected is not None:
            publication["variable_names"] = [row["name"] for row in projected]
            variables = [
                dict(variable_index=row["variable_index"], value=row["value"])
                for row in projected
            ]
    active_objectives = []
    if publication is not None:
        active_objectives = [
            row["objective_id"]
            for row in db.execute(
                """SELECT o.objective_id
            FROM environmental_profile_native_variable_policy p
            JOIN environmental_native_objectives o ON o.source_key=p.source_key
              AND o.scenario_id=p.native_scenario_id
            WHERE p.profile_key=%s AND p.version=%s AND p.native_scenario_id=%s
              AND o.client_visible ORDER BY o.objective_id""",
                (
                    profile["profile_key"],
                    profile["version"],
                    profile["native_scenario_id"],
                ),
            ).fetchall()
        ]
    live_rank = None
    challenge_value = sum(progress.values())
    if profile["mode"] == "competitive":
        from .environmental_evaluation import competitive_ranking

        ranking = competitive_ranking(db, event, profile)
        # Native ICU is the ranking denominator, not the contribution counter.
        challenge_value = len(ranking)
        if event["state"] == "active":
            live_rank = next(
                (
                    row["display_rank"]
                    for row in ranking
                    if row["character_id"] == participant["character_id"]
                ),
                -1,
            )
    native_result = None
    if participant["completed_at_ms"] is not None and profile["mode"] in (
        "race",
        "competitive",
    ):
        from .environmental_reward_bands import native_result_mapping

        native_result = native_result_mapping(db, event, profile, participant)
    elif participant["completed_at_ms"] is not None and profile["mode"] in (
        "solo",
        "collaborative",
    ):
        from .environmental_simple_results import project

        native_result = project(db, event, profile, participant, now_ms)
    # The native popup reads a global XP factor, not an amount in 13263.
    # Completed owners retain the earned policy even after operators change it.
    # Historical entitlements without pricing metadata keep their original x1.
    if participant["completed_at_ms"] is not None:
        rates = db.execute(
            "SELECT DISTINCT r.xp_rate_bp FROM environmental_reward_entitlements e "
            "JOIN environmental_entitlement_xp_rates r USING(entitlement_id) "
            "WHERE e.instance_id=%s AND e.character_id=%s AND e.account_id=%s "
            "AND r.character_id=e.character_id AND r.account_id=e.account_id "
            "AND r.earned_at_ms=e.earned_at_ms",
            (
                event["instance_id"],
                participant["character_id"],
                participant["account_id"],
            ),
        ).fetchall()
        if len(rates) > 1:
            raise ValueError("Environmental display has inconsistent earned XP rates")
        xp_rate_bp = rates[0]["xp_rate_bp"] if rates else 10000
    else:
        rate = db.execute(
            "SELECT v.xp_rate_bp FROM combat_reward_policy_active a "
            "JOIN combat_reward_policy_versions v USING(version) WHERE a.singleton"
        ).fetchone()
        if rate is None:
            raise ValueError("Missing canonical XP presentation rate")
        xp_rate_bp = rate["xp_rate_bp"]
    return dict(
        event,
        xp_rate_bp=xp_rate_bp,
        native_scenario_id=profile["native_scenario_id"],
        native_result=native_result,
        protector_id=None if publication is None else publication["protector_id"],
        now_ms=now_ms,
        countdown_deadline_ms=countdown,
        challenge_value=challenge_value,
        live_rank=live_rank,
        available=state in ("proposed", "active"),
        variables=variables,
        active_objectives=active_objectives,
        native_publication=publication,
    )


def refresh(db, *, account_id, character_id, location, now_ms, groups=None):
    """Resume instances and admit eligible owners only through enabled profiles."""
    _transaction(db)
    occupied = presence.capture(location["map_id"], location["instance_id"])
    if occupied is None:
        return dict(instances=[], deliveries=[], inactive_scope=True)
    _scope_lock(db, location["map_id"], location["instance_id"])
    if not presence.current(occupied, location["map_id"], location["instance_id"]):
        return dict(instances=[], deliveries=[], inactive_scope=True)
    expired = db.execute(
        "UPDATE environmental_event_instances SET state='expired',terminal_at_ms=deadline_ms,revision=revision+1 "
        "WHERE map_id=%s AND world_instance_id=%s AND state IN ('proposed','active') AND deadline_ms<=%s RETURNING *",
        (location["map_id"], location["instance_id"], now_ms),
    ).fetchall()
    for event in expired:
        profile = _event_profile(db, event)
        if profile["mode"] == "competitive":
            from .environmental_evaluation import competition_finish

            event = competition_finish(db, event, profile, now_ms)
        _queue_cleanup(db, event, now_ms)
        for participant in db.execute(
            "SELECT * FROM environmental_participants WHERE instance_id=%s",
            (event["instance_id"],),
        ).fetchall():
            _outbox(db, event, participant, "expired", now_ms)
    for event in db.execute(
        "UPDATE environmental_event_instances SET state='active',revision=revision+1 "
        "WHERE map_id=%s AND world_instance_id=%s AND state='proposed' AND started_at_ms<=%s "
        "AND deadline_ms>%s RETURNING *",
        (location["map_id"], location["instance_id"], now_ms, now_ms),
    ).fetchall():
        for participant in db.execute(
            "SELECT * FROM environmental_participants WHERE instance_id=%s",
            (event["instance_id"],),
        ).fetchall():
            _outbox(db, event, participant, "snapshot", now_ms)
    from . import environmental_schedule

    from .environmental_resource_placement import POLICY as mapwide_resource_policy

    # A genuine admitted map-wide resource event retains its original region
    # identity while its participant explores the rest of the same map. This
    # never enrolls another region's event or broadens ordinary ecology credit.
    pinned = db.execute(
        "SELECT e.* FROM environmental_event_instances e "
        "JOIN environmental_participants p USING(instance_id) "
        "JOIN environmental_runtime_profiles r ON "
        "(r.profile_key,r.version)=(e.profile_key,e.version) "
        "WHERE p.account_id=%s AND p.character_id=%s AND p.eligible "
        "AND e.map_id=%s AND e.world_instance_id=%s "
        "AND e.state IN ('proposed','active') AND e.deadline_ms>%s "
        "AND r.family='resource_collect' AND r.sealed "
        "AND EXISTS(SELECT 1 FROM environmental_owned_resources o "
        "JOIN environmental_event_memberships m ON "
        "(m.instance_id,m.entity_kind,m.entity_id)="
        "(o.instance_id,o.entity_kind,o.resource_uid) "
        "WHERE o.instance_id=e.instance_id AND o.map_id=e.map_id "
        "AND o.world_instance_id=e.world_instance_id AND m.spawn_owned "
        "AND m.entity_kind='resource' AND m.reference=o.reference "
        "AND split_part(m.source_key,':',3) ~ '^(0|[1-9][0-9]*)$' "
        "AND m.source_key='event-resource:'||e.instance_id::text||':'||"
        "split_part(m.source_key,':',3)||':'||%s) ORDER BY e.instance_id",
        (
            account_id,
            character_id,
            location["map_id"],
            location["instance_id"],
            now_ms,
            mapwide_resource_policy,
        ),
    ).fetchall()
    if len(pinned) > 1:
        raise ValueError("Multiple admitted map-wide resource events are ambiguous")
    scheduled = bool(pinned) or environmental_schedule.scheduled_scope(db, location)
    selected = (
        pinned[0]
        if pinned
        else environmental_schedule.select_event(db, location=location, now_ms=now_ms)
        if scheduled
        else None
    )
    if not presence.current(occupied, location["map_id"], location["instance_id"]):
        return dict(instances=[], deliveries=[], inactive_scope=True)
    level = db.execute(
        "SELECT level FROM characters WHERE id=%s AND account_id=%s",
        (character_id, account_id),
    ).fetchone()
    if level is None:
        raise ValueError("Missing environmental participant owner")
    profiles = (
        ([] if selected is None else [_event_profile(db, selected)])
        if scheduled
        else db.execute(
            "SELECT * FROM environmental_runtime_profiles WHERE enabled AND sealed AND map_id=%s "
            "AND region_id=%s ORDER BY profile_key,version",
            (location["map_id"], location["region_id"]),
        ).fetchall()
    )
    for profile in profiles:
        _objectives(db, profile)
        if not profile["level_min"] <= level["level"] <= profile["level_max"]:
            continue
        if scheduled:
            event = selected
        else:
            window = rules.admission_window(
                now_ms,
                duration_ms=profile["duration_ms"],
                anchor_ms=profile["anchor_ms"],
                recurrence_period_ms=profile["recurrence_period_ms"],
                proposal_ms=profile["proposal_ms"],
            )
            if window is None:
                continue
            cycle, starts, deadline, state = window
            event = db.execute(
                "SELECT * FROM environmental_event_instances WHERE profile_key=%s AND version=%s "
                "AND map_id=%s AND world_instance_id=%s AND cycle_key=%s FOR UPDATE",
                (
                    profile["profile_key"],
                    profile["version"],
                    location["map_id"],
                    location["instance_id"],
                    cycle,
                ),
            ).fetchone()
            if event is None:
                from .environmental_location_criteria import profile_eligible

                if not profile_eligible(
                    db, profile, world_instance_id=location["instance_id"]
                ):
                    continue
                db.execute(
                    "INSERT INTO environmental_event_instances "
                    "(profile_key,version,map_id,world_instance_id,region_id,cycle_key,started_at_ms,deadline_ms,state) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (
                        profile["profile_key"],
                        profile["version"],
                        location["map_id"],
                        location["instance_id"],
                        location["region_id"],
                        cycle,
                        starts,
                        deadline,
                        state,
                    ),
                )
                event = db.execute(
                    "SELECT * FROM environmental_event_instances WHERE profile_key=%s AND version=%s "
                    "AND map_id=%s AND world_instance_id=%s AND cycle_key=%s FOR UPDATE",
                    (
                        profile["profile_key"],
                        profile["version"],
                        location["map_id"],
                        location["instance_id"],
                        cycle,
                    ),
                ).fetchone()
        if event["state"] not in ("proposed", "active"):
            continue
        db.execute(
            "INSERT INTO environmental_participants(instance_id,character_id,account_id,joined_at_ms) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (event["instance_id"], character_id, account_id, now_ms),
        )
        if profile["family"] in ("group_defeat", "monster_defeat", "monster_destroy"):
            from .environmental_groups import bind_available

            if groups is not None:
                from .environmental_group_population import populate

                populate(db, event, groups, now_ms=now_ms)
            if profile["family"] != "monster_destroy":
                bind_available(db, event)
        elif profile["family"] == "resource_collect":
            from .environmental_resource_population import populate

            populate(db, event, now_ms=now_ms)
    instances = []
    for event in db.execute(
        "SELECT e.* FROM environmental_event_instances e JOIN environmental_participants p USING(instance_id) "
        "WHERE p.account_id=%s AND p.character_id=%s AND e.map_id=%s AND e.world_instance_id=%s "
        "AND (e.region_id IS NOT DISTINCT FROM %s OR e.instance_id=%s) "
        "AND e.deadline_ms>%s AND (%s=false OR e.instance_id=%s) ORDER BY e.instance_id",
        (
            account_id,
            character_id,
            location["map_id"],
            location["instance_id"],
            location["region_id"],
            pinned[0]["instance_id"] if pinned else None,
            now_ms,
            scheduled,
            None if selected is None else selected["instance_id"],
        ),
    ).fetchall():
        participant = db.execute(
            "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
            (event["instance_id"], character_id),
        ).fetchone()
        instances.append(
            _view(db, event, _event_profile(db, event), participant, now_ms)
        )
    deliveries = [
        dict(row, packets=[])
        for row in db.execute(
            "SELECT * FROM environmental_publication_outbox WHERE account_id=%s AND character_id=%s "
            "AND acknowledged_at_ms IS NULL ORDER BY delivery_id",
            (account_id, character_id),
        ).fetchall()
    ]
    return dict(instances=instances, deliveries=deliveries)


def claim_pending(db, store, *, account_id, character_id, now_ms):
    """Claim each completion atomically; capacity failure leaves all parts pending."""
    from wakfu_server.achievements import rewards
    from . import environmental_companion_rewards

    _transaction(db)
    delivered, blocked = [], []
    for entitlement in db.execute(
        "SELECT * FROM environmental_reward_entitlements WHERE account_id=%s AND character_id=%s "
        "AND claimed_at_ms IS NULL ORDER BY entitlement_id FOR UPDATE",
        (account_id, character_id),
    ).fetchall():
        try:
            with db.transaction():
                character = store.character(account_id, character_id, db)
                before = db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (character_id,),
                ).fetchone()["xp"]
                components = db.execute(
                    "SELECT * FROM environmental_reward_components WHERE entitlement_id=%s ORDER BY ordinal",
                    (entitlement["entitlement_id"],),
                ).fetchall()
                kamas = 0
                for component in components:
                    if component["kind"] == "kamas":
                        amount = component["quantity"]
                        if (
                            db.execute(
                                "UPDATE account_wallets SET kamas=kamas+%s WHERE account_id=%s AND kamas<=%s RETURNING kamas",
                                (amount, account_id, 2**63 - 1 - amount),
                            ).fetchone()
                            is None
                        ):
                            raise ValueError(
                                "Missing or overflowing environmental wallet"
                            )
                        kamas += amount
                    elif component["kind"] == "xp":
                        from .environmental_xp import award as award_xp

                        award_xp(db, store, character, component)
                    else:
                        parameters = (
                            [component["reference"], component["quantity"]]
                            if component["kind"] == "item"
                            else [component["quantity"]]
                        )
                        # Notifications are reconstructed as absolute state by
                        # the service; additive XP/item messages are not replayed.
                        rewards.grant(
                            db,
                            store,
                            character,
                            dict(
                                aeV=5 if component["kind"] == "item" else 6,
                                ckl=parameters,
                            ),
                        )
                after = db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (character_id,),
                ).fetchone()["xp"]
                environmental_companion_rewards.grant(
                    db,
                    store,
                    entitlement_id=entitlement["entitlement_id"],
                    account_id=account_id,
                    character_id=character_id,
                    owner_xp=after - before,
                )
                db.execute(
                    "INSERT INTO environmental_claim_receipts(entitlement_id,account_id,character_id,claimed_at_ms,owner_xp,kamas,component_count) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (
                        entitlement["entitlement_id"],
                        account_id,
                        character_id,
                        now_ms,
                        after - before,
                        kamas,
                        len(components),
                    ),
                )
                db.execute(
                    "UPDATE environmental_reward_entitlements SET claimed_at_ms=%s WHERE entitlement_id=%s",
                    (now_ms, entitlement["entitlement_id"]),
                )
                event = db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (entitlement["instance_id"],),
                ).fetchone()
                _outbox(db, event, entitlement, "claimed", now_ms)
        except rewards.RewardCapacity:
            blocked.append(entitlement["entitlement_id"])
            continue
        delivered.append(entitlement["entitlement_id"])
    character = store.character(account_id, character_id, db) if delivered else None
    return dict(delivered=delivered, capacity_pending=blocked, character=character)


def acknowledge(db, *, account_id, character_id, delivery_keys, now_ms=None):
    _transaction(db)
    if now_ms is None:
        now_ms = db.execute(
            "SELECT (extract(epoch FROM clock_timestamp())*1000)::bigint AS now"
        ).fetchone()["now"]
    return db.execute(
        "UPDATE environmental_publication_outbox SET acknowledged_at_ms=%s "
        "WHERE account_id=%s AND character_id=%s AND delivery_key=ANY(%s) AND acknowledged_at_ms IS NULL",
        (now_ms, account_id, character_id, list(delivery_keys)),
    ).rowcount
