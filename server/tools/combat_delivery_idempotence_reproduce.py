#!/usr/bin/env python3
"""Closed offline reproduction of the native delivery preparation correction.

Capture Source A observations and replay the identical typed inputs on Source C.
The C gate asserts idempotence/atomicity contracts, not family-backend equality.
Workers run read-only with a sealed catalog; no capsule selects executable code.
"""
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig

TOOL = Path(__file__).resolve()
SCHEMA = "wakemu-native-delivery-idempotence-correction-v1"
SCENARIOS = (
    "prepared-prefix",
    "pending-restoration-tail",
    "tail-exhaustion",
    "foreign-prefix",
)
MAX_BYTES = 64 * 1024 * 1024


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _json_hash(value):
    return _hash(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def _read(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Delivery correction artifact exceeds size bound")
    return json.loads(raw)


def _native_ids(delivery):
    return [entry["native_action_id"] for entry in delivery.native_actions]


def qualifies_c(scenario, facts):
    """Independent correction requirements; an observed C result is not an oracle."""
    expected_prefix = [2, 3, 4] if scenario == "prepared-prefix" else [1]
    common = (
        facts["input_delivery_unchanged"]
        and facts["input_ids"] == expected_prefix
        and facts["fight_reference_preserved"]
        and facts["actor_reference_preserved"]
    )
    if scenario == "prepared-prefix":
        return (
            common
            and facts["error"] is None
            and facts["first_same_object"]
            and facts["repeat_same_object"]
            and facts["prefix_bytes_preserved"]
            and facts["prefix_correlations_preserved"]
            and facts["first_ids"] == facts["second_ids"] == [2, 3, 4]
            and facts["first_counter"] == facts["final_counter"] == 4
        )
    if scenario == "pending-restoration-tail":
        return (
            common
            and facts["error"] is None
            and facts["prefix_bytes_preserved"]
            and facts["prefix_correlations_preserved"]
            and facts["repeat_same_object"]
            and facts["first_ids"] == facts["second_ids"] == [1, 2]
            and facts["first_counter"] == facts["final_counter"] == 2
            and not facts["pending_marker_after"]
            and facts["death_reported_after"]
            and facts["qi_slot_before"] >= 0
            and facts["qi_slot_after"] == -1
            and facts["global_guards_after"] == dict(baF=False, baG=False, baK=True)
        )
    if scenario in ("tail-exhaustion", "foreign-prefix"):
        error = facts["error"]
        return (
            common
            and error is not None
            and error["type"] == "builtins.ValueError"
            and ("exhausted" if scenario == "tail-exhaustion" else "allocator")
            in error["message"]
            and facts["runtime_unchanged"]
            and facts["pending_marker_after"]
            and facts["death_reported_after"] == facts["death_reported_before"]
            and facts["qi_slot_after"] == facts["qi_slot_before"]
            and facts["global_guards_after"] == facts["global_guards_before"]
            and facts["first_ids"] is None
            and facts["first_counter"]
            == facts["initial_counter"]
            == facts["final_counter"]
        )
    raise ValueError("Unknown closed delivery scenario")


def validate_closed_case(case):
    """Reject an unknown recipe or changed sealed input/observed outcome."""
    if case.get("scenario") not in SCENARIOS:
        raise ValueError("Unknown closed delivery scenario")
    if _json_hash(case["before"]) != case["before_sha256"]:
        raise ValueError("Typed correction input digest differs")
    observed = case.get("observed_source_a")
    if observed is not None:
        if _json_hash(observed["result"]) != observed["result_sha256"]:
            raise ValueError("Recorded Source A observation digest differs")
        if (
            qualifies_c(case["scenario"], observed["facts"])
            != observed["qualifies_source_c"]
        ):
            raise ValueError("Recorded Source A contract classification differs")


def _execute(case):
    from wakfu_server.combat_reproduction_state import encode_state, decode_state
    from wakfu_server.combat_reproduction import (
        controlled_environment,
        ReproductionClock,
        digest,
    )
    from wakfu_server.combat_pending_restoration import SOURCE

    validate_closed_case(case)
    state = decode_state(case["before"])
    if (
        set(state) != {"runtime", "delivery", "target_id"}
        or case["scenario"] not in SCENARIOS
    ):
        raise ValueError("Invalid closed delivery request graph")
    runtime, delivery = state["runtime"], state["delivery"]
    from wakfu_server.combat_native_action_ids import NativeDelivery
    from wakfu_server.combat_runtime_messages import RuntimeMessages

    if not isinstance(runtime, RuntimeMessages) or not isinstance(
        delivery, NativeDelivery
    ):
        raise ValueError("Typed runtime and NativeDelivery are required")
    runtime.clock = ReproductionClock(case["clocks"])
    before_runtime = encode_state(runtime)
    before_delivery = encode_state(delivery)
    initial_counter = runtime.native_action_id
    actor = runtime.fight.actors[state["target_id"]]
    original_fight, original_actor = runtime.fight, actor
    death_reported_before = actor.id in getattr(runtime, "_reported_deaths", set())
    qi_slot_before = actor.native_obstacle_id
    from wakfu_server.combat_global_pv_collections import global_fighter_guards

    global_guards_before = (
        global_fighter_guards(runtime.fight, actor.id)
        if hasattr(runtime.fight, "native_global_pv_collections")
        else None
    )
    error, first, second = None, None, None
    first_counter = initial_counter
    with controlled_environment(case["clocks"], case["policies"]):
        try:
            first = runtime.prepare_delivery(delivery)
            first_counter = runtime.native_action_id
            second = runtime.prepare_delivery(first)
        except ValueError as failure:
            error = dict(
                type=type(failure).__module__ + "." + type(failure).__name__,
                message=str(failure),
            )
            first_counter = runtime.native_action_id
    actor = runtime.fight.actors[state["target_id"]]
    facts = dict(
        error=error,
        input_ids=_native_ids(delivery),
        input_delivery_unchanged=encode_state(delivery) == before_delivery,
        runtime_unchanged=encode_state(runtime) == before_runtime,
        initial_counter=initial_counter,
        first_counter=first_counter,
        final_counter=runtime.native_action_id,
        first_ids=_native_ids(first) if first is not None else None,
        second_ids=_native_ids(second) if second is not None else None,
        first_same_object=first is delivery,
        repeat_same_object=second is first and first is not None,
        prefix_bytes_preserved=first is not None
        and tuple(first[: len(delivery)]) == tuple(delivery),
        prefix_correlations_preserved=first is not None
        and tuple(first.native_actions[: len(delivery.native_actions)])
        == delivery.native_actions,
        pending_marker_after=getattr(actor, "native_death_status", {}).get(
            "pending_restoration"
        )
        == SOURCE,
        death_reported_after=actor.id in getattr(runtime, "_reported_deaths", set()),
        death_reported_before=death_reported_before,
        fight_reference_preserved=runtime.fight is original_fight,
        actor_reference_preserved=actor is original_actor,
        qi_slot_before=qi_slot_before,
        qi_slot_after=actor.native_obstacle_id,
        global_guards_before=global_guards_before,
        global_guards_after=(
            global_fighter_guards(runtime.fight, actor.id)
            if hasattr(runtime.fight, "native_global_pv_collections")
            else None
        ),
    )
    result = encode_state(
        dict(runtime=runtime, first=first, second=second, facts=facts)
    )
    return dict(
        facts=facts,
        result=result,
        result_sha256=digest(result),
        qualifies_source_c=qualifies_c(case["scenario"], facts),
    )


def _capture_cases():
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_reproduction import ReproductionClock
    from wakfu_server.combat_reproduction_state import encode_state, decode_state
    from wakfu_server.combat_native_action_ids import MAX_NATIVE_ACTION_ID
    from wakfu_server.combat_pending_restoration import SOURCE
    import struct

    clocks = dict(wall_time_ns=1700000000000000000, monotonic_ns=0)
    policies = dict(WAKFU_NATIVE_AREA_CALLBACKS="1", WAKFU_NATIVE_GRANTED_CAST="0")
    cells = {(0, 0, 0), (1, 0, 0)}
    fight = Fight(
        7,
        [
            Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
            Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
        ],
        cells,
        {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
    )
    fight.ready(1)
    runtime = RuntimeMessages(fight, clock=ReproductionClock(clocks))
    ended = runtime.end_turn(1, 100, 1)
    if _native_ids(ended) != [1]:
        raise ValueError("Actual end-turn did not prepare the first native action")
    delivery = runtime.acknowledge_turn(struct.pack(">i", 1))
    if _native_ids(delivery) != [2, 3, 4] or runtime.native_action_id != 4:
        raise ValueError(
            "Actual end-turn/ACK did not produce the declared native prefix"
        )
    base = encode_state(dict(runtime=runtime, delivery=delivery, target_id=-200))
    # The tail cases use actual admitted native hostile damage and an owned KO
    # writer, not a mocked death publisher or an unregistered zero-HP actor.
    from test_native_player_death_runtime_qualified import NativePlayerDeathRuntimeTests
    from wakfu_server.combat_death import death_messages
    from wakfu_server.combat_pending_restoration import pending_restoration_uids

    _, _, corpse = NativePlayerDeathRuntimeTests().corpse()
    corpse_runtime = RuntimeMessages(corpse, clock=ReproductionClock(clocks))
    ko_delivery = corpse_runtime.prepare_delivery(death_messages(corpse_runtime, 8))
    if _native_ids(ko_delivery) != [1] or pending_restoration_uids(corpse, 8) != ():
        raise ValueError(
            "Actual KO prefix or exhausted restoration precondition differs"
        )
    corpse.actors[8].native_death_status["pending_restoration"] = SOURCE
    tail_base = encode_state(
        dict(runtime=corpse_runtime, delivery=ko_delivery, target_id=8)
    )
    cases = []
    for scenario in SCENARIOS:
        state = decode_state(base if scenario == "prepared-prefix" else tail_base)
        runtime, delivery = state["runtime"], state["delivery"]
        if scenario == "tail-exhaustion":
            runtime.native_action_id = MAX_NATIVE_ACTION_ID
        if scenario == "foreign-prefix":
            delivery.fight_id = runtime.fight.id + 1
        case = dict(
            scenario=scenario,
            before=encode_state(state),
            clocks=clocks,
            policies=policies,
            boundary="offline-runtime-delivery-preparation-not-client-or-live-publication",
            rng_boundary="no-RNG-consumed-by-this-closed-preparation-recipe",
            pending_precondition="exhausted-owned-restoration-checkpoint-no-upstream-cast"
            if scenario != "prepared-prefix"
            else None,
        )
        case["before_sha256"] = _json_hash(case["before"])
        case["observed_source_a"] = _execute(case)
        cases.append(case)
    return cases


def _worker(args):
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.server_root))
    sys.path.insert(0, str(args.server_root / "tests"))
    runner_sha256 = _hash(TOOL.read_bytes())
    helper = TOOL.with_name("combat_migration_replay.py")
    helper_sha256 = _hash(helper.read_bytes())
    fixture_files = {
        str(args.server_root / "tests" / name): _hash(
            (args.server_root / "tests" / name).read_bytes()
        )
        for name in (
            "test_native_player_death_runtime_qualified.py",
            "test_combat_resurrection_runtime.py",
        )
    }
    catalog_manifest_sha256 = _hash((args.catalog_bundle / "catalog.json").read_bytes())
    spec = importlib.util.spec_from_file_location(
        "trusted_delivery_replay_audit", helper
    )
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    sys.addaudithook(audit._read_only)
    from wakfu_server.combat_reproduction_catalog import ReplayCatalog

    with ReplayCatalog(args.catalog_bundle).install():
        from wakfu_server.combat_reproduction import source_identity, catalog_identity

        source = source_identity()
        if source["sha256"] != args.expected_source_sha256:
            raise ValueError(
                "Selected engine does not match the explicitly pinned source"
            )
        catalog = catalog_identity()
        if args.command == "capture-a":
            from wakfu_server.combat_reproduction import controlled_environment

            with controlled_environment(
                dict(wall_time_ns=1700000000000000000, monotonic_ns=0),
                dict(WAKFU_NATIVE_AREA_CALLBACKS="1", WAKFU_NATIVE_GRANTED_CAST="0"),
            ):
                cases = _capture_cases()
            result = dict(
                schema=SCHEMA,
                source_a=source,
                catalog=catalog,
                catalog_manifest_sha256=catalog_manifest_sha256,
                cases=cases,
                observed_source_a_contracts={
                    case["scenario"]: case["observed_source_a"]["qualifies_source_c"]
                    for case in cases
                },
            )
        else:
            capsule_sha256 = _hash(args.case.read_bytes())
            capsule = _read(args.case)
            if capsule.get("schema") != SCHEMA or capsule["catalog"] != catalog:
                raise ValueError("Wrong typed correction capsule or catalog")
            if capsule["catalog_manifest_sha256"] != catalog_manifest_sha256:
                raise ValueError("Correction capsule catalog seal differs")
            if (
                type(capsule.get("cases")) is not list
                or len(capsule["cases"]) != len(SCENARIOS)
                or {case.get("scenario") for case in capsule["cases"]} != set(SCENARIOS)
            ):
                raise ValueError(
                    "Correction capsule must contain each closed scenario exactly once"
                )
            results = []
            for case in capsule["cases"]:
                validate_closed_case(case)
                current = _execute(case)
                baseline_satisfied = case["observed_source_a"]["qualifies_source_c"]
                results.append(
                    dict(
                        scenario=case["scenario"],
                        source_a_result_sha256=case["observed_source_a"][
                            "result_sha256"
                        ],
                        source_c=current,
                        baseline_satisfied_c_contract=baseline_satisfied,
                        comparison_kind="already-correct-guard"
                        if baseline_satisfied
                        else "intentional-correction",
                        exact_outcome_matches_source_a=current["result_sha256"]
                        == case["observed_source_a"]["result_sha256"],
                        intentional_outcome_difference=(
                            not baseline_satisfied
                            and current["result_sha256"]
                            != case["observed_source_a"]["result_sha256"]
                        ),
                    )
                )
            if {row["scenario"] for row in results} != set(SCENARIOS) or len(
                results
            ) != len(SCENARIOS):
                raise ValueError(
                    "Correction capsule must contain each closed scenario exactly once"
                )
            result = dict(
                schema=SCHEMA,
                source_a_sha256=capsule["source_a"]["sha256"],
                source_c=source,
                catalog=catalog,
                capsule_sha256=capsule_sha256,
                results=results,
                qualified=(
                    capsule["source_a"]["sha256"] != source["sha256"]
                    and all(row["source_c"]["qualifies_source_c"] for row in results)
                    and all(
                        row["baseline_satisfied_c_contract"]
                        or row["intentional_outcome_difference"]
                        for row in results
                    )
                    and any(
                        row["scenario"] == "prepared-prefix"
                        and row["intentional_outcome_difference"]
                        for row in results
                    )
                ),
                scope="four-closed-delivery-correction-contracts-not-full-suite-or-family-backend-parity",
            )
            if _hash(args.case.read_bytes()) != capsule_sha256:
                raise ValueError("Typed correction capsule changed during execution")
        if source_identity() != source:
            raise ValueError("Selected engine changed during correction reproduction")
        if catalog_identity() != catalog:
            raise ValueError("Selected catalog changed during correction reproduction")
    if audit._ISOLATION_VIOLATIONS:
        raise ValueError("Closed correction recipe attempted external effects")
    if (
        _hash(TOOL.read_bytes()) != runner_sha256
        or _hash(helper.read_bytes()) != helper_sha256
    ):
        raise ValueError("Trusted diagnostic tool/helper changed during execution")
    if (
        _hash((args.catalog_bundle / "catalog.json").read_bytes())
        != catalog_manifest_sha256
    ):
        raise ValueError("Catalog manifest changed during correction reproduction")
    if any(
        _hash(Path(path).read_bytes()) != expected
        for path, expected in fixture_files.items()
    ):
        raise ValueError("Native fixture inputs changed during execution")
    result["runner_sha256"] = runner_sha256
    result["audit_helper_sha256"] = helper_sha256
    result["fixture_inputs"] = fixture_files
    result["fixture_construction_executed"] = args.command == "capture-a"
    result["live_commit"] = result["live_delivery"] = False
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture-a", "replay-c"))
    parser.add_argument("--server-root", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--catalog-bundle", type=Path, required=True)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.server_root = args.server_root.resolve()
    args.catalog_bundle = args.catalog_bundle.resolve()
    if args.command == "replay-c" and args.case is None:
        parser.error("Replay requires a typed correction capsule")
    if args.case is not None:
        args.case = args.case.resolve()
    if args.worker:
        with redirect_stdout(io.StringIO()):
            result = _worker(args)
        print(json.dumps(result, separators=(",", ":")))
        return 0
    if args.output is None or args.output.exists():
        parser.error("Use a new private output file")
    command = [
        str(TOOL),
        args.command,
        "--worker",
        "--server-root",
        str(args.server_root),
        "--expected-source-sha256",
        args.expected_source_sha256,
        "--catalog-bundle",
        str(args.catalog_bundle),
    ]
    if args.case is not None:
        command += ["--case", str(args.case)]
    bootstrap = (
        "import runpy,sys;sys.path.append("
        + repr(sysconfig.get_path("purelib"))
        + ");sys.argv="
        + repr(command)
        + ";runpy.run_path("
        + repr(str(TOOL))
        + ",run_name='__main__')"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", bootstrap],
        capture_output=True,
        text=True,
        timeout=args.timeout,
    )
    if process.returncode:
        raise RuntimeError(
            "Read-only delivery correction worker failed with exit "
            + str(process.returncode)
        )
    result = json.loads(process.stdout)
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
    print(
        json.dumps(
            dict(
                output=str(args.output),
                sha256=_hash(raw),
                qualified=result.get("qualified"),
                command=args.command,
            )
        )
    )
    return 0 if args.command == "capture-a" or result["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
