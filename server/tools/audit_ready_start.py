#!/usr/bin/env python3
"""Offline production Ready with full HP, innate effects and native start events.

No socket, real accounts, GUI or persistence mutation. Registration and actual
start-time changes are reported separately; neither implies complete gameplay.
"""
from pathlib import Path
import sys, json, time, hashlib, collections, argparse, datetime, random, traceback, os, struct
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_active_spells as fixture_module
from wakfu_server.combat_class_initialization import BREEDS
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.combat_arena_selection import bounded_arena
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_server_spell import (
    server_runtime,
    prepare_server_initialization,
    prewarm_runtime_catalogs,
    prepare_server_turn_end,
    prepare_server_turn_start,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells, encode_deck, validate_deck
from wakfu_server.paths import PROJECT_ROOT


def source_hashes():
    paths = list((PROJECT_ROOT / "server/wakfu_server").rglob("*.py"))
    paths += list((PROJECT_ROOT / "server/protocol").glob("*.json")) + list(
        (PROJECT_ROOT / "server/protocol").glob("*.json")
    )
    paths += [
        PROJECT_ROOT / "server/protocol/native-qi-surfaces" / name
        for name in ("publication.json", "manifest.json", "1134.json")
    ]
    paths += [
        PROJECT_ROOT / "server/tools" / name
        for name in (
            "audit_class_initialization.py",
            "audit_active_spells.py",
            "audit_ready_start.py",
            "audit_passive_activation.py",
            "audit_class_spell_grants.py",
            "class_spell_eligible_targets.py",
        )
    ]
    return {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(paths)
    }


def planned_cases(breeds, spells_for, *, basics_only=False, legal_passive_levels=False):
    cases = [(breed, level, None) for breed in sorted(breeds) for level in (1, 20, 200)]
    if not basics_only:
        for breed in sorted(breeds):
            for spell in spells_for(breed, 200):
                if spell["kind"] != "passive":
                    continue
                levels = {200}
                if spell["unlock_level"] <= 20:
                    levels.add(20)
                if legal_passive_levels:
                    levels.add(max(1, spell["unlock_level"]))
                cases.extend((breed, level, spell["id"]) for level in sorted(levels))
    return cases


def run(
    output,
    *,
    basics_only=False,
    from_report=None,
    reason=None,
    turn_cycle=False,
    legal_passive_levels=False,
    cases_override=None,
    on_ready=None,
    on_runtime=None,
    turn_steps=2,
    active_deck_provider=None,
    character_fixture_provider=None,
    preplacement_character_fixture_provider=None,
    preplacement_geometry_provider=None,
    monster_reference=5525,
    monster_level=1,
):
    if preplacement_character_fixture_provider is not None and not callable(
        preplacement_character_fixture_provider
    ):
        raise ValueError("Offline preplacement character provider must be callable")
    before = source_hashes()
    tool_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    warm = time.perf_counter()
    prewarm_runtime_catalogs()
    prewarm_ms = (time.perf_counter() - warm) * 1000
    geometry = map_geometry(1134)
    origin, target = next((tuple(a), tuple(b)) for a, b in geometry["edges"] if a != b)
    terrain = bounded_arena(geometry, origin, [target], radius=12)
    cases = planned_cases(
        BREEDS,
        available_spells,
        basics_only=basics_only,
        legal_passive_levels=legal_passive_levels,
    )
    if cases_override is not None:
        cases = list(cases_override)
    if from_report is not None:
        previous = json.loads(Path(from_report).read_text())
        cases = [
            (row["breed"], row["level"], row["passive"])
            for row in previous["rows"]
            if row["status"] in ("rejected", "lifecycle_failed")
            and (reason is None or reason in row.get("reason", ""))
        ]
    rows = []

    def save(final=False):
        after = source_hashes() if final else None
        result = {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scope": "Full HP, Ready production entry, native start event; own no-equipment fixture; no graphical validation",
            "turn_cycle_enabled": turn_cycle,
            "legal_passive_levels": legal_passive_levels,
            "native_start_events_enabled": os.environ.get(
                "WAKFU_COMBAT_START_EVENTS", "1"
            )
            == "1",
            "area_callbacks_enabled": os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1")
            == "1",
            "expected_cases": len(cases),
            "completed_cases": len(rows),
            "finished": final,
            "prewarm_ms": round(prewarm_ms, 3),
            "source_before": before,
            "source_after": after,
            "source_stable": before == after if final else None,
            "tool_sha256": tool_before,
            "tool_stable": tool_before
            == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            if final
            else None,
            # Ready coverage does not certify spell gameplay or deployment.
            "deployment_gate_passed": False,
            "ready_gate_passed": (
                final
                and before == after
                and len(rows) == len(cases)
                and all(
                    r["status"] == "ready_started"
                    and r["rollback_preserved"]
                    and r["trace_complete"]
                    for r in rows
                )
                and tool_before
                == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            ),
            "status_counts": dict(collections.Counter(r["status"] for r in rows)),
            "failure_counts": dict(
                collections.Counter(
                    r.get("reason")
                    for r in rows
                    if r["status"] in ("rejected", "lifecycle_failed")
                )
            ),
            "rows": rows,
        }
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return result

    base_origin, base_target, base_terrain = origin, target, terrain
    for breed, level, passive in cases:
        origin, target, terrain = base_origin, base_target, base_terrain
        if preplacement_geometry_provider is not None:
            if not callable(preplacement_geometry_provider):
                raise ValueError(
                    "Offline preplacement geometry provider must be callable"
                )
            origin, target, terrain = preplacement_geometry_provider(
                geometry, origin, target, breed, level, passive
            )
            if (
                origin not in terrain["cells"]
                or target not in terrain["cells"]
                or origin == target
            ):
                raise ValueError(
                    "Preplacement geometry requires distinct actual native cells"
                )
        character, monster, fight = fixture_module.fixture(
            breed,
            level,
            target,
            terrain,
            origin,
            ready=False,
            monster_reference=monster_reference,
            monster_level=monster_level,
            character_fixture=(
                None
                if preplacement_character_fixture_provider is None
                else lambda character: preplacement_character_fixture_provider(
                    character, breed, level, passive
                )
            ),
        )
        active = [
            spell["id"]
            for spell in available_spells(breed, level)
            if spell["kind"] == "active"
        ][:6]
        if active_deck_provider is not None:
            if not callable(active_deck_provider):
                raise ValueError("Offline Ready active deck provider must be callable")
            active = list(active_deck_provider(breed, level, passive))
        if character_fixture_provider is not None:
            if not callable(character_fixture_provider):
                raise ValueError(
                    "Offline Ready character fixture provider must be callable"
                )
            character_fixture_provider(character, breed, level, passive)
        deck = encode_deck(active, () if passive is None else [passive])
        if active_deck_provider is not None:
            validate_deck(deck, breed, level)
        original = snapshot(fight)
        events = []
        rng = random.Random(7)
        stage = "ready"
        started = time.perf_counter()
        row = {
            "breed": breed,
            "level": level,
            "passive": passive,
            "active": active,
            "hp_policy": "full",
            "gameplay_verified": False,
        }
        stats_source = {"fight": fight}

        def initialize(preview, action_id):
            result = prepare_server_initialization(
                character,
                {monster["id"]: monster},
                preview,
                3,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            )
            stats_source["fight"] = result[0]
            return result

        def end_provider(preview, **boundary):
            return prepare_server_turn_end(
                character, {monster["id"]: monster}, preview, deck, rng=rng, **boundary
            )

        def start_provider(preview, **boundary):
            result = prepare_server_turn_start(
                character,
                {monster["id"]: monster},
                preview,
                deck,
                rng=rng,
                native_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
                area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1")
                == "1",
                **boundary,
            )
            # Runtime adopts the returned state into this destination, retaining
            # existing actor identities. Bind the serializer to that same owner.
            stats_source["fight"] = preview
            return result

        def stats(actor, state=None):
            if actor.id == character["id"]:
                wp = BREEDS[breed]["resources"]["WP"]
                return actual_actor_stats(
                    character,
                    actor,
                    fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=wp,
                )
            source = stats_source["fight"] if state is None else state
            if actor.id in getattr(source, "native_summon_registrations", {}):
                from wakfu_server.combat_summon_stats import registered_summon_stats

                return registered_summon_stats(actor, source, source.map_id)
            if actor.id != monster["id"]:
                raise ValueError("Missing actual audit actor stats source")
            return actual_monster_actor_stats(
                monster,
                actor,
                fight.id,
                wp_current=monster["wp"],
                wp_maximum=monster["wp"],
            )

        try:
            with combat_diagnostic_scope(
                lambda **record: events.append(record), limit=1024
            ):
                preview, runtime, packets = prepare_ready(
                    fight,
                    3,
                    True,
                    initialize=initialize,
                    stats_serializer=stats,
                    runtime_stats_serializer=stats,
                    effects_serializer=actor_effects,
                    turn_end_provider=end_provider if turn_cycle else None,
                    turn_start_provider=start_provider if turn_cycle else None,
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        character,
                        {monster["id"]: monster},
                        deck,
                        action_id=action_id,
                        critical=False,
                        rng=rng,
                    )[0],
                )
            if turn_cycle:
                stage = "turn_lifecycle"
                row["turn_stages"] = []
                for _ in range(turn_steps):
                    if runtime.fight.phase != "active":
                        row["turn_stages"].append(
                            {
                                "status": "precondition_changed",
                                "phase": runtime.fight.phase,
                            }
                        )
                        break
                    source_turn = runtime.fight
                    turn_before = snapshot(source_turn)
                    rng_before = rng.getstate()
                    candidate = deepcopy(runtime)
                    stats_source["fight"] = candidate.fight
                    actor = candidate.fight.current
                    try:
                        with combat_diagnostic_scope(
                            lambda **record: events.append(record), limit=4096
                        ):
                            extra = (
                                candidate.end_turn(3, actor.id, actor.turn_count)
                                if actor.controlled
                                else candidate.end_server_turn(
                                    actor.id, candidate.fight.turn_id
                                )
                            )
                            pending = candidate.awaiting_ack
                            if pending is not None:
                                extra += candidate.acknowledge_turn(
                                    struct.pack(">i", pending)
                                )
                        runtime = candidate
                        packets += extra
                        row["turn_stages"].append(
                            {
                                "status": "completed",
                                "actor_id": actor.id,
                                "ack": pending,
                                "packet_count": len(extra),
                                "table_turn_after": candidate.fight.native_table_turn,
                            }
                        )
                    except Exception:
                        row["failed_stage_rollback_preserved"] = (
                            snapshot(source_turn) == turn_before
                        )
                        row["failed_stage_rng_rollback_preserved"] = (
                            rng.getstate() == rng_before
                        )
                        if (
                            not row["failed_stage_rollback_preserved"]
                            or not row["failed_stage_rng_rollback_preserved"]
                        ):
                            raise AssertionError(
                                "Failed turn stage changed source fight or RNG"
                            )
                        raise
                preview = runtime.fight
            pc = preview.actors[7]
            row.update(
                status="ready_started",
                packet_count=len(packets),
                native_start_event_delivered=preview.native_start_event_delivered,
                table_turn=preview.native_table_turn,
                applied_states=[
                    {"reference": state.reference, "level": state.level}
                    for state in pc.state_ledger.entries
                ],
                hp_before=fight.actors[7].hp,
                hp_after=pc.hp,
                max_hp_before=fight.actors[7].max_hp,
                max_hp_after=pc.max_hp,
                actor_changed=snapshot(preview)["actors"] != original["actors"],
                registered_effects=len(preview.native_retained_records),
            )
            if on_runtime is not None:

                def runtime_stats(actor, state):
                    stats_source["fight"] = state
                    return stats(actor)

                row["runtime_access"] = on_runtime(
                    runtime, character, monster, deck, packets, runtime_stats
                )
            if on_ready is not None:
                row["spell_access"] = on_ready(
                    preview, character, monster, deck, packets
                )
        except Exception as error:
            failed = next((e for e in events if e.get("status") == "failed"), {})
            row.update(
                status="rejected" if stage == "ready" else "lifecycle_failed",
                failed_stage=stage,
                reason=str(error),
                exception_type=type(error).__name__,
                effect_reference=failed.get("effect_reference"),
                effect_class=failed.get("effect_class"),
                effect_level=failed.get("level"),
                ancestors=failed.get("ancestors"),
                traceback=[
                    {
                        "file": frame.filename,
                        "line": frame.lineno,
                        "function": frame.name,
                    }
                    for frame in traceback.extract_tb(error.__traceback__)
                ],
            )
        row.update(
            rollback_preserved=snapshot(fight) == original,
            trace_complete=not any(e.get("effects_omitted", 0) for e in events),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            effect_status_counts=dict(
                collections.Counter(
                    e.get("status") for e in events if e.get("event") == "combat_effect"
                )
            ),
        )
        if not row["rollback_preserved"]:
            raise AssertionError("Source fight mutated")
        rows.append(row)
        if len(rows) % 18 == 0 or row["status"] == "rejected":
            save()
            print(
                json.dumps(
                    {"completed": len(rows), "expected": len(cases), "latest": row}
                ),
                flush=True,
            )
    result = save(True)
    print(
        json.dumps(
            {
                "finished": True,
                "counts": result["status_counts"],
                "source_stable": result["source_stable"],
            }
        ),
        flush=True,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--basics-only", action="store_true")
    area_options = parser.add_mutually_exclusive_group()
    area_options.add_argument(
        "--area-callbacks", action="store_true", dest="area_callbacks"
    )
    area_options.add_argument(
        "--no-area-callbacks", action="store_false", dest="area_callbacks"
    )
    parser.set_defaults(area_callbacks=None)
    parser.add_argument("--turn-cycle", action="store_true")
    parser.add_argument("--legal-passive-levels", action="store_true")
    parser.add_argument("--from-report")
    parser.add_argument("--reason")
    parser.add_argument(
        "--output", default="docs/reports/combat-inventory/ready-start-audit.json"
    )
    args = parser.parse_args()
    if args.area_callbacks is not None:
        os.environ["WAKFU_NATIVE_AREA_CALLBACKS"] = "1" if args.area_callbacks else "0"
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        output,
        basics_only=args.basics_only,
        turn_cycle=args.turn_cycle,
        legal_passive_levels=args.legal_passive_levels,
        from_report=args.from_report,
        reason=args.reason,
    )
