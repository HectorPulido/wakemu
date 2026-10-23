"""Inspect a retained Ombrage window through isolated native transactions."""
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import struct
import traceback
from unittest.mock import patch


def diagnose(checkpoint, output):
    from test_ombrage_native_paid_clock import back_path
    from wakfu_server.combat_damage_handler import NativeDamageHandler
    from wakfu_server.combat_spell_grant import granted_spells
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_los import authoritative_visible
    from wakfu_server.combat_effect_dispatch import EffectDispatcher
    from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount

    original = checkpoint["runtime"]
    runtime = deepcopy(original)
    characters, monsters, decks = (
        checkpoint[key] for key in ("characters", "monsters", "decks")
    )
    rng, common, stats = (checkpoint[key] for key in ("rng", "common", "stats"))
    first = next(iter(characters))
    initial_rng = rng.getstate()
    initial_fight = deepcopy(original.fight)
    result = dict(
        scope="isolated_native_window_damage_attribution",
        boundaries=[],
        casts=[],
        traces=[],
    )
    original_calculate = NativeDamageHandler._calculate
    original_call = NativeDamageHandler.__call__
    original_execute = EffectDispatcher.execute
    original_set = NativeRunnerAmount.set_calculated
    original_mutate = NativeRunnerAmount.mutate
    active_effects = []

    def execute(dispatcher, invocation, **kwargs):
        active_effects.append(
            dict(
                reference=invocation.reference,
                caster=invocation.caster_id,
                target=invocation.target_id,
                base_uid=invocation.base_uid,
            )
        )
        try:
            return original_execute(dispatcher, invocation, **kwargs)
        finally:
            active_effects.pop()

    def record_mutation(runner, before, operation):
        if runner.owner == "eXt" and before is not None and before != runner.value:
            result.setdefault("runner_mutations", []).append(
                dict(
                    uid=runner.uid,
                    before=before,
                    after=runner.value,
                    operation=operation,
                    effects=list(active_effects),
                    stack=[
                        dict(
                            file=frame.filename, line=frame.lineno, function=frame.name
                        )
                        for frame in traceback.extract_stack(limit=12)
                    ],
                )
            )

    def set_amount(runner, value):
        before = getattr(runner, "value", None)
        original_set(runner, value)
        record_mutation(runner, before, "set")

    def mutate_amount(runner, *args, **kwargs):
        before = runner.value
        original_mutate(runner, *args, **kwargs)
        record_mutation(runner, before, dict(args=args, kwargs=kwargs))

    def facts(fight):
        boss = fight.actors[-200]
        return dict(
            hp=boss.hp,
            maximum=boss.max_hp,
            minimum=boss.effect_minima[1],
            states=[(row.reference, row.level) for row in boss.state_ledger.entries],
            retained=[
                dict(row)
                for row in fight.native_retained_records.values()
                if row.get("target_id") == -200
            ],
            direction=boss.direction,
        )

    def calculate(handler, effect, invocation, **kwargs):
        value = original_calculate(handler, effect, invocation, **kwargs)
        if invocation.target_id == -200 and invocation.caster_id in characters:
            context = value[0]
            result["traces"].append(
                dict(
                    stage="calculated",
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    context=asdict(context) if is_dataclass(context) else str(context),
                    interpreted=value[1],
                    amount=value[2],
                    boss=facts(handler.fight),
                )
            )
        return value

    def apply_damage(handler, effect, values, invocation):
        relevant = invocation.target_id == -200 and invocation.caster_id in characters
        uid = invocation.native_running_uid
        runner = handler.runner_modifiers.get(uid)
        before = facts(handler.fight) if relevant else None
        value = original_call(handler, effect, values, invocation)
        if relevant:
            result["traces"].append(
                dict(
                    stage="applied",
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    result=bool(value),
                    before=before,
                    after=facts(handler.fight),
                    runner=None if runner is None else dict(vars(runner)),
                )
            )
        return value

    def prepare(identity, reference):
        fight = runtime.fight
        grants = granted_spells(fight, identity)
        boss = fight.actors[-200]
        return checkpoint["prepare_server_spell"](
            struct.pack(
                ">qqiih",
                identity,
                grants[reference]["uid"]
                if reference in grants
                else (identity << 32) | reference,
                *boss.position
            ),
            characters[identity],
            monsters,
            fight,
            characters[identity]["account_id"],
            decks[identity],
            action_id=runtime.action_id + 1,
            critical=None,
            **common,
            line_of_sight=lambda origin, target, phase: authoritative_visible(
                1229,
                origin,
                target,
                phase,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in phase.actors.values()
                    if actor.hp > 0
                },
            )
        )

    try:
        with patch.object(NativeDamageHandler, "_calculate", calculate), patch.object(
            NativeDamageHandler, "__call__", apply_damage
        ), patch.object(EffectDispatcher, "execute", execute), patch.object(
            NativeRunnerAmount, "set_calculated", set_amount
        ), patch.object(
            NativeRunnerAmount, "set_applied", set_amount
        ), patch.object(
            NativeRunnerAmount, "mutate", mutate_amount
        ):
            for _ in range(12):
                for _ in range(32):
                    if runtime.awaiting_ack is None:
                        break
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                else:
                    raise AssertionError("Cloned native ACK chain exhausted")
                fight = runtime.fight
                current = fight.current
                result["boundaries"].append(
                    dict(
                        turn=fight.turn_id,
                        table=fight.native_table_turn,
                        current=None if current is None else current.id,
                        boss=facts(fight),
                    )
                )
                if fight.phase != "active" or current is None:
                    break
                if current.id in characters:
                    identity = current.id
                    for _ in range(8):
                        fight = runtime.fight
                        invulnerable = any(
                            row.reference == 5657
                            for row in fight.actors[-200].state_ledger.entries
                        )
                        path = back_path(
                            fight,
                            identity,
                            require_back=invulnerable,
                            maximum_range=3,
                            require_los=False,
                        )
                        if path is None:
                            break
                        if path:
                            checkpoint["apply_client"](
                                runtime,
                                fight.actors[identity].owner_id,
                                struct.pack(">q", identity)
                                + b"".join(struct.pack(">iih", *cell) for cell in path),
                                lambda actor: stats(actor, runtime.fight),
                                runtime_stats_serializer=stats,
                                area_provider=lambda candidate, **kw: checkpoint[
                                    "prepare_area_movement"
                                ](
                                    characters[first],
                                    monsters,
                                    candidate,
                                    decks[first],
                                    **common,
                                    **kw
                                ),
                            )
                        tx = None
                        for reference in (
                            (8403, 4780, 4777, 4781)
                            if invulnerable
                            else (4777, 4780, 4781)
                        ):
                            before_rng = rng.getstate()
                            try:
                                tx = prepare(identity, reference)
                            except ValueError as error:
                                rng.setstate(before_rng)
                                result["casts"].append(
                                    dict(
                                        actor=identity,
                                        reference=reference,
                                        rejected=str(error),
                                    )
                                )
                            else:
                                break
                        if tx is None:
                            break
                        result["casts"].append(
                            dict(
                                actor=identity,
                                reference=reference,
                                source=runtime.fight.actors[identity].position,
                                before=facts(runtime.fight),
                                preview=facts(tx.fight),
                                costs=tx.plan["costs"],
                            )
                        )
                        if not invulnerable:
                            result[
                                "status"
                            ] = "first_vulnerable_native_damage_preview_observed"
                            return result
                        checkpoint["commit_spell_transaction"](
                            runtime, tx, stats_serializer=stats
                        )
                checkpoint["advance_actual_turn"](runtime)
            result["status"] = "bounded_clone_did_not_reach_vulnerable_preview"
            return result
    finally:
        rng.setstate(initial_rng)
        result["original_rng_unchanged"] = rng.getstate() == initial_rng
        result["original_turn_unchanged"] = (
            original.fight.turn_id == initial_fight.turn_id
        )
        result["original_hp_positions_unchanged"] = all(
            (actor.hp, actor.position, actor.ap, actor.mp)
            == (
                initial_fight.actors[key].hp,
                initial_fight.actors[key].position,
                initial_fight.actors[key].ap,
                initial_fight.actors[key].mp,
            )
            for key, actor in original.fight.actors.items()
        )
        Path(output).write_text(json.dumps(result, indent=2, default=str) + "\n")
