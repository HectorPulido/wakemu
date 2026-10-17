#!/usr/bin/env python3
"""Record isolated requests and replay bundles without client or service writes.

Use a fresh process for each replay so engine indexes are built from the pinned
catalog. ``samples`` demonstrates the workflow using existing native fixtures;
``record`` accepts a request captured with combat_reproduction.capture_request.
"""
import argparse
from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path
import random
import struct
import sys

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))


def _summary(name, case, result):
    from wakfu_server.combat_reproduction import compare_expectation

    return {
        "case": name,
        "status": result["status"],
        "result_sha256": result["sha256"],
        "source_matches": result["source_matches"],
        "source_sha256": result["source_sha256"],
        "catalog_matches": result["catalog_matches"],
        "catalog_revision": result["catalog_revision"],
        "boundary": case["boundary"],
        **compare_expectation(case, result),
    }


def _record(request, output):
    from wakfu_server.combat_reproduction_catalog import CaptureCatalog
    from wakfu_server.combat_reproduction import (
        read_case,
        execute_case,
        record_expectation,
        write_case,
        bind_catalog_bundle,
    )

    case = read_case(request)
    with CaptureCatalog() as catalog:
        result = execute_case(case)
        record_expectation(case, result)
    catalog.export(output)
    bind_catalog_bundle(case, output)
    write_case(output / "case.json", case)
    return _summary("case.json", case, result)


def _record_incident(request, output, provider_recipe, allow_source_drift):
    from wakfu_server.combat_reproduction_catalog import CaptureCatalog
    from wakfu_server.combat_incident_replay import (
        read_incident,
        replay_runtime_incident,
        bind_incident_bundle,
        write_incident,
    )

    receipt = read_incident(request)
    with CaptureCatalog() as catalog:
        result = replay_runtime_incident(
            receipt,
            provider_recipe=provider_recipe,
            allow_source_drift=allow_source_drift,
        )
    catalog.export(output)
    bind_incident_bundle(receipt, output)
    write_incident(output / "incident.json", receipt)
    return result


def _read_delivery_sidecars(paths):
    """Load bounded private evidence; the trusted verifier checks its schema."""
    from wakfu_server.combat_reproduction_state import MAX_BYTES

    if len(paths) > 128:
        raise ValueError("Delivery sidecar count exceeds bound")
    sidecars, total = [], 0
    for path in paths:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        total += len(raw)
        if len(raw) > MAX_BYTES or total > 256 * 1024 * 1024:
            raise ValueError("Delivery sidecars exceed size bound")
        sidecars.append(json.loads(raw))
    return sidecars


def _invariant_plan(document, *, incident=False):
    """Require only markers installed at the actual requested boundary."""
    from wakfu_server.combat_reproduction_state import decode_state

    commits = {"player_spell", "player_weapon", "player_unarmed", "npc_spell"}
    if incident:
        schema = document.get("schema")
        if schema == "wakemu-combat-npc-publication-v1":
            return "npc_publication", ("Registry.execute_server",), None
        if schema == "wakemu-combat-npc-incident-v1":
            return (
                "npc_chosen_action",
                (),
                "Private NativeOracle commit has no invariant marker",
            )
        if schema == "wakemu-shared-combat-incident-v1":
            request = decode_state(document["request"])
            if request["type"] != "execute":
                return request["type"], (), "Collective ACK has no invariant marker"
            required = ["Registry.execute"]
            operations = document.get("operations", [])
            action = decode_state(operations[0])["action"] if operations else {}
            if action.get("type") in commits:
                required.append("commit_spell_transaction")
            return action.get("type", "shared_execute"), tuple(required), None
    action = decode_state(document["before"])["action"]
    operation = action.get("type", "unknown")
    if operation in commits:
        return operation, ("commit_spell_transaction",), None
    return operation, (), "This isolated runtime action has no invariant marker"


