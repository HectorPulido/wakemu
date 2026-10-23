"""Actual Uhu constructor -> owned turn -> helper reaction, without state gifts."""
import os
from unittest.mock import patch

from postgres_case import PostgresCase
import test_monster_representative_full_combat as representative


class UhuNativeReactionPipelineTests(PostgresCase):
    def test_native_4786_owned_turn_produces_6059_damage_state_and_resource_loss(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.inventory_items import grant
        from wakfu_server.equipment_stats import bonuses
        from wakfu_server.monsters import reference as native_monster
        from wakfu_server.aptitudes import BONUSES, BONUS_CATEGORY, budgets, validate
        from wakfu_server.wire import proto_field

        revision = os.environ.get("WAKFU_MONSTER_PRODUCER_EXPECTED_REVISION")
        if not revision:
            self.skipTest("Set explicit catalog revision for native producer replay")
        points = budgets(200)[BONUS_CATEGORY[1]]
        if BONUSES[1]["maximum"]:
            points = min(points, BONUSES[1]["maximum"])
        aptitudes = proto_field(24, 200) + proto_field(
            34, proto_field(8, 1) + proto_field(16, points)
        )
        validate({"level": 200}, aptitudes)
        callbacks = []
        effects = []
        committed = []
        calculations = []
        equipment_facts = []
        original_save_build = self.store.save_build
        original_calculate = NativeDamageHandler._calculate
        original_replay = NativeEventReplay.__call__
        original_execute = EffectDispatcher.execute
        helper_roots = (196769, 196791, 242991, 242992)
        # Original Nogord3433 loot, not companion-only default emblems.
        equipment_recipe = (
            (20722, 3),
            (20723, 5),
            (20724, 13),
            (20725, 0),
            (20726, 12),
            (20727, 4),
            (20728, 7),
            (20729, 15),
            (20730, 8),
        )
        dropped = {
            row["item_reference_id"]
            for row in native_monster(3433)["loot_definitions"]
            if row["drop_rate"] > 0
        }
        self.assertTrue({ref for ref, _ in equipment_recipe} <= dropped)

        def equipped_build(account, generation, character_id, index, blobs):
            character = self.store.character(account, character_id)
            container = next(
                row["uid"]
                for row in character["inventory_containers"]
                if row["kind"] == 0
            )
            equipment = b""
            owned = []
            for inventory_slot, (reference, slot) in enumerate(equipment_recipe):
                item = grant(
                    self.store,
                    account,
                    generation,
                    character_id,
                    reference=reference,
                    quantity=1,
                    container=container,
                    slot=inventory_slot,
                    allowed_references={ref for ref, _ in equipment_recipe},
                )
                equipment += proto_field(
                    10, proto_field(8, item["uid"]) + proto_field(16, slot)
                )
                owned.append(dict(reference=reference, uid=item["uid"], slot=slot))
            saved = original_save_build(
                account,
                generation,
                character_id,
                index,
                dict(blobs, equipment=equipment),
            )
            evaluated = bonuses(saved)
            self.assertEqual(
                set(evaluated["equipped_uids"]), {item["uid"] for item in owned}
            )
            self.assertEqual(evaluated["stats"][27] + evaluated["stats"][30], 248)
            equipment_facts.append(dict(items=owned, stats=evaluated["stats"]))
            return saved

        def calculate(handler, effect, invocation, **kwargs):
            result = original_calculate(handler, effect, invocation, **kwargs)
            if invocation.reference == 196769:
                source = handler.fight.actors[invocation.caster_id]
                target = handler.fight.actors[invocation.target_id]
                context, flags, amount = result
                calculations.append(
                    dict(
                        amount=amount,
                        flags=flags,
                        context=dict(vars(context)),
                        source_stats=dict(source.effect_stats),
                        target_stats=dict(target.effect_stats),
                    )
                )
            return result

        def replay(dispatcher, event, **kwargs):
            fight = dispatcher.retention.fight
            tracked = event.manager_actor_id == -200 and 1001 in event.event_ids
            if tracked:
                player = next(
                    actor for actor in fight.actors.values() if actor.controlled
                )
                monster = fight.actors[-200]
                before = dict(
                    hp=player.hp,
                    max_hp=player.max_hp,
                    ap=player.ap,
                    mp=player.mp,
                    player_id=player.id,
                    current_actor_id=None
                    if fight.current is None
                    else fight.current.id,
                    monster_states=tuple(
                        s.reference for s in monster.state_ledger.entries
                    ),
                    player_states=tuple(
                        s.reference for s in player.state_ledger.entries
                    ),
                    distance=sum(
                        abs(player.position[i] - monster.position[i]) for i in (0, 1)
                    ),
                )
                first_effect = len(effects)
            result = original_replay(dispatcher, event, **kwargs)
            if tracked:
                player = fight.actors[before["player_id"]]
                callbacks.append(
                    dict(
                        before=before,
                        after=dict(
                            hp=player.hp,
                            ap=player.ap,
                            mp=player.mp,
                            states=tuple(
                                s.reference for s in player.state_ledger.entries
                            ),
                        ),
                        effects=tuple(effects[first_effect:]),
                        event_ids=tuple(event.event_ids),
                        manager=event.manager_actor_id,
                        channel=event.channel,
                        outcomes=tuple(result),
                    )
                )
            return result

        def execute(dispatcher, invocation, *args, **kwargs):
            if invocation.reference in helper_roots:
                effects.append(invocation.reference)
            return original_execute(dispatcher, invocation, *args, **kwargs)

        def observe(phase, fight, evidence):
            player = next(actor for actor in fight.actors.values() if actor.controlled)
            states = tuple(s.reference for s in player.state_ledger.entries)
            evidence["uhu_callback_observations"] = callbacks
            evidence["uhu_damage_calculations"] = calculations
            evidence["uhu_admitted_equipment"] = equipment_facts
            if any(
                row["before"]["current_actor_id"] == -200 and row["channel"] == 6
                for row in callbacks
            ):
                committed.append(dict(phase=phase, hp=player.hp, states=states))

        with patch.object(NativeEventReplay, "__call__", replay), patch.object(
            EffectDispatcher, "execute", execute
        ), patch.object(self.store, "save_build", equipped_build), patch.object(
            NativeDamageHandler, "_calculate", calculate
        ):
            evidence = representative.MonsterRepresentativeFullCombatTests._case(
                self,
                4329,
                203,
                expected_revision=revision,
                observe=observe,
                stop_when=lambda fight, evidence: bool(committed),
                scripted_actions=lambda fight, character, monster: None,
                maximum_boundaries=4,
                player_aptitudes=aptitudes,
            )
        self.assertEqual(evidence["status"], "focused_native_producer_observed")
        self.assertEqual(evidence["native_initial_state_triples"], [4786, 1, 0])
        self.assertNotIn(6059, evidence["native_owned_book"])
        self.assertEqual(evidence["actions"], [])  # Helper is earned, never submitted.
        self.assertTrue(callbacks)
        self.assertEqual(len(equipment_facts), 1)
        self.assertTrue(calculations)
        self.assertTrue(
            any(row["amount"] and row["amount"] > 0 for row in calculations)
        )
        positive = next(
            (row for row in callbacks if 4788 in row["after"]["states"]), None
        )
        self.assertIsNotNone(positive, callbacks)
        before, after = positive["before"], positive["after"]
        self.assertIn(4786, before["monster_states"])
        self.assertNotIn(4866, before["monster_states"])
        self.assertNotIn(4788, before["player_states"])
        self.assertIn(before["distance"], (1, 2))
        self.assertEqual(before["hp"], before["max_hp"])
        self.assertGreater(before["max_hp"], 2050)
        self.assertGreater(after["hp"], 0)
        self.assertLess(after["hp"], before["hp"])
        self.assertGreater(before["ap"], 0)
        self.assertGreater(before["mp"], 0)
        self.assertLess(after["ap"], before["ap"])
        self.assertLess(after["mp"], before["mp"])
        self.assertTrue(set(helper_roots) <= set(positive["effects"]), positive)
        # Source casting order is damage, state, AP loss, MP loss. The shared
        # dispatcher may visit child runners more than once during preparation.
        ordered = tuple(
            dict.fromkeys(ref for ref in positive["effects"] if ref in helper_roots)
        )
        self.assertEqual(ordered, helper_roots)
        self.assertTrue(committed)
        self.assertLess(committed[-1]["hp"], before["hp"], (committed, positive))
