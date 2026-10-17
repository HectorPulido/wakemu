"""Independent offline correlation of captured delivery bytes and mailbox state.

No delivery callback is executed. A returned socket call is an observed attempt,
never proof of client receipt or rendering. Missing history is not regenerated.
"""
from .combat_reproduction_state import decode_state
from .combat_shared import Session, Batch

SCHEMA = "wakemu-combat-delivery-verification-v1"
_SHARED = "wakemu-shared-combat-incident-v1"
_HISTORY = "wakemu-combat-delivery-history-v1"
_SIDECAR = "wakemu-combat-delivery-incident-v1"
_SESSION_FIELDS = {"account_id", "character_id", "generation", "map_id", "instance_id"}


class DeliveryEvidenceError(RuntimeError):
    """Evidence has an unsupported schema or cannot be safely interpreted."""


def _decode(value, label):
    try:
        return decode_state(value)
    except Exception as error:
        raise DeliveryEvidenceError(
            "Invalid typed delivery evidence: " + label
        ) from error


def _session(value):
    if type(value) is Session:
        value = {field: getattr(value, field) for field in _SESSION_FIELDS}
    if type(value) is not dict or set(value) != _SESSION_FIELDS:
        raise DeliveryEvidenceError("Invalid delivery session fields")
    if type(value["generation"]) is not str or any(
        type(value[field]) is not int for field in _SESSION_FIELDS - {"generation"}
    ):
        raise DeliveryEvidenceError("Invalid delivery session field types")
    return dict(value)


def _identity(session):
    return session["account_id"], session["generation"]


def _packets(value):
    if type(value) is not tuple or any(
        type(row) is not tuple
        or len(row) != 2
        or type(row[0]) is not int
        or type(row[1]) is not bytes
        for row in value
    ):
        raise DeliveryEvidenceError("Invalid ordered native packet evidence")
    return value


def _batches(value):
    if type(value) is not tuple:
        raise DeliveryEvidenceError("Ordered delivery batch tuple required")
    rows = []
    for batch in value:
        if type(batch) is Batch:
            sequence, packets = batch.sequence, batch.packets
        elif type(batch) is dict and set(batch) == {"sequence", "packets"}:
            sequence, packets = batch["sequence"], batch["packets"]
        else:
            raise DeliveryEvidenceError("Invalid typed mailbox batch")
        if type(sequence) is not int:
            raise DeliveryEvidenceError("Invalid mailbox sequence type")
        rows.append((sequence, _packets(packets)))
    return tuple(rows)


def _mailboxes(payload, label):
    if (
        type(payload) is not dict
        or payload.get("schema") != "wakemu-shared-combat-reproduction-v1"
    ):
        raise DeliveryEvidenceError("Unsupported expected shared state")
    state = _decode(payload.get("graph"), label)
    if (
        type(state) is not dict
        or not {"participants", "connected", "sequence", "outboxes"} <= state.keys()
    ):
        raise DeliveryEvidenceError("Shared mailbox projection is incomplete")
    if (
        type(state["participants"]) is not dict
        or type(state["outboxes"]) is not dict
        or type(state["connected"]) is not set
        or type(state["sequence"]) is not int
    ):
        raise DeliveryEvidenceError("Invalid shared mailbox field types")
    sessions = {
        account: _session(session) for account, session in state["participants"].items()
    }
    queues = {account: _batches(queue) for account, queue in state["outboxes"].items()}
    if any(
        type(account) is not int
        for account in (*sessions, *queues, *state["connected"])
    ):
        raise DeliveryEvidenceError("Mailbox account identities must be integers")
    fight_id = getattr(state.get("fight"), "id", None)
    if type(fight_id) is not int:
        raise DeliveryEvidenceError("Expected mailbox Fight identity required")
    return dict(
        fight_id=fight_id,
        participants=sessions,
        connected=state["connected"],
        sequence=state["sequence"],
        outboxes=queues,
    )


