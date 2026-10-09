#!/usr/bin/env python3
"""Native passive activation, separate from registration. Offline, no DB/GUI.

Each passive runs with owned breed innates and an ordinary Ready/full snapshot.
The damage source is the registered Wonejo's actual ability7962, applied through
its native roots/shared dispatcher (not a fabricated lifecycle notification).
RuntimeMessages supplies end/ACK/start/expiry; own casts use production entry.
Missing conditional prerequisites are reported, never manufactured.
"""
import argparse, collections, datetime, json, random, struct, time, os, hashlib
from pathlib import Path
from copy import deepcopy
import audit_ready_start as ready
import audit_active_spells as audit
from wakfu_server.paths import DATA_ROOT, PROJECT_ROOT
from wakfu_server.spells import available_spells, encode_deck
from wakfu_server.spell_audit import catalog
from wakfu_server.combat_server_spell import (
    prewarm_runtime_catalogs,
    prepare_server_initialization,
    prepare_server_turn_end,
    prepare_server_turn_start,
    prepare_server_spell,
    server_runtime,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_npc_attack import (
    ability,
    npc_runtime_catalog,
    npc_spell_catalog,
)
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import snapshot


def passive_cases(breed=None, *, identities=None, level=None):
    names = {
        r["id"]: r["name"]
        for r in json.loads((DATA_ROOT / "spell-names.json").read_text())["spells"]
    }
    rows = json.loads((DATA_ROOT / "spells.json").read_text())["spells"]
    selected = [
        r
        for r in rows
        if r["kind"] == "passive" and (breed is None or r["breed"] == breed)
    ]
    if identities is not None:
        requested = set(identities)
        missing = requested - {r["id"] for r in selected}
        if missing:
            raise ValueError(
                f"Unknown passive IDs for selected breed: {sorted(missing)}"
            )
        selected = [r for r in selected if r["id"] in requested]
    if level is not None and (type(level) is not int or not 10 <= level <= 200):
        raise ValueError("Passive audit level must be between10 and200")
    if level is not None and any(r["unlock_level"] > level for r in selected):
        raise ValueError("Requested level does not unlock every selected passive")
    return [
        dict(
            r,
            name=names.get(r["id"]),
            level=max(10, r["unlock_level"]) if level is None else level,
        )
        for r in selected
    ]


def summarize_stage(name, events, before, after, packets, roots):
    attributable = [
        e
        for e in events
        if e.get("event") == "combat_effect"
        and (
            e.get("effect_reference") in roots or set(e.get("ancestors") or ()) & roots
        )
    ]
    waiting = {
        e["effect_reference"]
        for e in attributable
        if e.get("status") == "subscribed_waiting_event"
    }
    # Completed registration is not an activation. Replayed roots no longer
    # enter the waiting branch; their retained children carry the same ancestry.
    activated = [
        e
        for e in attributable
        if e.get("status") == "completed" and e.get("effect_reference") not in waiting
    ]
    return dict(
        stage=name,
        packet_count=len(packets),
        actor_changed=before["actors"] != after["actors"],
        resources_before={
            uid: {k: actor.get(k) for k in ("hp", "max_hp", "ap", "mp")}
            for uid, actor in before["actors"].items()
        },
        resources_after={
            uid: {k: actor.get(k) for k in ("hp", "max_hp", "ap", "mp")}
            for uid, actor in after["actors"].items()
        },
        removed_retained_uids=sorted(
            set(before.get("native_retained_records", {}))
            - set(after.get("native_retained_records", {}))
        ),
        passive_activation_observed=bool(activated),
        activated_effects=[
            {
                k: e.get(k)
                for k in (
                    "effect_reference",
                    "effect_class",
                    "target_id",
                    "status",
                    "ancestors",
                )
            }
            for e in activated
        ],
        passive_trace=attributable,
        skipped_prerequisites=[
            e.get("criteria")
            for e in attributable
            if e.get("status") == "skipped_condition"
        ],
        trace_complete=all(
            e.get("effects_omitted", 0) == 0
            for e in events
            if e.get("event") == "combat_effect_trace_summary"
        ),
    )


def run_case(case, terrain, origin, target):
    level, breed = case["level"], case["breed"]
    character, monster, source = audit.fixture(
        breed, level, target, terrain, origin, ready=False
    )
    monsters = {monster["id"]: monster}
    active = [r["id"] for r in available_spells(breed, level) if r["kind"] == "active"][
        :6
    ]
    deck = encode_deck(active, [case["id"]])
    character["builds"] = {0: {"deck": deck.hex()}}
    rng = random.Random(7)
    roots = set(catalog()["spells"][str(case["id"])]["levels"][level - 1][2])
    original = snapshot(source)
    stages = []
    runtime = None
    row = dict(
        passive_id=case["id"],
        passive_name=case["name"],
        breed=breed,
        level=level,
        unlock_level=case["unlock_level"],
        active_deck=active,
        installed=False,
        activation_observed=False,
        gameplay_verified=False,
        stages=stages,
    )

    def stats(actor):
        if actor.controlled:
            return actual_actor_stats(
                character,
                actor,
                source.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
            )
        return actual_monster_actor_stats(
            monster,
            actor,
            source.id,
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
        )

    def end_provider(fight, **boundary):
        return prepare_server_turn_end(
            character, monsters, fight, deck, rng=rng, **boundary
        )

    def area_provider(fight, **boundary):
        return prepare_server_turn_start(
            character,
            monsters,
            fight,
            deck,
            rng=rng,
            native_events=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1",
            area_callbacks=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1",
            **boundary,
        )

    def record_stage(name, operation, fight):
        events = []
        before = snapshot(fight)
        random_before = rng.getstate()
        with combat_diagnostic_scope(lambda **e: events.append(e), limit=8192):
            try:
                result, packets = operation()
            except Exception as error:
                rollback = snapshot(fight) == before
                random_rollback = rng.getstate() == random_before
                failed = next((e for e in events if e.get("status") == "failed"), {})
                stages.append(
                    dict(
                        stage=name,
                        status="blocked",
                        reason=str(error),
                        effect_reference=failed.get("effect_reference"),
                        effect_class=failed.get("effect_class"),
                        rollback_preserved=rollback,
                        rng_rollback_preserved=random_rollback,
                        passive_trace=[
                            e for e in events if e.get("event") == "combat_effect"
                        ],
                    )
                )
                if not rollback or not random_rollback:
                    raise AssertionError(
                        "Failed passive stage changed source fight or RNG"
                    ) from error
                raise
        stages.append(
            dict(
                status="completed",
                **summarize_stage(
                    name, events, before, snapshot(result), packets, roots
                ),
            )
        )
        return result

    try:

        def initialize():
            nonlocal runtime
            fight, runtime, packets = prepare_ready(
                source,
                3,
                True,
                initialize=lambda preview, action_id: prepare_server_initialization(
                    character,
                    monsters,
                    preview,
                    3,
                    deck,
                    action_id=action_id,
                    rng=rng,
                    fight_start=True,
                ),
                stats_serializer=stats,
                effects_serializer=actor_effects,
                turn_end_provider=end_provider,
                turn_start_provider=area_provider
                if (
                    os.environ.get("WAKFU_COMBAT_START_EVENTS", "1") == "1"
                    or os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1"
                )
                else None,
            )
            return fight, packets

        record_stage("ready_native_start", initialize, source)
        row["installed"] = True

        # Fixture may begin on either participant: preserve native timeline order.
        def end_actor():
            candidate = deepcopy(runtime)
            actor = candidate.fight.current
            packets = (
                candidate.end_turn(3, actor.id, actor.turn_count)
                if actor.controlled
                else candidate.end_server_turn(actor.id, candidate.fight.turn_id)
            )
            return candidate, packets

        def transition(name):
            nonlocal runtime
            candidate = None

            def execute():
                nonlocal candidate
                candidate, packets = end_actor()
                if candidate.awaiting_ack is not None:
                    packets += candidate.acknowledge_turn(
                        struct.pack(">i", candidate.awaiting_ack)
                    )
                return candidate.fight, packets

            record_stage(name, execute, runtime.fight)
            runtime = candidate

        if runtime.fight.current.controlled:
            transition("own_end_ack_npc_start")
        if (
            runtime.fight.phase == "active"
            and runtime.fight.current.id == monster["id"]
        ):

            def damage():
                preview = deepcopy(runtime.fight)
                rule = ability(monster)
                actor = preview.current
                pc = preview.actors[character["id"]]
                if (
                    abs(actor.position[0] - pc.position[0])
                    + abs(actor.position[1] - pc.position[1])
                    != 1
                ):
                    raise ValueError("Native NPC ability requires adjacent target")
                if not audit.static_visible(1134, actor.position, pc.position):
                    raise ValueError("Native NPC ability requires verified LOS")
                factory, _ = server_runtime(
                    character,
                    monsters,
                    deck,
                    action_id=runtime.action_id + 1,
                    critical=False,
                    rng=rng,
                    compiled=npc_runtime_catalog(),
                )
                dispatcher, packets = factory(
                    preview,
                    dict(
                        actor_id=actor.id,
                        spell_id=rule["spell_id"],
                        evaluation_level=rule["spell_level"],
                        target_id=pc.id,
                        target=pc.position,
                        costs={k: rule[k] for k in ("ap", "mp", "wp")},
                    ),
                )
                with preview.effect_resolution():
                    for reference in npc_spell_catalog()["spells"][
                        str(rule["spell_id"])
                    ]["levels"][rule["spell_level"] - 1][2]:
                        dispatcher.execute(
                            EffectInvocation(
                                reference,
                                rule["spell_level"],
                                actor.id,
                                pc.id,
                                pc.position,
                                native_explicit_target=True,
                            )
                        )
                return preview, packets

            runtime.fight = record_stage("owned_npc_7962_damage", damage, runtime.fight)
            runtime.action_id += 1
            if runtime.fight.phase == "active":
                transition("npc_end_ack_own_start")
        if (
            runtime.fight.phase == "active"
            and runtime.fight.current.id == character["id"]
        ):
            # One genuine pass with unspent native resources tests end reactions
            # before a damaging cast can legitimately finish the small NPC fight.
            transition("own_end_unspent_ack_npc_start")
            if runtime.fight.phase == "active":
                transition("npc_pass_end_ack_own_start")
        if (
            runtime.fight.phase == "active"
            and runtime.fight.current.id == character["id"]
        ):
            attempts = []
            accepted = None
            for spell in active:
                events = []
                previous = snapshot(runtime.fight)
                random_before = rng.getstate()
                try:
                    with combat_diagnostic_scope(
                        lambda **e: events.append(e), limit=8192
                    ):
                        tx = prepare_server_spell(
                            struct.pack(
                                ">qqiih",
                                character["id"],
                                (character["id"] << 32) | spell,
                                *runtime.fight.actors[monster["id"]].position,
                            ),
                            character,
                            monsters,
                            runtime.fight,
                            3,
                            deck,
                            action_id=runtime.action_id + 1,
                            critical=False,
                            rng=rng,
                            line_of_sight=lambda a, b, f: authoritative_visible(
                                1134,
                                a,
                                b,
                                f,
                                blocking_footprints={
                                    x.id: {x.position[:2]}
                                    for x in f.actors.values()
                                    if x.hp > 0
                                },
                            ),
                        )
                    stages.append(
                        dict(
                            status="completed",
                            **summarize_stage(
                                "own_native_cast_" + str(spell),
                                events,
                                previous,
                                snapshot(tx.fight),
                                tx.packets,
                                roots,
                            ),
                        )
                    )
                    runtime.fight = tx.fight
                    runtime.action_id += 1
                    accepted = spell
                    break
                except Exception as error:
                    if snapshot(runtime.fight) != previous:
                        raise AssertionError("Rejected own cast mutated source")
                    if rng.getstate() != random_before:
                        raise AssertionError("Rejected own cast mutated RNG")
                    failed = next(
                        (e for e in events if e.get("status") == "failed"), {}
                    )
                    attempts.append(
                        dict(
                            spell_id=spell,
                            reason=str(error),
                            effect_reference=failed.get("effect_reference"),
                            effect_class=failed.get("effect_class"),
                            rollback_preserved=True,
                            rng_rollback_preserved=True,
                        )
                    )
            row["own_cast_attempts"] = attempts
            if accepted is None:
                stages.append(
                    dict(
                        stage="own_native_cast",
                        status="prerequisite_missing",
                        reason="No equipped first-six active accepted at actual enemy cell",
                        attempts=attempts,
                    )
                )
            if runtime.fight.phase == "active":
                transition("own_end_after_damage_cast")
        row["status"] = "cycle_observed"
    except Exception as error:
        row.update(status="blocked", reason=str(error), first_blocker=stages[-1])
    row["start_activation_observed"] = any(
        s.get("passive_activation_observed")
        for s in stages
        if s["stage"] == "ready_native_start"
    )
    row["activation_observed"] = any(
        s.get("passive_activation_observed")
        for s in stages
        if s["stage"] != "ready_native_start"
    )
    row["trace_complete"] = all(stage.get("trace_complete", True) for stage in stages)
    row["rollback_preserved"] = snapshot(source) == original
    if not row["rollback_preserved"]:
        raise AssertionError("Source Fight mutated")
    row["unreached_prerequisites"] = [
        "No ally/healing/setup/summon/KO/profession prerequisites are fabricated",
        "Removal observed only through actual end/start timer expiry; permanent passives are not forcibly removed",
    ]
    return row


def run(output, breed=None, *, identities=None, level=None):
    before = ready.source_hashes()
    started = time.perf_counter()
    prewarm_runtime_catalogs()
    geometry = audit.map_geometry(1134)
    origin, target = next(
        (tuple(a), tuple(b))
        for a, b in geometry["edges"]
        if a != b
        and abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        and audit.static_visible(1134, tuple(b), tuple(a))
    )
    terrain = audit.bounded_arena(geometry, origin, [target], radius=12)
    cases = passive_cases(breed, identities=identities, level=level)
    rows = []
    output.parent.mkdir(parents=True, exist_ok=True)

    def save(final=False):
        after = ready.source_hashes() if final else None
        result = dict(
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            finished=final,
            scope="Legal-minimum passive, full native Ready, registered NPC7962 damage, real turn/ACK/expiry, production own cast; offline no GUI",
            requested_passives=identities,
            requested_level=level,
            expected=len(cases),
            completed=len(rows),
            native_passive_count=len(passive_cases()),
            source_before=before,
            source_after=after,
            source_stable=before == after if final else None,
            area_callbacks_enabled=os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1")
            == "1",
            native_start_events_enabled=os.environ.get("WAKFU_COMBAT_START_EVENTS", "1")
            == "1",
            tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            status_counts=dict(collections.Counter(r["status"] for r in rows)),
            incomplete_trace_cases=sum(not r["trace_complete"] for r in rows),
            installed=sum(r["installed"] for r in rows),
            activation_observed=sum(r["activation_observed"] for r in rows),
            elapsed_seconds=round(time.perf_counter() - started, 3),
            rows=rows,
        )
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(output)
        return result

    for case in cases:
        rows.append(run_case(case, terrain, origin, target))
        if rows[-1]["status"] == "blocked" or len(rows) % 10 == 0:
            save()
        print(
            json.dumps(
                dict(
                    completed=len(rows),
                    passive=case["id"],
                    status=rows[-1]["status"],
                    activated=rows[-1]["activation_observed"],
                ),
                ensure_ascii=False,
            ),
            flush=True,
        )
    result = save(True)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("rows", "source_before", "source_after")
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if not result["source_stable"]:
        raise SystemExit("Source changed; repeat before using counts")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--breed", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--passive",
        type=int,
        action="append",
        help="Repeat to recheck specific native passive IDs",
    )
    parser.add_argument(
        "--level",
        type=int,
        help="Explicit legal evaluation level; default is unlock level",
    )
    args = parser.parse_args()
    run(args.output, args.breed, identities=args.passive, level=args.level)
