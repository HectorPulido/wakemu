"""Original Frenzy/Fury consumers on one accepted ordinary wave component.

Requires the explicitly bounded semantic manifest; this is not a full Ready,
paid raid or client acceptance test. No catalog fallback or event spy replaces
native equipment custody, target resolution, state or characteristic handlers.
The component binds the catalog dependency to its verified original compiled
closure, shared with its real pin and dispatcher; it does not build unrelated
player-class or NPC gameplay catalogs.
"""
from copy import deepcopy
from contextlib import ExitStack, contextmanager
from dataclasses import fields, is_dataclass
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def _diagnostic_value(value, depth=0):
    """Serialize observations without querying runtime providers or iterators."""
    if value is None or type(value) in (str, int, float, bool):
        return value
    if depth >= 7:
        return {"type": type(value).__name__, "depth_limit": True}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _diagnostic_value(getattr(value, field.name), depth + 1)
            for field in fields(value)
        }
    if type(value) is dict:
        return {
            str(key): _diagnostic_value(item, depth + 1) for key, item in value.items()
        }
    if type(value) in (tuple, list, set, frozenset):
        return [_diagnostic_value(item, depth + 1) for item in value]
    return {"type": type(value).__name__}


@contextmanager
def _wave_diagnostic(dispatcher, label):
    """Opt-in pass-through tracing of calls the real publisher already makes."""
    output = os.environ.get("WAKFU_SUBLIMATION_WAVE_DIAGNOSTIC")
    if not output:
        yield
        return
    from wakfu_server import combat_equipment_external_events as external
    from wakfu_server import combat_equipment_finish as finish
    from wakfu_server import combat_event_replay as replay
    from wakfu_server import combat_effect_dispatch as dispatch

    fight = dispatcher.native_retention.fight
    events = []
    delivery = {}

    def observe(name, original):
        def invoke(*args, **kwargs):
            record = dict(
                call=name,
                args=_diagnostic_value(args),
                kwargs=_diagnostic_value(kwargs),
            )
            events.append(record)
            try:
                result = original(*args, **kwargs)
            except BaseException as error:
                record["error"] = dict(type=type(error).__name__, message=str(error))
                raise
            # A view's entries are the existing materialized tuple. Never
            # enumerate a provider or replay the condition to explain a result.
            record["result"] = _diagnostic_value(
                result.entries if name == "retained.view" else result
            )
            return result

        return invoke

    def retained_rows():
        return _diagnostic_value(
            dict(
                groups=getattr(fight, "native_owned_group_effects", {}),
                records=getattr(fight, "native_retained_records", {}),
                equipment=getattr(fight, "native_owned_equipment_initializations", {}),
                carriers={
                    identity: actor.state_ledger.entries
                    for identity, actor in fight.actors.items()
                },
            )
        )

    before = retained_rows()
    with ExitStack() as patches:
        for owner, attribute, name in (
            (external, "qualified_uids", "qualified_uids"),
            (finish, "_qualified_sources", "qualified_sources"),
            (finish, "_scope", "qualified_scope"),
            (dispatcher.native_retention, "view", "retained.view"),
            (dispatcher, "replay_event", "replay_event"),
            (dispatcher, "execute_activation", "execute_activation"),
            (replay, "subscription_selection", "subscription_selection"),
            (dispatch, "evaluate_condition", "evaluate_condition"),
        ):
            patches.enter_context(
                patch.object(owner, attribute, observe(name, getattr(owner, attribute)))
            )
        try:
            yield delivery
        finally:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        dict(
                            label=label,
                            before=before,
                            events=events,
                            delivery=_diagnostic_value(delivery),
                            after=retained_rows(),
                            wave=_diagnostic_value(
                                getattr(fight, "rift_wave_state", None)
                            ),
                            definitions=_diagnostic_value(
                                {
                                    str(
                                        reference
                                    ): dispatcher.native_retention.metadata[
                                        "effects"
                                    ].get(
                                        str(reference)
                                    )
                                    for reference in (
                                        392414,
                                        392415,
                                        392416,
                                        392417,
                                        392418,
                                        392419,
                                        392420,
                                        392421,
                                    )
                                }
                            ),
                        ),
                        ensure_ascii=True,
                    )
                    + "\n"
                )


