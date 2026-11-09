import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from wakfu_server.wakia_bridge.wakfu_ai.bridge import jondo_summon_estimate as subject
from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import (
    invariant_summon_casting,
)


class SummonEstimateTests(unittest.TestCase):
    def setUp(self):
        subject._BOOKS.clear()
        self.actor = NS(id=7, hp=10, team=0)
        self.summon = NS(
            id=9,
            hp=10,
            team=0,
            position=(1, 0, 0),
            direction=1,
            effective_level=20,
            native_controller_id=7,
            native_summoned_from_symbiot=False,
            native_summon_source=dict(
                ref=1236,
                level=20,
                caster_id=7,
                controller_id=7,
                native_relation_source="big.new_bje.fdt_initial_registration",
                native_symbiot_source="eZl.new_eHD.pRO_false",
            ),
            native_summon_action_book=dict(
                producer="big.new_bje.bz.aQc.bPD",
                profile=1236,
                descriptor_level=20,
                actions=[dict(uid=100, reference=100, level=20)],
            ),
            spell_ap_cost_modifiers={},
            spell_range_modifiers={},
            effect_stats={2: 6},
            state_ledger=NS(entries=[]),
        )
        self.fight = NS(
            actors={7: self.actor, 9: self.summon},
            native_summon_registrations={
                9: dict(actor_id=9, caster_id=7, controller_id=7)
            },
        )
        self.oracle = NS(descriptor=lambda fight, actor: {})
        self.source = dict(
            fightInstanceId="fight", fightId=1, catalogRevision="revision"
        )
        self.spells = [
            dict(
                id=100,
                grade=20,
                cost=3,
                minRange=1,
                maxRange=4,
                nativeCosts=dict(mp=0, wp=0),
                unknownProjection=[],
                rows=[
                    dict(
                        kind="damage",
                        target="enemy",
                        amount=12,
                        conditional=False,
                        probability=100,
                        element="fire",
                        nativeCoefficientMask=3,
                        nativeDamageFlags=[],
                        nativeLocalization=False,
                        nativeBase=dict(kind=0, sourceBindingKnown=True),
                    )
                ],
            )
        ]
        self.control = patch.object(
            subject, "effective_server_controlled", return_value=True
        )
        self.team = patch.object(
            subject,
            "effective_affiliation",
            side_effect=lambda fight, actor: actor.team,
        )
        self.control.start()
        self.team.start()
        self.addCleanup(self.control.stop)
        self.addCleanup(self.team.stop)

    def remember(self):
        subject.remember(
            self.oracle,
            self.fight,
            self.summon,
            self.source,
            {100: 20},
            self.spells,
            {(100, 20)},
        )

    def read(self, source=None, visible=None):
        return subject.estimates(
            self.oracle,
            self.fight,
            self.actor,
            [self.summon] if visible is None else visible,
            source or self.source,
        )

    def test_reuses_owned_projection_and_invalidates_live_dependencies(self):
        self.spells[0]["rows"][0]["nativeDamageFlags"] = [22]
        self.spells[0]["rows"][0]["nativeLocalization"] = True
        self.remember()
        self.assertEqual(self.read()[0]["spells"][0]["damage"], 12)
        self.assertEqual(self.read()[0]["spells"][0]["nativeDamageFlags"], [22])
        self.assertEqual(self.read(visible=[]), [])
        self.assertEqual(self.read({**self.source, "catalogRevision": "other"}), [])
        self.summon.effect_stats[2] = 4
        self.assertEqual(self.read(), [])
        self.summon.effect_stats[2] = 6
        self.summon.position = (2, 0, 0)
        self.assertEqual(self.read(), [])
        self.summon.position = (1, 0, 0)
        self.summon.native_summon_action_book["actions"][0]["level"] = 19
        self.assertEqual(self.read(), [])

    def test_rejects_grants_morph_and_non_deterministic_damage(self):
        self.spells[0]["rows"][0]["probability"] = 10
        self.remember()
        self.assertEqual(self.read(), [])
        self.spells[0]["rows"][0]["probability"] = 100
        self.remember()
        self.assertTrue(self.read())
        self.fight.native_spell_grants = {9: {100: {}}}
        self.assertEqual(self.read(), [])
        self.fight.native_spell_grants = {}
        self.fight.native_morph_spellbooks = {9: {"book_uid": 1}}
        self.assertEqual(self.read(), [])

    def test_does_not_use_cache_when_busy_or_control_changes(self):
        self.remember()
        with subject._LOCK:
            self.assertEqual(self.read(), [])
        self.summon.native_controller_id = 8
        self.assertEqual(self.read(), [])

    def test_estimate_budget_expiry_returns_no_partial_book(self):
        self.remember()
        with patch.object(subject, "monotonic", side_effect=[0.0, 0.002]):
            self.assertEqual(self.read(), [])

    def test_extra_owned_action_metadata_invalidates_estimate(self):
        self.remember()
        self.assertTrue(self.read())
        self.summon.native_summon_action_book["actions"][0]["unexpected"] = True
        self.assertEqual(self.read(), [])

    def test_expired_refresh_preserves_a_still_valid_previous_book(self):
        self.remember()
        with patch.object(subject, "monotonic", side_effect=[0.0, 0.002]):
            self.remember()
        self.assertEqual(self.read()[0]["spells"][0]["damage"], 12)

    def test_refresh_expiring_on_last_row_does_not_revoke_previous_book(self):
        self.remember()
        self.spells[0]["unknownProjection"] = ["unknown"]
        with patch.object(
            subject, "monotonic", side_effect=[0.0, 0.0001, 0.0002, 0.002]
        ):
            self.remember()
        self.assertEqual(self.read()[0]["spells"][0]["damage"], 12)

    def test_remember_and_consume_never_load_catalog(self):
        with patch(
            "wakfu_server.native_catalog.load",
            side_effect=AssertionError("catalog I/O"),
        ), patch(
            "wakfu_server.native_catalog._database",
            side_effect=AssertionError("database I/O"),
        ):
            self.remember()
            self.assertTrue(self.read())
            self.assertEqual(
                self.read({**self.source, "fightInstanceId": "another"}), []
            )

    def test_casting_must_have_invariant_costs_and_range(self):
        table = dict(conditional=[], categories=[], range_modifiable=False)
        rule = dict(
            costs=dict(ap=1, mp=0, wp=0, conditional_rules=0), minimum=1, maximum=1
        )
        self.assertTrue(invariant_summon_casting(table, rule, [1, 0, 0], [1, 1]))
        free_rule = dict(
            costs=dict(ap=0, mp=0, wp=0, conditional_rules=0), minimum=2, maximum=16
        )
        self.assertTrue(invariant_summon_casting(table, free_rule, [0, 0, 0], [2, 16]))
        self.assertFalse(
            invariant_summon_casting(
                {**table, "conditional": [{}]}, rule, [1, 0, 0], [1, 1]
            )
        )
        self.assertFalse(
            invariant_summon_casting(
                {**table, "range_modifiable": True}, rule, [1, 0, 0], [1, 1]
            )
        )
        self.assertFalse(
            invariant_summon_casting(table, {**rule, "maximum": 2}, [1, 0, 0], [1, 1])
        )

    def test_profile_5522_free_7969_is_estimated_once_and_negative_cost_is_excluded(
        self,
    ):
        self.summon.native_summon_source.update(ref=5522)
        self.summon.native_summon_action_book.update(
            profile=5522, actions=[dict(uid=7969, reference=7969, level=1)]
        )
        free = dict(
            id=7969,
            grade=1,
            cost=0,
            minRange=2,
            maxRange=16,
            nativeCosts=dict(ap=0, mp=0, wp=0),
            unknownProjection=[],
            rows=[
                dict(
                    kind="damage",
                    target="enemy",
                    amount=25,
                    conditional=False,
                    probability=100,
                    element="fire",
                    nativeCoefficientMask=3,
                    nativeDamageFlags=[],
                    nativeLocalization=False,
                    nativeBase=dict(kind=0, sourceBindingKnown=True),
                )
            ],
        )
        self.spells = [free]
        subject.remember(
            self.oracle,
            self.fight,
            self.summon,
            self.source,
            {7969: 1},
            self.spells,
            {(7969, 1)},
        )
        estimated = self.read()
        self.assertEqual(len(estimated), 1)
        self.assertEqual(len(estimated[0]["spells"]), 1)
        self.assertEqual(estimated[0]["spells"][0]["id"], 7969)
        self.assertEqual(estimated[0]["spells"][0]["cost"], 0)
        self.assertEqual(estimated[0]["spells"][0]["damage"], 25)

        self.spells[0]["cost"] = -1
        subject.remember(
            self.oracle,
            self.fight,
            self.summon,
            self.source,
            {7969: 1},
            self.spells,
            {(7969, 1)},
        )
        self.assertEqual(self.read(), [])

    def test_transferred_controller_and_revoked_projection_are_not_reused(self):
        self.fight.native_controller_registry = {}
        self.summon.native_controlled_by_ai = True
        with patch(
            "wakfu_server.combat_controller_registry.current_native_controller",
            return_value=7,
        ) as controller:
            self.remember()
            self.assertTrue(self.read())
            controller.return_value = 8
            self.assertEqual(self.read(), [])
            controller.return_value = 7
            self.spells[0]["unknownProjection"] = ["new uncertainty"]
            self.remember()
            self.assertEqual(self.read(), [])

    def test_direct_npc_controller_requires_actual_qi_and_current_owner(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_controller_registry import (
            initialize_controller_registry,
            register_native_controller,
            transfer_native_controller,
        )
        from wakfu_server.combat_pointer_qi_actor import ActualActorQI
        from wakfu_server.combat_pointer_qi_actor import ActorQK
        from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint

        def scene(*, player=False):
            owner = Actor(
                11, 0, (0, 0, 0), 100, 6, 3, 20, 20, native_controlled_by_ai=True
            )
            summon = Actor(
                12,
                0,
                (1, 0, 0),
                100,
                6,
                3,
                10,
                20,
                owner_id=owner.id if player else None,
                controlled=player,
                native_controlled_by_ai=False,
            )
            alternate = Actor(
                13, 0, (2, 0, 0), 100, 6, 3, 5, 20, native_controlled_by_ai=True
            )
            enemy = Actor(14, 1, (3, 0, 0), 100, 6, 3, 1, 20)
            walkable = {
                owner.position,
                summon.position,
                alternate.position,
                enemy.position,
            }
            fight = Fight(
                901,
                (owner, summon, alternate, enemy),
                walkable,
                {
                    0: {owner.position, summon.position, alternate.position},
                    1: {enemy.position},
                },
            )
            actors = (owner, summon, alternate, enemy)
            qi = ActualActorQI.__new__(ActualActorQI)
            qi.width, qi.height = 4, 1
            qi.origin = (0, 0)
            qi.fight = fight
            qi.objects = {actor.id: ActorQK(actor) for actor in actors}
            qi.area_objects = {}
            qi.pending_constructor_actors = {}
            qi.slots = [None] * 127
            qi.anchors = {}
            qi.cells = {}
            qi.movement_blocking = {}
            for slot, actor in enumerate(actors):
                actor.native_obstacle_id = slot
                actor.physical_radius = 0
                obj = qi.objects[actor.id]
                obj.byte = slot
                qi.slots[slot] = obj
                qi.anchors[slot] = actor.position[:2]
                qi.movement_blocking[id(obj)] = True
            checkpoint = NativePointerCheckpoint.__new__(NativePointerCheckpoint)
            dict.__init__(checkpoint)
            checkpoint._qi = qi
            checkpoint._lineage = object()
            fight.native_pointer_checkpoint = checkpoint
            fight.native_qi_slots = [None] * 127
            for slot, actor in enumerate(actors):
                fight.native_qi_slots[slot] = {
                    "identity": ["actor", actor.id],
                    "position": list(actor.position[:2]),
                    "radius": actor.physical_radius,
                    "indexed": True,
                    "movement_blocking": True,
                }
            initialize_controller_registry(fight)
            register_native_controller(
                fight, summon.id, team=summon.team, controller_id=owner.id
            )
            source = dict(
                ref=1236,
                level=20,
                caster_id=owner.id,
                controller_id=owner.id,
                native_relation_source="big.new_bje.fdt_initial_registration",
                native_symbiot_source="eZl.new_eHD.pRO_false",
            )
            registration = dict(
                actor_id=summon.id,
                caster_id=owner.id,
                controller_id=owner.id,
                authority=dict(
                    is_summon=True,
                    native_actor_type=1,
                    breed_id=1236,
                    native_real_level=20,
                ),
            )
            return fight, owner, summon, alternate, registration, source

        fight, owner, summon, alternate, registration, source = scene()
        npc_positive = subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene(player=True)
        player_rejected = not subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene()
        summon.native_obstacle_id = (
            126  # The actual QI checkpoint has no QK at this slot.
        )
        stale_slot_rejected = not subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene()
        register_native_controller(
            fight, alternate.id, team=alternate.team, controller_id=alternate.id
        )
        transfer_native_controller(fight, summon.id, alternate.id)
        changed_owner_rejected = not subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene()
        del fight.native_pointer_checkpoint
        legacy_qi_positive = subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene()
        del fight.native_pointer_checkpoint
        slot = summon.native_obstacle_id
        fight.native_qi_slots[slot]["indexed"] = False
        legacy_slot_invalid_rejected = not subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene()
        del fight.native_pointer_checkpoint
        fight.native_qi_slots[summon.native_obstacle_id]["movement_blocking"] = 1
        legacy_bool_shape_rejected = not subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene()
        del fight.native_pointer_checkpoint
        fight.native_qi_slots[summon.native_obstacle_id]["unexpected"] = False
        legacy_extra_slot_field_rejected = not subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene()
        del fight.native_pointer_checkpoint
        summon.native_obstacle_id = 127
        legacy_slot_missing_rejected = not subject._direct_npc_controller(
            fight, summon, registration, source
        )

        fight, owner, summon, alternate, registration, source = scene()
        del fight.native_pointer_checkpoint
        register_native_controller(
            fight, alternate.id, team=alternate.team, controller_id=alternate.id
        )
        transfer_native_controller(fight, summon.id, alternate.id)
        legacy_changed_owner_rejected = not subject._direct_npc_controller(
            fight, summon, registration, source
        )
        self.assertEqual(
            (
                npc_positive,
                player_rejected,
                stale_slot_rejected,
                changed_owner_rejected,
            ),
            (True, True, True, True),
        )
        self.assertEqual(
            (
                legacy_qi_positive,
                legacy_slot_invalid_rejected,
                legacy_bool_shape_rejected,
                legacy_extra_slot_field_rejected,
                legacy_slot_missing_rejected,
                legacy_changed_owner_rejected,
            ),
            (True, True, True, True, True, True),
        )


if __name__ == "__main__":
    unittest.main()
