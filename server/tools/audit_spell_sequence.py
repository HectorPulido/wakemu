"""Opt-in repeat-cast/end-turn audit; each boundary keeps its owned source private."""


PRECONDITION_REASONS = frozenset(
    (
        "Caster is not the owned active actor",
        "Spell UID belongs to another actor or expired grant",
        "Spell is absent from current deck",
        "Insufficient authoritative spell resources",
        "Spell target is outside verified terrain",
        "Spell target is outside native range",
        "Spell requires a straight line",
        "Spell target has no verified line of sight",
        "Spell requires an unoccupied target cell",
    )
)


def blocking_verdict(row, max_cast_seconds):
    """A later broken boundary must not be hidden by an accepted first cast."""
    if row["status"] in ("initialization_blocked", "cast_rejected"):
        return "blocked"
    steps = row.get("sequence", {}).get("steps", ())
    if any(step["status"] in ("REJECTED", "LIFECYCLE_FAILED") for step in steps):
        return "sequence_blocked"
    elapsed = row.get("cast_elapsed_seconds")
    if elapsed is not None and elapsed > max_cast_seconds:
        return "slow_execution"
    if row["status"] == "no_effect_observed" or any(
        step["status"] == "NO_EFFECT_OBSERVED" for step in steps
    ):
        return "no_effect_requires_review"
    return "client_validation_required"


def audit_sequence(
    first,
    *,
    actor_id,
    owner_id,
    preflight,
    cast,
    turn_end,
    rng,
    snapshot,
    target_id=None,
    target_cell=None,
    observe=None
):
    current = first.fight
    steps = []

    def changed(stage, reason):
        steps.append(dict(stage=stage, status="PRECONDITION_CHANGED", reason=reason))

    def live_turn(stage):
        actor = current.actors.get(actor_id)
        if current.phase != "active" or actor is None or actor.hp <= 0:
            changed(stage, "Fight is not active with a living owned caster")
            return False
        if (
            current.current is None
            or current.current.id != actor_id
            or actor.owner_id != owner_id
            or actor.controlled is not True
        ):
            changed(stage, "Owned caster no longer holds the turn")
            return False
        return True

    before_first = snapshot(current)
    second_ready = live_turn("second_cast")
    if second_ready and target_id is not None:
        target = current.actors.get(target_id)
        if target is None or target.hp <= 0:
            changed("second_cast", "Original target is no longer alive/present")
            second_ready = False
        elif target_cell is not None and target.position != target_cell:
            changed("second_cast", "Original target moved away from the requested cell")
            second_ready = False
    if second_ready:
        before = snapshot(current)
        rng_before = rng.getstate()
        # Preflight must use the common native validator. Its RNG inspection
        # is rolled back even on success so the actual cast sees the same draw.
        try:
            preflight(current)
        except ValueError as error:
            if type(error) is ValueError and str(error) in PRECONDITION_REASONS:
                changed("second_cast", str(error))
            else:
                steps.append(
                    dict(
                        stage="second_cast",
                        status="REJECTED",
                        reason=str(error),
                        error=type(error).__name__,
                    )
                )
        except Exception as error:
            steps.append(
                dict(
                    stage="second_cast",
                    status="REJECTED",
                    reason=str(error),
                    error=type(error).__name__,
                )
            )
        else:
            rng.setstate(rng_before)
            try:
                result = cast(current)
            except Exception as error:
                rng.setstate(rng_before)
                steps.append(
                    dict(
                        stage="second_cast",
                        status="REJECTED",
                        reason=str(error),
                        error=type(error).__name__,
                        effect_reference=getattr(error, "audit_reference", None),
                    )
                )
            else:
                next_fight = result.fight
                outcome = None if observe is None else observe(current, result)
                steps.append(
                    dict(
                        stage="second_cast",
                        status="NO_EFFECT_OBSERVED"
                        if outcome == "no_effect_observed"
                        else "EXECUTED",
                        outcome=outcome,
                        costs=result.plan["costs"],
                        events=list(result.events),
                        packet_opcodes=[op for op, _ in result.packets],
                        changed=snapshot(next_fight) != before,
                    )
                )
                current = next_fight
        finally:
            # Failed preflight is observational; an executed cast advances RNG.
            if not steps or steps[-1]["status"] not in (
                "EXECUTED",
                "NO_EFFECT_OBSERVED",
            ):
                rng.setstate(rng_before)
        steps[-1]["source_preserved"] = snapshot(first.fight) == before_first

    if live_turn("end_turn"):
        before = snapshot(current)
        rng_before = rng.getstate()
        try:
            preview, packets = turn_end(current)
            # prepare_server_turn_end delivers native end event on a copy;
            # production RuntimeMessages then advances the FSM/timers.
            preview.end_turn(owner_id, actor_id, preview.actors[actor_id].turn_count)
        except Exception as error:
            rng.setstate(rng_before)
            steps.append(
                dict(
                    stage="end_turn",
                    status="LIFECYCLE_FAILED",
                    reason=str(error),
                    error=type(error).__name__,
                    effect_reference=getattr(error, "audit_reference", None),
                    source_preserved=snapshot(current) == before,
                )
            )
        else:
            steps.append(
                dict(
                    stage="end_turn",
                    status="EXECUTED",
                    packet_opcodes=[op for op, _ in packets],
                    events=list(preview.events[len(current.events) :]),
                    changed=snapshot(preview) != before,
                    source_preserved=snapshot(current) == before,
                )
            )
            current = preview
    return dict(
        steps=steps,
        first_result_preserved=snapshot(first.fight) == before_first,
        source_resources={
            k: getattr(first.fight.actors[actor_id], k) for k in ("hp", "ap", "mp")
        },
        final_resources={
            k: getattr(current.actors[actor_id], k) for k in ("hp", "ap", "mp")
        },
    )
