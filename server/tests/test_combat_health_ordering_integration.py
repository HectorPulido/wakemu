"""Qualified flag8 metadata and actual HP constructor operands are both required."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_target_ordering import order_native_targets
from wakfu_server.combat_target_health_ordering import health_operand_for_pv
from wakfu_server.combat_hp_raw import SOURCE, install_fresh_hp_operand


class HealthOrderingIntegrationTests(unittest.TestCase):
    def actor(self, identity, hp, maximum):
        actor = SimpleNamespace(
            id=identity,
            hp=hp,
            position=(identity, 0, 0),
            effect_stats={1: hp},
            effect_maxima={1: maximum},
            effect_minima={1: 0},
            effect_frozen=frozenset(),
        )
        install_fresh_hp_operand(
            actor, dict(producer=SOURCE, actor_id=identity, raw_current=hp)
        )
        return actor

    def test_actual_constructor_operand_orders_effective_health_before_cap(self):
        actors = (
            self.actor(1, 50, 100),
            self.actor(2, 10, 100),
            self.actor(3, 20, 200),
        )
        fight = SimpleNamespace(actors={a.id: a for a in actors})
        effect = dict(effect_class=330, native_effect_flags=[8, 26])
        invocation = SimpleNamespace(reference=123, cell=(0, 0, 0))
        metadata = {
            "123": dict(
                effect,
                maximum_targets=2,
                ordering_contract="faI.PV.a.sgC.PA.aYS.aYU.float32.asc.v1",
            )
        }
        result = order_native_targets(
            effect,
            invocation,
            actors,
            metadata=metadata,
            health_operand=lambda a: health_operand_for_pv(fight, a),
        )
        self.assertEqual([a.id for a in result], [2, 3])

    def test_legacy_metadata_cannot_enable_health_ordering(self):
        effect = dict(effect_class=330, native_effect_flags=[8, 26])
        invocation = SimpleNamespace(reference=123, cell=(0, 0, 0))
        with self.assertRaisesRegex(ValueError, "health-percent"):
            order_native_targets(
                effect,
                invocation,
                (),
                metadata={"123": dict(effect, maximum_targets=2)},
            )

    def test_scalar_hp_and_container_without_native_source_do_not_prove_presence(self):
        actor = SimpleNamespace(
            id=1, hp=10, effect_stats={1: 10}, effect_maxima={1: 20}
        )
        with self.assertRaisesRegex(ValueError, "constructor/copy authority"):
            health_operand_for_pv(SimpleNamespace(actors={1: actor}), actor)

    def test_alias_and_raw_effective_mismatch_stay_rejected(self):
        actor = self.actor(1, 10, 20)
        fight = SimpleNamespace(actors={1: actor})
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            health_operand_for_pv(fight, SimpleNamespace(id=1, hp=10))
        actor.hp = 11
        with self.assertRaisesRegex(ValueError, "raw/effective"):
            health_operand_for_pv(fight, actor)
