#!/usr/bin/env python3
"""Real GUI casts: exact selection, server acceptance, client delivery and delta.

Start a legitimate fight first. This tool uses normal client input, never
injects game packets or resources. Authentication and captures remain private.
"""
import argparse, json, shutil, struct, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from gui_combat_verdict import (
    expected_changes,
    verdict,
    target_precondition,
    owned_action_precondition,
)
from gui_capture_tail import (
    CaptureTail,
    owned_delivery,
    native_cast_branch,
    native_item_branch,
)

ROOT = Path(__file__).resolve().parents[2]


class InvalidatedPrecondition(Exception):
    pass


def run(args):
    client_observation_limit = getattr(args, "client_observation_limit", 6)
    report = {
        "verdict": "OBSERVATION_ERROR",
        "expected": None,
        "before": {},
        "after": {},
        "requests": [],
        "server": None,
        "checks": [],
        "received_client_update": False,
        "execution_limit_seconds": args.execution_limit,
        "client_observation_limit_seconds": client_observation_limit,
        "api_observations": [],
        "evidence_scope": "actual client GUI, no simulation or packet injection",
    }
    deadline = time.monotonic() + args.timeout
    try:
        case = json.loads(args.case.read_text())
        report["expected"] = case
        if not case.get("expectations"):
            raise ValueError("At least one exact client expectation is required")
        branch_expectations = case.get("expectations_by_critical", {})
        if case.get("critical_policy") == "natural":
            if any(not branch_expectations.get(key) for key in ("false", "true")):
                raise ValueError(
                    "Natural critical sampling requires exact expectations for both native branches"
                )
        request_opcode = case.get("request_opcode", 13260)
        if request_opcode not in (13260, 12889):
            raise ValueError("Unsupported GUI request opcode")
        if "expected_critical" in case and type(case["expected_critical"]) is not bool:
            raise ValueError("expected_critical must be a boolean native branch")
        profile = ROOT / ".runtime/local/instances" / args.profile
        cfg = json.loads((profile / "inspector.json").read_text())

        def api(action, body=None):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("GUI observation deadline exceeded")
            req = urllib.request.Request(
                "http://127.0.0.1:%s/%s" % (cfg["port"], action),
                data=None if body is None else json.dumps(body).encode(),
                headers={"X-Inspector-Key": cfg["secret"]},
            )
            api_started = time.monotonic()
            with urllib.request.urlopen(req, timeout=min(remaining, 2)) as response:
                raw = response.read()
                if response.headers.get("Content-Type", "").startswith("image/"):
                    image = profile / "client-screen.png"
                    image.write_bytes(raw)
                    return str(image)
            report["api_observations"].append(
                dict(action=action, duration_seconds=time.monotonic() - api_started)
            )
            data = raw.decode()
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data.strip()

        ids = {case["actor_id"]} | {e["actor_id"] for e in case["expectations"]}
        if case.get("critical_policy") == "natural":
            ids |= {
                e["actor_id"]
                for entries in branch_expectations.values()
                for e in entries
            }

        def states():
            rows = {str(i): api("combat-actor", {"actor_id": str(i)}) for i in ids}
            if any(
                row.get("id") != int(identity)
                or not isinstance(row.get("stats"), dict)
                or not row.get("stats")
                or "position" not in row
                for identity, row in rows.items()
            ):
                raise ValueError("Required combat actor fields missing in client")
            return rows

        diagnostic = api("combat-diagnostic")
        report["client_preflight"] = diagnostic
        if (
            diagnostic.get("actor_owned") is not True
            or diagnostic.get("fight_phase") != "ACTION"
        ):
            raise ValueError("GUI fixture requires the owned actor ACTION turn")
        report["before"] = states()
        target_actor_id = case.get("target_actor_id")
        report["preconditions_verified"] = {
            "owned_action": True,
            "target_actor_current_cell": None,
        }
        if target_actor_id is not None:
            initial_target = api("combat-actor", {"actor_id": str(target_actor_id)})
            valid = target_precondition(initial_target, target_actor_id, case["target"])
            report["preconditions_verified"]["target_actor_current_cell"] = valid
            if not valid:
                raise InvalidatedPrecondition(
                    "Target actor was not alive at the expected cell before selection"
                )
        tail = CaptureTail(Path(cfg["capture"]) / "events.jsonl")
        tail.read()  # One baseline scan, then incremental reads only.
        logs = ROOT / ".runtime/local/logs/game-server.jsonl"
        with logs.open("rb") as stream:
            stream.seek(max(0, logs.stat().st_size - 65536))
            last = stream.read().splitlines()[-1]
        boot = json.loads(last)["server_boot_id"]
        report["server_boot_id"] = boot
        log_offset = logs.stat().st_size
        log_pending = b""
        server = []
        rows = []
        private = profile / ("gui-case-" + str(time.time_ns()))
        private.mkdir(mode=0o700)
        report["private_screenshots"] = str(private)
        shutil.copyfile(api("screen"), private / "before.png")
        # Observation API overhead before selection is excluded from cast latency.
        deadline = time.monotonic() + args.timeout
        anchor_mono = time.monotonic()
        anchor_utc = datetime.now(timezone.utc).timestamp()
        if "selection_key" in case:
            api("type", {"text": str(case["selection_key"]), "submit": False})
        else:
            api("click", dict(zip(("x", "y"), case["selection_click"])))
        current_turn = api("combat-diagnostic")
        if not owned_action_precondition(current_turn):
            raise InvalidatedPrecondition("Owned ACTION turn changed before targeting")
        if target_actor_id is not None:
            current_target = api("combat-actor", {"actor_id": str(target_actor_id)})
            if not target_precondition(current_target, target_actor_id, case["target"]):
                raise InvalidatedPrecondition(
                    "Target actor moved or died between selection and targeting"
                )
        point = api("project-cell", dict(zip(("x", "y", "z"), case["target"])))
        api("click", {"x": point["x"], "y": point["y"]})
        identity_key = "spell_id" if request_opcode == 13260 else "item_uid"
        expected = {k: case[k] for k in ("actor_id", identity_key, "target")}
        expected["request_opcode"] = request_opcode
        first_delta_utc = None
        while time.monotonic() < deadline:
            rows.extend(tail.read())
            requests = []
            for row in rows:
                if row["direction"] == "out" and row["opcode"] in (13260, 12889, 12366):
                    item = {k: row[k] for k in ("opcode", "frame", "time", "channel")}
                    if row["opcode"] == 13260 and len(row["body"]) == 26:
                        actor, uid, x, y, z = struct.unpack(">qqiih", row["body"])
                        item.update(
                            actor_id=actor, spell_id=uid & 0xFFFFFFFF, target=[x, y, z]
                        )
                    elif row["opcode"] == 12889 and len(row["body"]) == 27:
                        actor, uid, slot, x, y, z = struct.unpack(
                            ">qqbiih", row["body"]
                        )
                        item.update(
                            actor_id=actor, item_uid=uid, slot=slot, target=[x, y, z]
                        )
                    requests.append(item)
            report["requests"] = requests
            with logs.open("rb") as stream:
                stream.seek(log_offset)
                chunk = stream.read()
                log_offset = stream.tell()
            lines = (log_pending + chunk).split(b"\n")
            log_pending = lines.pop()
            server.extend(json.loads(line) for line in lines if line)
            finishes = [
                r
                for r in server
                if r.get("event") == "request_finished"
                and r.get("request_opcode") == request_opcode
                and r.get("state_before", {}).get("character", {}).get("id")
                == case["actor_id"]
            ]
            if len(finishes) > 1:
                requests.append({"opcode": "multiple_server_casts"})
            finished = None
            stages = []
            if len(finishes) == 1:
                source = finishes[0]
                if source.get("server_boot_id") != boot:
                    requests.append({"opcode": "server_boot_changed"})
                finished = {
                    k: source.get(k)
                    for k in (
                        "request_id",
                        "status",
                        "elapsed_ms",
                        "rejections",
                        "server_boot_id",
                    )
                }
                stages = [
                    r
                    for r in server
                    if r.get("request_id") == source["request_id"]
                    and r.get("server_boot_id") == boot
                    and (
                        r.get("event") == "combat_commit_stage"
                        or (
                            r.get("event") == "combat_melee_delivery"
                            and r.get("actor_id") == case["actor_id"]
                            and r.get("item_uid") == case.get("item_uid")
                            and r.get("target") == case["target"]
                        )
                    )
                ]
            report["server"] = finished
            critical_expected = case.get("expected_critical")
            active_expectations = case["expectations"]
            if case.get("critical_policy") == "natural" and finished is not None:
                decisions = [
                    r.get("critical_decision")
                    for r in server
                    if r.get("event") == "combat_cast"
                    and r.get("request_id") == finished["request_id"]
                    and r.get("server_boot_id") == boot
                    and r.get("actor_id") == case["actor_id"]
                    and r.get("spell_id") == case.get("spell_id")
                ]
                if (
                    len(decisions) == 1
                    and isinstance(decisions[0], dict)
                    and type(decisions[0].get("critical")) is bool
                ):
                    critical_expected = decisions[0]["critical"]
                    report["critical_decision"] = decisions[0]
                    active_expectations = case["expectations_by_critical"][
                        str(critical_expected).lower()
                    ]
            report["after"] = states()
            report["checks"] = expected_changes(
                report["before"], report["after"], active_expectations
            )
            if (
                first_delta_utc is None
                and report["checks"]
                and all(c["passed"] for c in report["checks"])
            ):
                # Inspector timestamps identify when the client state was read;
                # later log/capture processing must not extend delta latency.
                first_delta_utc = max(
                    datetime.fromisoformat(
                        report["after"][str(e["actor_id"])]["time"].replace(
                            "Z", "+00:00"
                        )
                    ).timestamp()
                    for e in active_expectations
                )
                report["first_exact_delta_utc"] = datetime.fromtimestamp(
                    first_delta_utc, timezone.utc
                ).isoformat()
            pairs = {
                (r["fight_id"], r["action_id"])
                for r in stages
                if "fight_id" in r and "action_id" in r
            }
            report["delivery_correlations"] = [
                dict(
                    fight_id=f,
                    action_id=a,
                    request_id=finished["request_id"],
                    boot_id=boot,
                )
                for f, a in pairs
            ]
            report["received_client_update"] = any(
                owned_delivery(row, fight_id=f, action_id=a, actor_ids=ids)
                for f, a in pairs
                for row in rows
            )
            critical_checks = None
            if "expected_critical" in case or case.get("critical_policy") == "natural":
                branches = [
                    (
                        native_cast_branch(
                            row,
                            fight_id=f,
                            action_id=a,
                            actor_id=case["actor_id"],
                            spell_id=case["spell_id"],
                            target=case["target"],
                        )
                        if request_opcode == 13260
                        else native_item_branch(
                            row,
                            fight_id=f,
                            action_id=a,
                            actor_id=case["actor_id"],
                            item_reference=case["item_reference"],
                            target=case["target"],
                        )
                    )
                    for f, a in pairs
                    for row in rows
                ]
                unique = {b["opcode"]: b for b in branches if b is not None}
                critical_checks = (
                    []
                    if critical_expected is None
                    else [
                        dict(
                            b,
                            passed=not b["failed"]
                            and b["critical"] is critical_expected,
                        )
                        for b in unique.values()
                    ]
                )
                report["critical_checks"] = critical_checks
            exact = [
                r
                for r in requests
                if r.get("actor_id") == expected["actor_id"]
                and r.get(identity_key) == expected[identity_key]
                and r.get("target") == expected["target"]
            ]
            elapsed = 0
            if len(exact) == 1:
                stamp = datetime.fromisoformat(
                    exact[0]["time"].replace("Z", "+00:00")
                ).timestamp()
                request_mono = anchor_mono + (stamp - anchor_utc)
                observed_mono = (
                    time.monotonic()
                    if first_delta_utc is None
                    else anchor_mono + (first_delta_utc - anchor_utc)
                )
                elapsed = max(0, observed_mono - request_mono)
                report["request_to_delta_observed_seconds"] = elapsed
                deliveries = [
                    row
                    for f, a in pairs
                    for row in rows
                    if owned_delivery(row, fight_id=f, action_id=a, actor_ids=ids)
                ]
                report["timings"] = dict(
                    server_execution_seconds=None
                    if finished is None
                    else finished.get("elapsed_ms", 0) / 1000,
                    request_to_wire_update_seconds=min(
                        (
                            datetime.fromisoformat(
                                row["time"].replace("Z", "+00:00")
                            ).timestamp()
                            - stamp
                            for row in deliveries
                        ),
                        default=None,
                    ),
                    request_to_client_observation_seconds=None
                    if first_delta_utc is None
                    else first_delta_utc - stamp,
                    elapsed_wait_seconds=elapsed,
                )
            result = verdict(
                requests=requests,
                expected=expected,
                server_finished=finished,
                checks=report["checks"],
                elapsed_seconds=elapsed,
                execution_limit_seconds=args.execution_limit,
                client_observation_limit_seconds=client_observation_limit,
                delivery_seen=report["received_client_update"],
                observation_complete=False,
                critical_checks=critical_checks,
            )
            report["verdict"] = result
            if result == "PASS" and case.get("critical_policy") == "natural":
                report["sample_verdict"] = (
                    "CRITICAL_SAMPLE_VALID"
                    if critical_expected
                    else "NORMAL_SAMPLE_VALID"
                )
            if result != "OBSERVING":
                break
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        if report["verdict"] == "OBSERVING":
            report["verdict"] = verdict(
                requests=report["requests"],
                expected=expected,
                server_finished=report["server"],
                checks=report["checks"],
                elapsed_seconds=report.get("request_to_delta_observed_seconds", 0),
                execution_limit_seconds=args.execution_limit,
                client_observation_limit_seconds=client_observation_limit,
                delivery_seen=report["received_client_update"],
                observation_complete=True,
                critical_checks=report.get("critical_checks"),
            )
        # Screenshots are optional after the verdict; never extend observation deadline.
        if time.monotonic() < deadline:
            shutil.copyfile(api("screen"), private / "after.png")
    except InvalidatedPrecondition as error:
        report["verdict"] = "INVALIDATED_PRECONDITION"
        report["precondition_error"] = str(error)
    except (ConnectionError, urllib.error.URLError) as error:
        report["verdict"] = "CLIENT_DISCONNECTED"
        report["observation_error"] = type(error).__name__
    except Exception as error:
        report["verdict"] = "OBSERVATION_ERROR"
        report["observation_error"] = str(error)
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"verdict": report["verdict"], "output": str(args.output)}))
    return 0 if report["verdict"] == "PASS" else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", required=True)
    p.add_argument("--case", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timeout", type=float, default=8)
    p.add_argument("--execution-limit", type=float, default=2)
    p.add_argument("--client-observation-limit", type=float, default=6)
    args = p.parse_args()
    if (
        args.timeout <= 0
        or args.execution_limit <= 0
        or args.client_observation_limit <= 0
    ):
        p.error("Timeouts must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
