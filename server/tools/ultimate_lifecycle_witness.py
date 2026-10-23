"""Bounded genuine Magmog turn/phase witness; validation owner executes only.

No forced state, HP, resource, property or spell-book edits. Missing phase
production remains an unresolved native scenario, never an automatic pass.
"""
import hashlib
from random import Random
import struct
import traceback
from unittest.mock import patch


def run_witness():
    result = {
        "status": "pending",
        "scope": "Magmog42 level110 genuine owned turn1002/1037 phase; no full encounter claim",
        "steps": [],
        "triggered": [],
    }
    try:
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_witness_fixture import legal_witness_cell
        from native_tank_witness_fixture import native_tank_fixture
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_triggered_spell_handler import (
            NativeTriggeredSpellHandler,
        )
        from wakfu_server.combat_effect_removal import _identity_fields

        enemy_cell, placement = legal_witness_cell()
        native_fixture, fixture_facts = native_tank_fixture(validator, feca=True)
        result["placement"] = placement
        result["native_player_fixture"] = fixture_facts
        result["enemy_cell"] = list(enemy_cell)
        with original_bootstrap_publication() as publication:
            fight, character, monsters, deck = native_fixture(
                42, 110, enemy_cell, native_lifecycle=True
            )
        result["recorded_publication"] = publication
        assert fight.native_start_event_delivered
        result["initialization"] = fight.native_npc_initialization_receipts
        rng = Random(0)

        def serialize(actor, state):
            if getattr(actor, "native_summon_source", None) is not None:
                return registered_summon_stats(actor, state, character["map_id"])
            kw = {
                "wp_current": actor.effect_stats[4],
                "wp_maximum": actor.effect_maxima[4],
                "fight": state,
            }
            return (
                actual_actor_stats(character, actor, state.id, **kw)
                if actor.controlled
                else actual_monster_actor_stats(
                    monsters[actor.id], actor, state.id, **kw
                )
            )

        runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=serialize,
            turn_start_provider=lambda p, **b: prepare_server_turn_start(
                character,
                monsters,
                p,
                deck,
                rng=rng,
                native_events=True,
                area_callbacks=True,
                **b
            ),
            turn_end_provider=lambda p, **b: prepare_server_turn_end(
                character, monsters, p, deck, rng=rng, **b
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character, monsters, deck, action_id=action_id, critical=False, rng=rng
            )[0],
        )

        def grade():
            return max(
                (
                    e.level
                    for e in runtime.fight.actors[-200].state_ledger.entries
                    if e.reference == 7335
                ),
                default=0,
            )

        packets = []
        result["paid_defense_casts"] = []

        def advance_buff_runtime(runtime, actor_id):
            from wakfu_server.combat_server_spell import prepare_server_spell
            from wakfu_server.combat_spell_commit import commit_spell_transaction
            from wakfu_server.combat_spell_grant import granted_spells
            from wakfu_server.combat_los import authoritative_visible
            from wakfu_server.combat_geometry_snapshot import source_snapshot

            for _ in range(len(runtime.fight.actors) * 2 + 1):
                actor = runtime.fight.current
                if actor is None:
                    break
                if actor.id == actor_id:
                    return
                if actor.controlled:
                    if not any(e.reference == 6364 for e in actor.state_ledger.entries):
                        assert 7009 in granted_spells(
                            runtime.fight, actor.id
                        ), "Native Feca ready grant absent"
                        before_state = source_snapshot(runtime.fight)
                        transaction = prepare_server_spell(
                            struct.pack(">qqiih", actor.id, 7009, *actor.position),
                            character,
                            monsters,
                            runtime.fight,
                            actor.owner_id,
                            deck,
                            action_id=runtime.action_id + 1,
                            line_of_sight=authoritative_visible,
                            critical=False,
                            rng=rng,
                        )
                        assert (
                            source_snapshot(runtime.fight) == before_state
                        ), "Defense preparation mutated source"
                        costs = transaction.plan["costs"]
                        assert (
                            costs["ap"] == 2 and costs["wp"] == 1
                        ), "Native PeaceArmor costs differ from source recipe"
                        defense = list(
                            commit_spell_transaction(
                                runtime, transaction, stats_serializer=serialize
                            )
                        )
                        packets.extend(defense)
                        assert any(
                            e.reference == 6364
                            for e in runtime.fight.actors[actor.id].state_ledger.entries
                        ), "Paid PeaceArmor state not installed"
                        result["paid_defense_casts"].append(
                            {
                                "turn_id": runtime.fight.turn_id,
                                "spell_id": 7009,
                                "costs": costs,
                                "packets": len(defense),
                                "hp": runtime.fight.actors[actor.id].hp,
                            }
                        )
                    packets.extend(
                        runtime.end_turn(
                            actor.owner_id, actor.id, current_wire_turn(runtime.fight)
                        )
                    )
                else:
                    packets.extend(
                        runtime.end_server_turn(actor.id, runtime.fight.turn_id)
                    )
                if runtime.awaiting_ack is not None:
                    packets.extend(
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    )
            raise ValueError("Native defended scene could not reach actual Magmog turn")

        original = NativeTriggeredSpellHandler.__call__

        def observed(handler, effect, values, invocation):
            outcome = original(handler, effect, values, invocation)
            if outcome:
                result["triggered"].append(
                    {
                        "reference": invocation.reference,
                        "caster_id": invocation.caster_id,
                        "turn_id": handler.fight.turn_id,
                        "parameters": list(effect["parameters"]),
                    }
                )
            return outcome

        with patch.object(NativeTriggeredSpellHandler, "__call__", observed):
            packets.extend(runtime.turn_started())
            for cycle in range(6):
                if (
                    runtime.fight.phase != "active"
                    or runtime.fight.actors[-200].hp <= 0
                ):
                    break
                advance_buff_runtime(runtime, -200)
                initial = grade()
                pre = runtime.fight.turn_id
                delivery = runtime.end_server_turn(-200, pre)
                packets.extend(delivery)
                after_end = grade()
                if runtime.awaiting_ack is not None:
                    packets.extend(
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    )
                result["steps"].append(
                    {
                        "cycle": cycle + 1,
                        "turn_id": pre,
                        "before": initial,
                        "after_end": after_end,
                        "hp": runtime.fight.actors[-200].hp,
                        "phase": runtime.fight.phase,
                        "packets": len(delivery),
                    }
                )
                if any(t["reference"] == 333127 for t in result["triggered"]):
                    break
        result["packets"] = [
            {
                "opcode": op,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
            for op, body in packets
        ]
        result["final_grade"] = grade()
        assert result["steps"], "No actual owned end boundary reached"
        assert any(
            t["reference"] == 333127 and t["caster_id"] == -200
            for t in result["triggered"]
        ), "Genuine turn phase did not execute native333127→7515 within6cycles"
        phase_packets = []
        for op, body in packets:
            if (
                op == 12613
                and len(body) >= 19
                and struct.unpack_from(">i", body, 13)[0] == 426
            ):
                size = struct.unpack_from(">h", body, 17)[0]
                fields = _identity_fields(body[19 : 19 + size])
                if fields.get(3) == 333127:
                    phase_packets.append(
                        {
                            "opcode": op,
                            "bytes": len(body),
                            "sha256": hashlib.sha256(body).hexdigest(),
                            "generic_effect": fields[3],
                            "uid": fields.get(1),
                        }
                    )
        result["phase_packets"] = phase_packets
        assert phase_packets, "No exact333127 eYZ application delivered"
        result["status"] = "native_phase_callback_executed"
    except Exception as error:
        result.update(
            error_type=type(error).__name__,
            error=str(error),
            traceback=traceback.format_exc(),
        )
        if "runtime" in locals():
            actual = runtime.fight
            result["terminal_snapshot"] = {
                "phase": actual.phase,
                "turn_id": actual.turn_id,
                "current": None if actual.current is None else actual.current.id,
                "awaiting_ack": runtime.awaiting_ack,
                "pending_packets": len(runtime.pending),
                "actors": {
                    str(uid): {
                        "hp": actor.hp,
                        "maximum_hp": actor.max_hp,
                        "position": actor.position,
                        "states": [
                            [e.reference, e.level] for e in actor.state_ledger.entries
                        ],
                        "resources": {str(k): actor.effect_stats[k] for k in (2, 3, 4)},
                    }
                    for uid, actor in actual.actors.items()
                },
            }

    return result