def verify_delivery_evidence(
    receipt, sidecars, *, expected_after=None, replay_outcome=None
):
    """Compare exact routing against recorded or explicit trusted mailbox state.

    Root replay callers should pass their actual ``capture_shared_state`` result
    as expected_after and their replay summary. Absent that state, this verifies
    recorded evidence consistency only. Findings contain paths, never raw bytes.
    """
    if type(receipt) is not dict or receipt.get("schema") != _SHARED:
        raise DeliveryEvidenceError("Unsupported shared incident schema")
    if type(sidecars) not in (list, tuple) or len(sidecars) > 128:
        raise DeliveryEvidenceError("Bounded materialized delivery sidecars required")
    before = _mailboxes(receipt.get("before"), "before")
    recorded = _mailboxes(receipt.get("after"), "after")
    after = (
        recorded
        if expected_after is None
        else _mailboxes(expected_after, "explicit-after")
    )
    findings, attempt_failures = [], []
    contradictions = [False]

    def find(code, path, severity="mismatch"):
        if severity in ("mismatch", "missing"):
            contradictions[0] = True
        if len(findings) < 256:
            findings.append(dict(code=code, path=path, severity=severity))

    mailbox_matches = recorded == after
    if not mailbox_matches:
        find("replayed_mailboxes_differ", "expected_after")
    correlation = receipt.get("delivery_correlation")
    if (
        type(correlation) is not dict
        or not {"process_boot_id", "fight_id", "before_sequence"} <= correlation.keys()
    ):
        find("delivery_correlation_missing", "delivery_correlation", "unknown")
        correlation = {}
    boot, fight_id = correlation.get("process_boot_id"), correlation.get("fight_id")
    if (
        boot is not None
        and type(boot) is not str
        or fight_id is not None
        and type(fight_id) is not int
    ):
        raise DeliveryEvidenceError("Invalid delivery correlation identity")
    if fight_id != before["fight_id"] or fight_id != after["fight_id"]:
        find("mailbox_fight_correlation_differs", "delivery_correlation")
    if correlation.get("before_sequence") != before["sequence"]:
        find("mailbox_sequence_correlation_differs", "delivery_correlation")
    history = None
    if receipt.get("preceding_delivery_history") is not None:
        history = _decode(receipt["preceding_delivery_history"], "preceding-history")
        if (
            type(history) is not dict
            or history.get("schema") != _HISTORY
            or type(history.get("streams")) is not tuple
        ):
            raise DeliveryEvidenceError("Unsupported preceding delivery history")
        if (
            history.get("process_boot_id") != boot
            or history.get("fight_id") != fight_id
        ):
            find("preceding_history_correlation_differs", "preceding_delivery_history")
    else:
        find("preceding_history_missing", "preceding_delivery_history", "unknown")

    targets = {}
    expected_sessions = {}
    expected_batches, expected_positions = {}, {}
    for account, queue in after["outboxes"].items():
        session = after["participants"].get(account)
        if session is None:
            find("mailbox_participant_missing", "after.outboxes." + str(account))
            continue
        if session["account_id"] != account:
            find("participant_account_differs", "after.participants." + str(account))
        expected_sessions[_identity(session)] = session
        for position, (sequence, packets) in enumerate(queue):
            key = (*_identity(session), sequence)
            if key in expected_batches:
                find(
                    "duplicate_expected_mailbox_sequence",
                    "after.outboxes." + str(account),
                )
            expected_batches[key] = packets
            expected_positions[key] = position
        old_session = before["participants"].get(account)
        prior = before["outboxes"].get(account, ()) if old_session == session else ()
        if queue[: len(prior)] != prior:
            find("preceding_mailbox_prefix_changed", "after.outboxes." + str(account))
            delta = queue
        else:
            delta = queue[len(prior) :]
        for sequence, packets in delta:
            key = (*_identity(session), sequence)
            if key in targets:
                find(
                    "duplicate_expected_batch_sequence",
                    "after.outboxes." + str(account),
                )
            targets[key] = packets

    bootstrap_by_session = {}
    history_complete = True
    relevant = {key[:2] for key in targets} or {
        _identity(session)
        for account, session in after["participants"].items()
        if account in after["connected"]
    }
    seen_streams = set()
    if history is not None:
        for index, stream in enumerate(history["streams"]):
            path = "history.streams[" + str(index) + "]"
            if (
                type(stream) is not dict
                or not {
                    "session",
                    "bootstrap",
                    "events",
                    "bootstrap_missing",
                    "history_gap",
                    "history_evicted",
                    "oversized",
                }
                <= stream.keys()
            ):
                raise DeliveryEvidenceError("Incomplete delivery stream history")
            session = _session(stream["session"])
            identity = _identity(session)
            if identity in seen_streams:
                find("duplicate_history_session", path)
            seen_streams.add(identity)
            if type(stream["events"]) is not tuple or any(
                type(stream[field]) is not bool
                for field in (
                    "bootstrap_missing",
                    "history_gap",
                    "history_evicted",
                    "oversized",
                )
            ):
                raise DeliveryEvidenceError("Invalid stream history field types")
            bootstrap = stream["bootstrap"]
            if bootstrap is not None:
                if type(bootstrap) is not dict or bootstrap.get("kind") != "bootstrap":
                    raise DeliveryEvidenceError("Invalid captured bootstrap event")
                bootstrap_by_session[identity] = _packets(bootstrap.get("packets"))
            if stream["bootstrap_missing"] != (bootstrap is None):
                find("bootstrap_availability_flag_differs", path)
            if identity in relevant:
                if expected_sessions.get(identity, session) != session:
                    find("history_session_identity_differs", path)
                if bootstrap is None:
                    find("bootstrap_missing", path, "unknown")
                    history_complete = False
                if (
                    stream["history_gap"]
                    or stream["history_evicted"]
                    or stream["oversized"]
                ):
                    find("preceding_stream_history_incomplete", path, "unknown")
                    history_complete = False
            last_id = -1
            pending = []
            for event_index, event in enumerate(stream["events"]):
                event_path = path + ".events[" + str(event_index) + "]"
                if (
                    type(event) is not dict
                    or type(event.get("observation_id")) is not int
                    or type(event.get("kind")) is not str
                ):
                    raise DeliveryEvidenceError("Invalid history observation event")
                if event["observation_id"] <= last_id:
                    find("history_observation_order_differs", event_path)
                last_id = event["observation_id"]
                kind = event["kind"]
                if kind == "evidence_gap":
                    find("history_explicit_gap", event_path, "unknown")
                    if identity in relevant:
                        history_complete = False
                if kind == "enqueue":
                    pending.extend(_batches(event.get("batches")))
                elif kind == "drain":
                    drained = _batches(event.get("batches"))
                    if (
                        not stream["history_gap"]
                        and bootstrap is not None
                        and tuple(pending[: len(drained)]) != drained
                    ):
                        find("history_drain_without_matching_enqueue", event_path)
                    if tuple(pending[: len(drained)]) == drained:
                        del pending[: len(drained)]
            if bootstrap is not None and bootstrap not in stream["events"]:
                find("bootstrap_event_missing_from_history", path)
    if relevant - seen_streams:
        history_complete = False
        find("recipient_history_missing", "preceding_delivery_history", "unknown")

    observed, seen_sidecars = {}, set()
    planned_batches, attempted_batches = set(), set()
    ordered_attempts = {}
    ordering_complete = True

    def verify_batch_list(identity, batches, path, seen, stage):
        positions = []
        for sequence, packets in batches:
            key = (*identity, sequence)
            if key not in expected_batches:
                find(stage + "_unknown_mailbox_batch", path)
            else:
                positions.append(expected_positions[key])
                if packets != expected_batches[key]:
                    find(stage + "_mailbox_batch_bytes_differ", path)
            if key in seen:
                find(stage + "_duplicate_mailbox_batch", path)
            seen.add(key)
        if positions and positions != list(
            range(positions[0], positions[0] + len(positions))
        ):
            find(stage + "_mailbox_batch_order_differs", path)

    planned_target_count = 0
    for sidecar_index, sidecar in enumerate(sidecars):
        path = "sidecars[" + str(sidecar_index) + "]"
        if type(sidecar) is not dict or sidecar.get("schema") != _SIDECAR:
            raise DeliveryEvidenceError("Unsupported delivery sidecar schema")
        if (
            sidecar.get("boundary")
            != "actual-delivery-callback-return-not-client-receipt"
        ):
            raise DeliveryEvidenceError("Unsupported delivery sidecar boundary")
        incident_id = sidecar.get("incident_id")
        if type(incident_id) is not str or not incident_id:
            raise DeliveryEvidenceError("Missing delivery sidecar identity")
        if incident_id in seen_sidecars:
            find("duplicate_sidecar", path)
        seen_sidecars.add(incident_id)
        if (
            sidecar.get("process_boot_id") != boot
            or sidecar.get("fight_id") != fight_id
        ):
            find("sidecar_boot_or_fight_differs", path)
            continue
        if sidecar.get("client_receipt_confirmed") is not False:
            find("unsupported_client_receipt_claim", path)
        plan, attempts = _decode(sidecar.get("plan"), path + ".plan"), _decode(
            sidecar.get("attempts"), path + ".attempts"
        )
        if type(plan) is not tuple or type(attempts) is not tuple:
            raise DeliveryEvidenceError("Ordered dispatch plan and attempts required")
        plan_sessions, attempt_sessions = {}, {}
        for plan_index, row in enumerate(plan):
            row_path = path + ".plan[" + str(plan_index) + "]"
            if type(row) is not dict or "session" not in row:
                raise DeliveryEvidenceError("Invalid dispatch plan row")
            session = _session(row["session"])
            identity = _identity(session)
            if identity in plan_sessions:
                find("duplicate_planned_recipient", row_path)
            plan_sessions[identity] = row
            expected_session = expected_sessions.get(identity)
            if expected_session != session:
                find("sidecar_session_generation_or_identity_differs", row_path)
            if "batches" in row:
                batches = _batches(row["batches"])
                verify_batch_list(
                    identity, batches, row_path, planned_batches, "planned"
                )
                for sequence, packets in batches:
                    key = (*identity, sequence)
                    if key in targets:
                        planned_target_count += 1
                        if packets != targets[key]:
                            find("planned_batch_bytes_differ", row_path)
            elif "packets" in row and row.get("sequence") is None:
                if bootstrap_by_session.get(identity) != _packets(row["packets"]):
                    find("direct_bootstrap_bytes_differ", row_path)
            else:
                raise DeliveryEvidenceError("Unknown delivery plan boundary")
        for attempt_index, row in enumerate(attempts):
            row_path = path + ".attempts[" + str(attempt_index) + "]"
            if (
                type(row) is not dict
                or not {"session", "status", "error"} <= row.keys()
            ):
                raise DeliveryEvidenceError("Invalid dispatch attempt row")
            session = _session(row["session"])
            identity = _identity(session)
            if identity in attempt_sessions:
                find("duplicate_recipient_attempt", row_path)
            attempt_sessions[identity] = row
            planned = plan_sessions.get(identity)
            payload = {
                key: value
                for key, value in row.items()
                if key not in ("status", "error", "observation_id", "ordinal_boundary")
            }
            if planned is None:
                find("unplanned_recipient_attempt", row_path)
            elif payload != planned:
                find("attempt_plan_bytes_or_order_differ", row_path)
            if row["status"] not in ("returned", "raised"):
                raise DeliveryEvidenceError("Unsupported delivery attempt status")
            if (row["status"] == "returned") != (row["error"] is None):
                find("attempt_status_error_differs", row_path)
            if row["error"] is not None:
                if (
                    type(row["error"]) is not dict
                    or type(row["error"].get("type")) is not str
                ):
                    raise DeliveryEvidenceError("Invalid delivery exception evidence")
                attempt_failures.append(
                    dict(path=row_path, exception_type=row["error"]["type"])
                )
            if "batches" in row:
                batches = _batches(row["batches"])
                verify_batch_list(
                    identity, batches, row_path, attempted_batches, "attempted"
                )
                ordinal = row.get("observation_id")
                if ordinal is None:
                    find("attempt_order_ordinal_missing", row_path, "unknown")
                    ordering_complete = False
                elif type(ordinal) is not int:
                    raise DeliveryEvidenceError("Invalid delivery attempt ordinal type")
                elif ordinal <= 0:
                    find("attempt_order_ordinal_invalid", row_path)
                elif (
                    row.get("ordinal_boundary")
                    != "serialized-registry-callback-completion"
                ):
                    find("attempt_order_boundary_unsupported", row_path, "unknown")
                    ordering_complete = False
                else:
                    ordered_attempts.setdefault(identity, []).append(
                        (ordinal, batches, row_path)
                    )
                for sequence, packets in batches:
                    key = (*identity, sequence)
                    if key in targets:
                        if key in observed:
                            find("duplicate_target_batch_attempt", row_path)
                        observed[key] = packets
                        if packets != targets[key]:
                            find("attempted_batch_bytes_differ", row_path)
        if plan_sessions.keys() - attempt_sessions.keys():
            find("planned_recipient_attempt_missing", path + ".attempts", "missing")
        elif tuple(plan_sessions) != tuple(attempt_sessions):
            find("dispatch_recipient_attempt_order_differs", path + ".attempts")
    if targets.keys() - observed.keys():
        find("target_batch_attempt_missing", "sidecars", "missing")
    for identity, attempts in ordered_attempts.items():
        prior_ordinal = prior_position = None
        for ordinal, batches, path in sorted(attempts, key=lambda attempt: attempt[0]):
            if ordinal == prior_ordinal:
                find("duplicate_stream_attempt_ordinal", path)
            positions = [
                expected_positions[(*identity, sequence)]
                for sequence, packets in batches
                if (*identity, sequence) in expected_positions
            ]
            if (
                positions
                and prior_position is not None
                and positions[0] <= prior_position
            ):
                find("cross_dispatch_mailbox_order_differs", path)
            if positions:
                prior_position = positions[-1]
            prior_ordinal = ordinal
    mismatches = contradictions[0]
    routing = not mismatches if targets else None
    replay_compared = (
        expected_after is not None
        and type(replay_outcome) is dict
        and replay_outcome.get("mailbox_matches") is True
    )
    if replay_outcome is not None and (
        type(replay_outcome) is not dict
        or replay_outcome.get("mailbox_matches") is not True
    ):
        find("mailbox_replay_not_verified", "replay_outcome", "unknown")
    bootstrap_qualified = (
        history_complete
        and bool(relevant)
        and not any(
            row["severity"] == "mismatch"
            and (
                row["path"].startswith("history")
                or row["path"].startswith("preceding_delivery_history")
                or row["path"] == "delivery_correlation"
            )
            for row in findings
        )
    )
    dispatch_qualified = bool(targets) and routing is True and ordering_complete
    return dict(
        schema=SCHEMA,
        matches=not mismatches,
        routing_matches=routing,
        mailbox_state_matches=mailbox_matches,
        replay_mailboxes_compared=replay_compared,
        explicit_expected_state_compared=expected_after is not None,
        expected_state_authority="explicit-caller-state"
        if expected_after is not None
        else "recorded-after-self-consistency-only",
        bootstrap_qualified=bootstrap_qualified,
        dispatch_qualified=dispatch_qualified,
        shared_delivery_qualified=replay_compared
        and bootstrap_qualified
        and dispatch_qualified,
        client_receipt_confirmed=False,
        client_reconstruction_verified=False,
        expected_batch_attempts=len(targets),
        observed_batch_attempts=len(observed),
        dispatch_order_qualified=bool(targets)
        and ordering_complete
        and routing is True,
        planned_target_batches=planned_target_count,
        attempt_failures=attempt_failures,
        findings=findings,
        qualification_boundary="captured-bootstrap-continuity-and-exact-mailbox-routing-with-observed-callback-attempts-only",
    )
