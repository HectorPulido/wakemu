"""Pure verdicts for real client cast evidence; simulation is never GUI proof."""


def expected_changes(before, after, expectations):
    checks = []
    for item in expectations:
        key = str(item["actor_id"])
        left, right = before.get(key), after.get(key)
        actual = None
        if left is not None and right is not None:
            # Optional getter errors do not erase successfully read fields.
            # Missing required characteristics still produce no expectation match.
            if item["kind"] in ("stat_delta", "stat_delta_one_of"):
                stat = str(item["stat_id"])
                if stat in left.get("stats", {}) and stat in right.get("stats", {}):
                    actual = right["stats"][stat] - left["stats"][stat]
            elif item["kind"] == "position":
                actual = right.get("position")
            else:
                raise ValueError("Unknown GUI expectation kind")
        wanted = item["value"]
        if item["kind"] == "stat_delta_one_of":
            if (
                not isinstance(wanted, list)
                or not wanted
                or any(type(v) is not int for v in wanted)
            ):
                raise ValueError(
                    "Native stochastic outcomes require explicit nonempty integer values"
                )
            passed = actual is not None and actual in wanted
        else:
            passed = actual == wanted and actual is not None
        checks.append(dict(expectation=item, actual=actual, passed=passed))
    return checks


def verdict(
    *,
    requests,
    expected,
    server_finished,
    checks,
    elapsed_seconds,
    execution_limit_seconds=2.0,
    client_observation_limit_seconds=2.0,
    delivery_seen=False,
    observation_complete=True,
    critical_checks=None
):
    opcode = expected.get("request_opcode", 13260)
    identity_key = "spell_id" if opcode == 13260 else "item_uid"
    matching = [
        r
        for r in requests
        if r.get("actor_id") == expected["actor_id"]
        and r.get(identity_key) == expected[identity_key]
        and r.get("target") == expected["target"]
        and r.get("opcode") == opcode
    ]
    # A second matching request is interference too: it could supply the delta.
    if len(requests) != len(matching) or len(matching) > 1:
        return "INVALIDATED_BY_INTERFERENCE"
    if not matching:
        return "BLOCKED_CLIENT" if observation_complete else "OBSERVING"
    if server_finished is None:
        return (
            "TIMEOUT_EXECUTION"
            if observation_complete or elapsed_seconds > execution_limit_seconds
            else "OBSERVING"
        )
    if (
        server_finished.get("rejections")
        or server_finished.get("status") != "completed"
    ):
        return "REJECTED_SERVER"
    if server_finished.get("elapsed_ms", 0) > execution_limit_seconds * 1000:
        return "TIMEOUT_EXECUTION"
    if elapsed_seconds > client_observation_limit_seconds:
        return "CLIENT_OBSERVATION_TIMEOUT"
    if not checks or not all(c["passed"] for c in checks):
        return "NO_EXPECTED_EFFECT" if observation_complete else "OBSERVING"
    if critical_checks is not None:
        if any(not c["passed"] for c in critical_checks):
            return "WRONG_CRITICAL_BRANCH"
        if len(critical_checks) != (2 if opcode == 13260 else 1):
            return "NO_CRITICAL_EVIDENCE" if observation_complete else "OBSERVING"
    if not delivery_seen:
        return "NO_CLIENT_DELIVERY" if observation_complete else "OBSERVING"
    return "PASS"


def target_precondition(actor, actor_id, cell):
    """Required native fields; missing evidence cannot certify a target."""
    return (
        actor.get("id") == actor_id
        and actor.get("position") == cell
        and actor.get("stats", {}).get("1", 0) > 0
    )


def owned_action_precondition(diagnostic):
    return (
        diagnostic.get("actor_owned") is True
        and diagnostic.get("fight_phase") == "ACTION"
    )
