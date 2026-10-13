"""Current NPC controller policy preserves raw native flags and human control."""
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest
from wakfu_server.combat_npc_controller_policy import npc_controller_routes_ai


class NpcControllerPolicyTests(unittest.TestCase):
    def fixture(self):
        child = NS(
            id=3,
            hp=100,
            native_obstacle_id=0,
            native_controlled_by_ai=False,
            native_summon_source=dict(
                ref=3251,
                level=98,
                caster_id=-200,
                native_relation_source="big.new_bje.fdt_initial_registration",
            ),
        )
        parent = NS(id=-200, hp=100, controlled=False, native_controlled_by_ai=True)
        player = NS(id=7, hp=100, controlled=True, native_controlled_by_ai=False)
        fight = NS(
            actors={3: child, -200: parent, 7: player},
            native_summon_registrations={
                3: dict(
                    actor_id=3,
                    caster_id=-200,
                    authority=dict(
                        is_summon=True,
                        native_actor_type=1,
                        breed_id=3251,
                        native_real_level=98,
                    ),
                )
            },
        )
        registry = NS(slots=[dict(identity=["actor", 3])])
        return fight, child, parent, registry

    def check(self, fight, child, registry, controllers):
        with patch(
            "wakfu_server.combat_qi_fight.current_registry", return_value=registry
        ), patch(
            "wakfu_server.combat_controller_registry.current_native_controller",
            side_effect=lambda f, i: controllers.get(i),
        ):
            return npc_controller_routes_ai(fight, child)

    def test_actual_npc_controller_routes_without_rewriting_native_flag(self):
        f, c, p, r = self.fixture()
        self.assertTrue(self.check(f, c, r, {3: -200}))
        self.assertIs(c.native_controlled_by_ai, False)

    def test_current_player_controller_overrides_original_npc_source(self):
        f, c, p, r = self.fixture()
        self.assertFalse(self.check(f, c, r, {3: 7}))

    def test_player_created_child_stays_manual(self):
        f, c, p, r = self.fixture()
        c.native_summon_source["caster_id"] = 7
        f.native_summon_registrations[3]["caster_id"] = 7
        self.assertFalse(self.check(f, c, r, {3: 7}))

    def test_dead_or_absent_controller_never_authorizes(self):
        f, c, p, r = self.fixture()
        p.hp = 0
        self.assertFalse(self.check(f, c, r, {3: -200}))
        del f.actors[-200]
        self.assertFalse(self.check(f, c, r, {3: -200}))

    def test_cyclic_current_controller_chain_never_authorizes(self):
        f, c, p, r = self.fixture()
        p.native_controlled_by_ai = False
        p.native_summon_source = {}
        self.assertFalse(self.check(f, c, r, {3: -200, -200: 3}))

    def test_stale_qi_slot_rejected(self):
        f, c, p, r = self.fixture()
        r.slots[0]["identity"] = ["actor", 99]
        with self.assertRaises(ValueError):
            self.check(f, c, r, {3: -200})

    def test_untyped_qi_identity_cannot_authorize_a_native_fighter(self):
        f, c, p, r = self.fixture()
        r.slots[0]["identity"] = 3
        with self.assertRaises(ValueError):
            self.check(f, c, r, {3: -200})