class SublimationWaveConsumerTests(unittest.TestCase):
    def test_original_wave_damage_counter_next_start_and_private_failure(self):
        tools = str(Path(__file__).resolve().parents[1] / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        from sublimation_semantic_fixture import build_fixture

        manifest = os.environ.get("WAKFU_SUBLIMATION_SEMANTIC_MANIFEST")
        if not manifest:
            raise RuntimeError("1048 execution requires the bounded semantic manifest")

        # One BASIC per physical item. Each source has its own genuine pin,
        # source container, state root and already-delivered opening1028.
        variants = ((27126, 5995, 392416, 10), (27153, 6028, 392420, 5))
        selected = os.environ.get("WAKFU_SUBLIMATION_WAVE_VARIANT")
        if selected is not None:
            if selected not in {str(row[0]) for row in variants}:
                raise ValueError("Unknown original wave consumer variant")
            variants = tuple(row for row in variants if str(row[0]) == selected)
        for scroll, counter_state, damage_listener, expected_gain in variants:
            with self.subTest(scroll=scroll):
                fixture = build_fixture(scroll, manifest)
                # The production scope reader normally obtains the process's
                # complete catalog. This component supplies the exact original
                # closure already used for its real pin and native dispatcher.
                # All digest/custody/UID checks and actual event consumers run.
                with patch(
                    "wakfu_server.combat_server_spell.compiled_runtime_catalog",
                    return_value=fixture.compiled,
                ):
                    self._consumer_case(
                        fixture, counter_state, damage_listener, expected_gain
                    )
                print(f"Native wave consumer variant {scroll} PASS", flush=True)
                # Each variant owns an independent static compilation. Releasing
                # that worker-only cache avoids retaining the previous graph
                # while constructing the next fixture under the same RSS cap.
                from wakfu_server.combat_owned_equipment_factory import (
                    _compiled_sources,
                )
                import gc

                del fixture
                _compiled_sources.cache_clear()
                gc.collect()

    def _consumer_case(self, fixture, counter_state, damage_listener, expected_gain):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_equipment_wave_events import deliver_registered_wave
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_turn_events import deliver_turn_start
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.rift_npc_creation import install_native_wave
        from wakfu_server.combat_entry_executor import private_entry_preview
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_random_transaction import rollback_external_rng

        source = fixture.fight
        self.assertIsInstance(source, Fight)
        player_id = fixture.character["id"]
        player = source.actors[player_id]
        self.assertIs(source.current, player)
        self.assertTrue(player.controlled)
        self.assertIsNotNone(player.effect_stats)
        self.assertTrue(source.native_owned_equipment_initializations)
        self.assertFalse(
            any(s.reference == counter_state for s in player.state_ledger.entries)
        )
        source_bytes = snapshot(source)
        rng_before = fixture.factory.transaction_rng.getstate()
        dispatcher, packets = fixture.dispatcher_for(source)
        packet_before = tuple(packets)
        # No pending ordinary wave is not a notification opportunity.
        with self.assertRaises(ValueError):
            deliver_registered_wave(
                dispatcher, actors=(), monsters=(), player_ids=(player_id,)
            )
        self.assertEqual(snapshot(source), source_bytes)
        self.assertEqual(tuple(packets), packet_before)

        @rollback_external_rng
        def admit(*, notify, fail=False, check_foreign=False, rng):
            _, preview = private_entry_preview(
                source, snapshot=source_snapshot, clone=deepcopy
            )
            sources = deepcopy(fixture.monster_sources)
            enemies = [
                a
                for a in preview.actors.values()
                if a.team == 1 and preview._in_play(a)
            ]
            self.assertEqual(len(enemies), 1)
            old = enemies[0]
            old_source = sources[old.id]
            # A declared ordinary one-species component uses the real policy
            # selector and native NPC constructor. It is not claimed as the
            # original balance/composition of any complete Rift catalog.
            preview.rift_wave_state = dict(
                instance_id=9,
                wave=1,
                turn_budget=40,
                seed="1048-component",
                wave_actor_ids=[old.id],
                catalog=dict(
                    type="INFINITE_WAVE", wave_id=1, species_refs=[old_source["ref"]]
                ),
                policy=dict(
                    policy_kind="local_dev_not_official",
                    enabled=True,
                    turn_budget=40,
                    max_members=6,
                    classic_wave_size=1,
                    ultimate_wave_size=1,
                    starting_wave=1,
                    selection="uniform_with_replacement",
                    scaling="native_base_grade",
                    rewards="callback_only",
                ),
            )
            # The real Fight death/outcome path stages pending_wave. This is
            # fixture wave clearance, not a paid spell or injected event1048.
            preview.apply_effect_damage(player_id, old.id, old.hp)
            self.assertFalse(preview._in_play(old))
            self.assertIsNotNone(preview.rift_wave_state["pending_wave"])
            occupied = {a.position for a in preview.actors.values()}
            free = sorted(set(preview.walkable) - occupied)
            self.assertTrue(
                free, "bounded semantic terrain needs one native birth cell"
            )
            x, y, z = free[0]
            born = dict(
                old_source, id=min(preview.actors) - 1, x=x, y=y, z=z, instance_id=9
            )
            sources[born["id"]] = born
            preview.rift_monsters = deepcopy(sources)
            observed = {}

            def initialize_wave(fight, actors, monsters):
                live, outbox = fixture.dispatcher_for(fight, monster_sources=sources)
                observed.update(dispatcher=live, packets=outbox, actors=actors)
                if check_foreign:
                    before = snapshot(fight)
                    before_packets = tuple(outbox)
                    with self.assertRaises(ValueError):
                        deliver_registered_wave(
                            live,
                            actors=actors,
                            monsters=monsters,
                            player_ids=(999999,),
                        )
                    self.assertEqual(snapshot(fight), before)
                    self.assertEqual(tuple(outbox), before_packets)
                if notify:
                    with _wave_diagnostic(
                        live,
                        dict(
                            counter_state=counter_state,
                            fail=fail,
                            check_foreign=check_foreign,
                        ),
                    ) as diagnostic:
                        observed["wave_outcomes"] = deliver_registered_wave(
                            live,
                            actors=actors,
                            monsters=monsters,
                            player_ids=(player_id,),
                        )
                        if diagnostic is not None:
                            diagnostic["outcomes"] = observed["wave_outcomes"]
                    first = snapshot(fight)
                    first_packets = tuple(outbox)
                    self.assertEqual(
                        deliver_registered_wave(
                            live,
                            actors=actors,
                            monsters=monsters,
                            player_ids=(player_id,),
                        ),
                        (),
                    )
                    self.assertEqual(snapshot(fight), first)
                    self.assertEqual(tuple(outbox), first_packets)
                if fail:
                    raise ValueError("after actual native1048 consumer registration")
                return tuple(outbox)

            births = install_native_wave(
                preview,
                [born],
                initialize_actor=lambda *_: (),
                initialize_wave=initialize_wave,
            )
            self.assertIn(13091, [opcode for opcode, _ in births])
            self.assertEqual(preview.rift_wave_state["wave"], 2)
            return preview, observed, sources

        # A private failure discards the registered descendants, wave receipt,
        # QI additions and packet outbox together, leaving the source untouched.
        try:
            with self.assertRaisesRegex(ValueError, "after actual native1048"):
                admit(notify=True, fail=True, rng=fixture.factory.transaction_rng)
            self.assertEqual(snapshot(source), source_bytes)
            self.assertEqual(fixture.factory.transaction_rng.getstate(), rng_before)
        finally:
            fixture.factory.transaction_rng.setstate(rng_before)

        # Native new NPC birth without this wave publisher must not accidentally
        # grant the source owner's wave-only damage counter.
        without, control, _ = admit(notify=False, rng=fixture.factory.transaction_rng)
        baseline = without.actors[player_id].effect_stats[48]
        target = control["actors"][0]
        control["dispatcher"].execute(
            EffectInvocation(
                fixture.damage_reference,
                1,
                player_id,
                target.id,
                target.position,
            )
        )
        self.assertFalse(
            any(
                s.reference == counter_state
                for s in without.actors[player_id].state_ledger.entries
            )
        )
        self.assertEqual(without.actors[player_id].effect_stats[48], baseline)
        fixture.factory.transaction_rng.setstate(rng_before)

        # Actual wave callback registers the original per-new-fighter listener,
        # then genuine native damage executes its original state child.
        preview, applied, _ = admit(
            notify=True, check_foreign=True, rng=fixture.factory.transaction_rng
        )
        live = applied["dispatcher"]
        self.assertTrue(
            any(
                entry.generic_effect == damage_listener
                for entry in live.native_retention.view().entries
            )
        )
        self.assertEqual(
            snapshot(source), source_bytes
        )  # successful preview is private too
        before = preview.actors[player_id].effect_stats[48]
        target = applied["actors"][0]
        hp_before = target.hp
        live.execute(
            EffectInvocation(
                fixture.damage_reference,
                1,
                player_id,
                target.id,
                target.position,
            )
        )
        self.assertLess(target.hp, hp_before)
        states = [
            s
            for s in preview.actors[player_id].state_ledger.entries
            if s.reference == counter_state
        ]
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].level, 1)
        self.assertEqual(preview.actors[player_id].effect_stats[48], before)

        # Move the actual timeline to the next owner START, rather than setting
        # a turn number or directly invoking the scalar reward leaf.
        preview.end_turn(
            fixture.owner_id, player_id, preview.actors[player_id].turn_count
        )
        for _ in range(len(preview.actors) + 1):
            if preview.current.id == player_id:
                break
            preview.end_server_turn(preview.current.id, preview.turn_id)
        self.assertEqual(preview.current.id, player_id)
        deliver_turn_start(live, actor_id=player_id)
        self.assertEqual(
            preview.actors[player_id].effect_stats[48], before + expected_gain
        )
        self.assertFalse(
            any(
                s.reference == counter_state
                for s in preview.actors[player_id].state_ledger.entries
            )
        )
        self.assertEqual(snapshot(source), source_bytes)