def _invariant_resource_authority():
    """Read explicit offline evidence before entering the operation input tape."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.combat_reproduction_catalog import MissingReproductionCatalog
    from wakfu_server.combat_invariant_resources import ResourceAuthority

    documents = (
        "native-actor-characteristics.json",
        "native-class-copy-characteristics.json",
    )
    try:
        actor_bytes, copy_bytes = (
            native_catalog.read_bytes(DATA_ROOT / name) for name in documents
        )
        hashes = native_catalog.document_hashes()
        authority = ResourceAuthority.from_documents(
            revision=native_catalog.release(),
            actor_bytes=actor_bytes,
            copy_bytes=copy_bytes,
            actor_sha256=hashes[documents[0]],
            copy_sha256=hashes[documents[1]],
        )
    except MissingReproductionCatalog:
        return None, dict(
            status="missing",
            documents=list(documents),
            reason="Resource documents were not captured in this offline bundle",
        )
    except Exception as error:
        return None, dict(
            status="error",
            documents=list(documents),
            reason="Resource authority verification failed: " + type(error).__name__,
        )
    return authority, dict(status="verified", **authority.as_dict())


@contextmanager
def _checked_invariant_scope():
    from wakfu_server.combat_invariant_observation import invariant_observation_scope

    authority, metadata = _invariant_resource_authority()
    with invariant_observation_scope(resource_authority=authority) as observation:
        observation._cli_resource_authority = metadata
        yield observation


def _invariant_scope(enabled):
    if not enabled:
        return nullcontext(None)
    return _checked_invariant_scope()


def _invariant_summary(observation, plan):
    operation, required, unsupported = plan
    reports = [report.as_dict() for report in observation.reports]
    observed = sorted({report["operation"] for report in reports})
    missing = [name for name in required if name not in observed]
    findings = [finding for report in reports for finding in report["findings"]]
    violations = sum(finding["status"] == "violation" for finding in findings)
    unknown = sum(finding["status"] == "unknown" for finding in findings)
    authority_input = getattr(observation, "_cli_resource_authority", None)
    authority_failed = (
        authority_input is not None and authority_input["status"] == "error"
    )
    if authority_input is not None and authority_input["status"] != "verified":
        unknown += 1
    checker_failed = any(
        finding["invariant"] == "checker.failed" for finding in findings
    )
    dropped = observation._dropped
    truncated = dropped > 0 or any(
        finding["invariant"] == "coverage.limit" for finding in findings
    )
    complete = (
        observation.complete
        and bool(reports)
        and not missing
        and unsupported is None
        and not authority_failed
    )
    status = (
        "violations"
        if violations
        else "incomplete"
        if not complete
        else "partial_coverage"
        if unknown
        else "checked_available_invariants"
    )
    return dict(
        operation=operation,
        reports=reports,
        expected_markers=list(required),
        observed_operations=observed,
        missing_markers=missing,
        missing_boundary=not reports or bool(missing),
        unsupported_boundary=unsupported,
        collection_complete=observation.complete,
        complete=complete,
        truncated=truncated,
        dropped_reports=dropped,
        checker_failed=checker_failed,
        violation_count=violations,
        unknown_count=unknown,
        status=status,
        qualified=complete and not violations and not unknown,
        full_coverage=False,
        coverage_scope="available_declared_invariants_only",
        resource_authority_input=authority_input,
    )


def _invariant_exit_code(code, diagnostics):
    if diagnostics["violation_count"]:
        return 1
    if not diagnostics["complete"]:
        return 2
    return code


def _samples(output):
    from wakfu_server.combat_reproduction_catalog import CaptureCatalog
    from wakfu_server.combat_reproduction import (
        capture_request,
        execute_case,
        record_expectation,
        write_case,
        read_case,
        bind_catalog_bundle,
    )

    summaries = []
    clocks = {"wall_time_ns": 1700000000000000000, "monotonic_ns": 123000000000}
    with CaptureCatalog() as catalog:
        sys.path.insert(0, str(SERVER / "tests"))
        import test_combat_reproduction_actions as fixtures
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_reproduction_state import decode_state

        fixture = fixtures.ReproductionActionTests()
        for name in (
            "player-spell",
            "rejected-spell",
            "movement",
            "end-turn",
            "pending-ack",
            "npc-spell",
            "feca-peace-armor",
            "feca-granted-teleport",
        ):
            is_feca = name.startswith("feca-")
            runtime, inputs = (
                fixture.fixture(1, 200, (6972,)) if is_feca else fixture.fixture()
            )
            policies = {
                "WAKFU_NATIVE_AREA_CALLBACKS": "1",
                "WAKFU_NATIVE_GRANTED_CAST": "1"
                if is_feca
                else os.environ.get("WAKFU_NATIVE_GRANTED_CAST", "0"),
            }
            target = runtime.fight.actors[-7].position
            action = dict(
                type="player_spell",
                owner_id=3,
                critical=None,
                body=struct.pack(">qqiih", 7, (7 << 32) | 6266, *target),
            )
            if name == "rejected-spell":
                action["body"] = b"malformed-native-cast"
            elif is_feca:
                from wakfu_server.combat_spell_grant import granted_spells

                spell = granted_spells(runtime.fight, 7)[7009]["uid"]
                action["critical"] = False
                action["body"] = struct.pack(
                    ">qqiih", 7, spell, *runtime.fight.actors[7].position
                )
                if name == "feca-granted-teleport":
                    preparation = capture_request(
                        runtime,
                        action,
                        inputs,
                        random.Random(42),
                        clocks=clocks,
                        policies=policies,
                    )
                    runtime = decode_state(execute_case(preparation)["result"])[
                        "runtime"
                    ]
                    uid = granted_spells(runtime.fight, 7)[7052]["uid"]
                    from tools.class_spell_eligible_targets import eligible_cast_targets
                    from wakfu_server.combat_server_spell import server_runtime
                    from wakfu_server.combat_los import authoritative_visible
                    from wakfu_server.combat_reproduction import controlled_environment

                    with controlled_environment(clocks, policies):
                        _, adapter = server_runtime(
                            inputs["character"],
                            inputs["monsters"],
                            inputs["deck_blob"],
                            action_id=runtime.action_id + 1,
                            critical=False,
                            rng=random.Random(42),
                            player_characters=inputs["player_characters"],
                            deck_blobs=inputs["deck_blobs"],
                        )
                        selection = eligible_cast_targets(
                            runtime.fight,
                            inputs["character"],
                            inputs["deck_blob"],
                            uid,
                            adapter=adapter,
                            actor_id=7,
                            limit=512,
                            maximum_eligible=1,
                            line_of_sight=lambda origin, cell, fight: authoritative_visible(
                                inputs["map_id"],
                                origin,
                                cell,
                                fight,
                                blocking_footprints={
                                    actor.id: {actor.position[:2]}
                                    for actor in fight.actors.values()
                                    if actor.hp > 0
                                },
                            ),
                        )
                    if not selection["eligible"]:
                        raise ValueError(
                            "No validated target for the granted teleport sample"
                        )
                    destination = tuple(selection["eligible"][0]["target"])
                    action["body"] = struct.pack(">qqiih", 7, uid, *destination)
            elif name == "movement":
                origin = runtime.fight.actors[7].position
                destination = next(
                    cell
                    for cell in sorted(runtime.fight.walkable)
                    if cell != target
                    and (origin, cell) in runtime.fight.edges
                    and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) == 1
                )
                action = dict(
                    type="move", owner_id=3, body=struct.pack(">qiih", 7, *destination)
                )
            elif name in ("end-turn", "pending-ack", "npc-spell"):
                action = dict(
                    type="end_turn",
                    owner_id=3,
                    actor_id=7,
                    turn_id=current_wire_turn(runtime.fight),
                )
                if name != "end-turn":
                    preparation = capture_request(
                        runtime, action, inputs, random.Random(42), clocks=clocks
                    )
                    ended = decode_state(execute_case(preparation)["result"])
                    runtime = ended["runtime"]
                    action = dict(
                        type="ack", body=struct.pack(">i", runtime.awaiting_ack)
                    )
                    if name == "npc-spell":
                        preparation = capture_request(
                            runtime, action, inputs, random.Random(42), clocks=clocks
                        )
                        runtime = decode_state(execute_case(preparation)["result"])[
                            "runtime"
                        ]
                        from wakfu_server.combat_npc_spell import owned_spells

                        spells = owned_spells(
                            runtime.fight,
                            inputs["monsters"],
                            character=inputs["character"],
                            player_characters=inputs["player_characters"],
                        )
                        spell, level = next(iter(spells.items()))
                        action = dict(
                            type="npc_spell",
                            action=dict(
                                type="cast",
                                spellId=spell,
                                level=level,
                                targetId=7,
                                target=runtime.fight.actors[7].position,
                            ),
                        )
            case = capture_request(
                runtime,
                action,
                inputs,
                random.Random(42),
                clocks=clocks,
                recipients=(3,),
                policies=policies,
            )
            result = execute_case(case)
            record_expectation(case, result)
            write_case(output / (name + ".json"), case)
            summaries.append(_summary(name + ".json", case, result))
    catalog.export(output)
    for summary in summaries:
        path = output / summary["case"]
        write_case(path, bind_catalog_bundle(read_case(path), output))
    (output / "index.json").write_text(
        json.dumps(
            {
                "schema": "wakemu-combat-reproduction-index-v1",
                "scope": "native-fixture-demonstrations-not-live-incident-captures",
                "cases": summaries,
            },
            indent=2,
        )
        + "\n"
    )
    return {"cases": summaries, "catalog": "catalog.json"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser(
        "record", help="Execute and record a captured request using published catalogs"
    )
    record.add_argument("--request", required=True, type=Path)
    record.add_argument("--output", required=True, type=Path)
    samples = commands.add_parser(
        "samples", help="Create representative native fixture bundles"
    )
    samples.add_argument("--output", required=True, type=Path)
    record_incident = commands.add_parser(
        "record-incident",
        help="Compare an automatically captured operation and export its offline catalog",
    )
    record_incident.add_argument("--request", required=True, type=Path)
    record_incident.add_argument("--output", required=True, type=Path)
    record_incident.add_argument(
        "--provider-recipe",
        required=True,
        choices=[
            "ordinary-server-runtime-v1",
            "observed-live-server-v1",
            "native-oracle-chosen-action-v1",
            "native-npc-publication-v1",
        ],
    )
    record_incident.add_argument("--allow-source-drift", action="store_true")
    replay = commands.add_parser(
        "replay", help="Replay a bundle in this fresh process with no catalog services"
    )
    replay.add_argument("--bundle", required=True, type=Path)
    replay.add_argument("--case", default="case.json")
    replay.add_argument(
        "--allow-source-drift",
        action="store_true",
        help="Explicitly compare changed engine sources or Python against captured behavior",
    )
    replay.add_argument("--output", type=Path)
    replay.add_argument(
        "--check-invariants",
        action="store_true",
        help="Observe available pre-adoption invariants during replay; report coverage separately from the recorded outcome",
    )
    replay_incident = commands.add_parser(
        "replay-incident",
        help="Replay observed operation evidence from an exported catalog",
    )
    replay_incident.add_argument("--bundle", required=True, type=Path)
    replay_incident.add_argument("--receipt", default="incident.json")
    replay_incident.add_argument(
        "--provider-recipe",
        required=True,
        choices=[
            "ordinary-server-runtime-v1",
            "observed-live-server-v1",
            "native-oracle-chosen-action-v1",
            "native-npc-publication-v1",
        ],
    )
    replay_incident.add_argument("--allow-source-drift", action="store_true")
    replay_incident.add_argument("--output", type=Path)
    replay_incident.add_argument(
        "--check-invariants",
        action="store_true",
        help="Observe available pre-adoption invariants during actual incident execution; does not enforce gameplay",
    )
    replay_incident.add_argument(
        "--delivery-sidecar",
        action="append",
        default=[],
        type=Path,
        help="Correlate actual dispatch evidence with recomputed shared mailboxes; repeat for multiple sidecars",
    )
    args = parser.parse_args(argv)
    if args.command in ("record", "samples", "record-incident"):
        if args.output.exists():
            parser.error("Use a new private output directory")
        args.output.mkdir(parents=True, mode=0o700)
        if args.command == "record":
            result = _record(args.request, args.output)
        elif args.command == "samples":
            result = _samples(args.output)
        else:
            result = _record_incident(
                args.request, args.output, args.provider_recipe, args.allow_source_drift
            )
        code = 1 if result.get("operation_matches") is False else 0
    elif args.command == "replay":
        root = args.bundle.resolve()
        path = (root / args.case).resolve()
        if path.parent != root or path.suffix != ".json":
            parser.error("Case must be a JSON file directly inside the bundle")
        from wakfu_server.combat_reproduction_catalog import ReplayCatalog

        with ReplayCatalog(root).install():
            from wakfu_server.combat_reproduction import (
                read_case,
                execute_case,
                verify_catalog_bundle,
            )

            case = read_case(path)
            verify_catalog_bundle(case, root)
            plan = _invariant_plan(case) if args.check_invariants else None
            with _invariant_scope(args.check_invariants) as observation:
                outcome = execute_case(case, allow_source_drift=args.allow_source_drift)
            result = _summary(path.name, case, outcome)
            code = 0 if result.get("matches") is True else 1
            if observation is not None:
                result["invariants"] = _invariant_summary(observation, plan)
                code = _invariant_exit_code(code, result["invariants"])
    else:
        root = args.bundle.resolve()
        path = (root / args.receipt).resolve()
        if path.parent != root or path.suffix != ".json":
            parser.error("Receipt must be a JSON file directly inside the bundle")
        from wakfu_server.combat_reproduction_catalog import ReplayCatalog

        with ReplayCatalog(root).install():
            from wakfu_server.combat_incident_replay import (
                read_incident,
                verify_incident_bundle,
                replay_runtime_incident,
            )

            receipt = read_incident(path)
            verify_incident_bundle(receipt, root)
            private_evidence = []
            plan = (
                _invariant_plan(receipt, incident=True)
                if args.check_invariants
                else None
            )
            with _invariant_scope(args.check_invariants) as observation:
                result = replay_runtime_incident(
                    receipt,
                    provider_recipe=args.provider_recipe,
                    allow_source_drift=args.allow_source_drift,
                    evidence_sink=private_evidence.append
                    if args.delivery_sidecar
                    else None,
                )
            code = 0 if result["operation_matches"] else 1
            if args.delivery_sidecar:
                from wakfu_server.combat_delivery_reproduction import (
                    verify_delivery_evidence,
                )

                if len(private_evidence) != 1:
                    raise ValueError(
                        "Shared replay produced no private mailbox evidence"
                    )
                result["delivery"] = verify_delivery_evidence(
                    receipt,
                    _read_delivery_sidecars(args.delivery_sidecar),
                    expected_after=private_evidence[0],
                    replay_outcome=result,
                )
                for qualification in (
                    "bootstrap_qualified",
                    "dispatch_qualified",
                    "shared_delivery_qualified",
                ):
                    result[qualification] = result["delivery"][qualification]
                if not result["delivery"]["shared_delivery_qualified"]:
                    code = 1
            if observation is not None:
                result["invariants"] = _invariant_summary(observation, plan)
                code = _invariant_exit_code(code, result["invariants"])
    if args.output is not None and args.command in ("replay", "replay-incident"):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
