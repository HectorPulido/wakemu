"""Actual paid ordinary-monster producer paths; no post-admission HP grants.

The existing persisted representative bootstrap owns construction, native
initialization, resources, transaction serialization and turn ACK boundaries.
This module adds observations and stops at its source-qualified mechanism.
"""
import os
import unittest

from postgres_case import PostgresCase
from wakfu_server.combat_characteristic_percentage import characteristic_percentage
import test_monster_representative_full_combat as _representative


class OrdinaryMonsterNativeProducerTests(PostgresCase):
    def _threshold(self, reference):
        revision = os.environ.get("WAKFU_MONSTER_PRODUCER_EXPECTED_REVISION")
        if not revision:
            self.skipTest(
                "Set explicit selected catalog revision for native producer replay"
            )
        observations = []
        crossed = False
        later_npc_action = False

        def observe(phase, fight, evidence):
            nonlocal crossed, later_npc_action
            monster = fight.actors[-200]
            states = tuple(state.reference for state in monster.state_ledger.entries)
            observations.append(
                dict(
                    phase=phase,
                    hp=monster.hp,
                    maximum=monster.max_hp,
                    states=states,
                    last_actor=evidence["actions"][-1]["actor_id"]
                    if evidence["actions"]
                    else None,
                )
            )
            percentage = characteristic_percentage(monster.hp, monster.max_hp)
            if not crossed and percentage > 50:
                self.assertNotIn(4405, states)
            elif not crossed and monster.hp > 0:
                self.assertIn(4405, states)
                crossed = True
            if (
                crossed
                and phase == "cast"
                and evidence["actions"][-1]["actor_id"] == -200
            ):
                later_npc_action = True

        evidence = _representative.MonsterRepresentativeFullCombatTests._case(
            self,
            reference,
            23,
            expected_revision=revision,
            observe=observe,
            stop_when=lambda fight, evidence: later_npc_action,
            maximum_boundaries=30,
        )
        self.assertTrue(crossed)
        self.assertTrue(later_npc_action)
        self.assertEqual(evidence["status"], "focused_native_producer_observed")
        self.assertGreater(len(evidence["actions"]), 1)
        self.assertTrue(
            any(
                characteristic_percentage(row["hp"], row["maximum"]) > 50
                for row in observations
            )
        )
        self.assertTrue(
            any(
                row["hp"] > 0
                and characteristic_percentage(row["hp"], row["maximum"]) <= 50
                for row in observations
            )
        )

    def test_royal_gobball_paid_injury_produces_threshold_state(self):
        self._threshold(44)

    def test_arch_gobball_paid_injury_produces_threshold_state(self):
        self._threshold(4086)

    def _scripted_producer(self, reference, level, spell_id, kind):
        from random import Random
        from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        revision = os.environ.get("WAKFU_MONSTER_PRODUCER_EXPECTED_REVISION")
        if not revision:
            self.skipTest(
                "Set explicit selected catalog revision for native producer replay"
            )
        tracked = []
        retired = False
        observed = []
        examined_wall_attack = False
        tracked_obstacles = {}

        def records(fight):
            if kind == "summon":
                return {
                    actor.id: actor
                    for actor in fight.actors.values()
                    if getattr(actor, "native_summon_source", None) is not None
                    and actor.native_summon_source.get("caster_id") == -200
                }
            return {
                uid: row
                for uid, row in getattr(fight, "native_effect_areas", {}).items()
                if row.get("reference") == 196 and row.get("owner_id") == -200
            }

        def observe(phase, fight, evidence):
            nonlocal retired, examined_wall_attack
            owned = records(fight)
            if not tracked and owned:
                if kind == "summon":
                    identity = sorted(owned)[0]
                else:
                    player = next(
                        actor for actor in fight.actors.values() if actor.controlled
                    )
                    identity = min(
                        owned,
                        key=lambda uid: (
                            sum(
                                abs(owned[uid]["cell"][axis] - player.position[axis])
                                for axis in (0, 1)
                            ),
                            uid,
                        ),
                    )
                tracked.append(identity)
                if kind == "summon":
                    actor = owned[identity]
                    self.assertEqual(actor.native_summon_source["ref"], 6)
                    self.assertIn(identity, fight.order)
                    self.assertGreater(actor.hp, 0)
                    self.assertIn(identity, fight.native_summon_registrations)
                else:
                    from wakfu_server.combat_effect_area import native_effect_areas
                    from wakfu_server.combat_wall_area import verified_wall_constructor

                    row = owned[identity]
                    constructor = verified_wall_constructor(
                        row, native_effect_areas()["196"], fight=fight
                    )
                    self.assertEqual(constructor["hp_initial"], 1)
                    self.assertTrue(constructor["movement_blocking"])
                    self.assertTrue(constructor["los_blocking"])
                    tracked_obstacles[identity] = row["native_obstacle_id"]
            if (
                tracked
                and phase == "cast"
                and evidence["actions"][-1]["actor_id"] != -200
            ):
                identity = tracked[0]
                if kind == "summon":
                    actor = fight.actors.get(identity)
                    if actor is None or actor.hp == 0:
                        self.assertNotIn(identity, fight.order)
                        self.assertTrue(
                            any(
                                event.get("kind") == "death"
                                and event.get("actor_id") == identity
                                for event in fight.events
                            )
                        )
                        retired = True
                elif identity not in owned:
                    from wakfu_server.combat_qi_fight import current_registry
                    from wakfu_server.combat_effect_area_targets import area_targets

                    registry = current_registry(fight)
                    slot = registry.slots[tracked_obstacles[identity]]
                    self.assertTrue(
                        slot is None
                        or tuple(slot["identity"]) != ("effect_area", identity)
                    )
                    self.assertNotIn(
                        identity, {target.id for target in area_targets(fight)}
                    )
                    self.assertTrue(
                        any(
                            event.get("kind") == "damage"
                            and event.get("target_id") == identity
                            and event.get("hp") == 0
                            for event in fight.events
                        )
                    )
                    self.assertEqual(
                        evidence["actions"][-1]["area_retirements"].count(identity), 1
                    )
                    retired = True
                if kind == "wall":
                    examined_wall_attack = True
            observed.append(
                dict(
                    phase=phase,
                    owned=sorted(owned),
                    retired=retired,
                    walls={
                        str(uid): {
                            "hp": row.get("native_wall_hp_current"),
                            "completed": row.get("native_qq_bhi"),
                            "completion_source": row.get("native_qq_guard_source"),
                            "obstacle_id": row.get("native_obstacle_id"),
                        }
                        for uid, row in owned.items()
                    }
                    if kind == "wall"
                    else {},
                    tracked_events=[
                        event
                        for event in fight.events
                        if tracked
                        and (
                            event.get("target_id") == tracked[0]
                            or event.get("actor_id") == tracked[0]
                        )
                    ],
                )
            )
            evidence["native_producer_observations"] = observed

        def script(fight, char, monster):
            current = fight.current
            owned = records(fight)
            if tracked:
                if not current.controlled:
                    return None
                record = owned.get(tracked[0])
                if record is None:
                    return None
                target_id = record.id if kind == "summon" else None
                cell = record.position if kind == "summon" else tuple(record["cell"])
                return dict(spell_id=4780, target_id=target_id, target_cell=cell)
            if current.id != -200:
                return None
            book = owned_spells(fight, {-200: monster})
            self.assertIn(spell_id, book)
            casting, table_index = native_casting_table(spell_id, book[spell_id])
            minimum, maximum = casting["levels"][table_index][:2]
            player_casting, player_index = native_casting_table(4780, char["level"])
            player_maximum = player_casting["levels"][player_index][1]
            source = snapshot(fight)
            occupied = {
                actor.position for actor in fight.actors.values() if actor.hp > 0
            }
            player = fight.actors[char["id"]]
            choices = sorted(
                (
                    cell
                    for cell in (
                        (player.position,) if kind == "wall" else fight.walkable
                    )
                    if (kind == "wall" or cell not in occupied)
                    and minimum
                    <= sum(abs(cell[i] - current.position[i]) for i in (0, 1))
                    <= maximum
                    and (
                        kind == "wall"
                        or 1
                        <= sum(abs(cell[i] - player.position[i]) for i in (0, 1))
                        <= player_maximum
                    )
                ),
                key=lambda cell: (
                    sum(abs(cell[i] - player.position[i]) for i in (0, 1)),
                    cell,
                ),
            )
            errors = []
            for cell in choices:
                request = dict(
                    type="cast",
                    spellId=spell_id,
                    level=book[spell_id],
                    target=list(cell),
                    targetId=player.id if kind == "wall" else None,
                )
                try:
                    transaction = prepare_npc_spell(
                        fight,
                        request,
                        char,
                        {-200: monster},
                        encode_deck([4780]),
                        action_id=100 + fight.turn_id,
                        rng=Random(7),
                    )
                    self.assertEqual(snapshot(fight), source)
                    if records(transaction.fight):
                        return dict(
                            spell_id=spell_id,
                            target_id=player.id if kind == "wall" else None,
                            target_cell=cell,
                        )
                    errors.append(
                        dict(
                            cell=cell,
                            reason="native preview produced no selected owned object",
                        )
                    )
                except Exception as error:
                    self.assertEqual(snapshot(fight), source)
                    errors.append(
                        dict(cell=cell, error=type(error).__name__, reason=str(error))
                    )
            self.fail("No genuine native producer target: " + repr(errors))

        evidence = _representative.MonsterRepresentativeFullCombatTests._case(
            self,
            reference,
            level,
            expected_revision=revision,
            observe=observe,
            stop_when=lambda fight, evidence: retired or examined_wall_attack,
            maximum_boundaries=16,
            scripted_actions=script,
            player_position=(-11, -7, -1) if kind == "wall" else (-9, -7, -1),
            rollback_on_first_controlled_cast=kind == "wall",
        )
        self.assertTrue(tracked)
        self.assertTrue(
            retired, "Native wall lifecycle after first paid attack: " + repr(observed)
        )
        self.assertEqual(evidence["status"], "focused_native_producer_observed")
        self.assertTrue(any(row["actor_id"] == -200 for row in evidence["actions"]))
        self.assertTrue(any(row["actor_id"] != -200 for row in evidence["actions"]))
        self.assertGreater(len(observed), 1)
        if kind == "wall":
            self.assertTrue(
                any(identity > 0 for identity in evidence["serializer_rollback_actors"])
            )

    def test_tofona_native_paid_1152_birth_and_paid_lethal_retirement(self):
        self._scripted_producer(5, 10, 1152, "summon")

    def test_demonic_rose_native_paid_1910_wall196_birth_and_paid_destruction(self):
        self._scripted_producer(95, 40, 1910, "wall")


if __name__ == "__main__":
    unittest.main()
