"""Native eXO KO admission is independent of flag15, with strict lifecycle proof."""
from copy import deepcopy
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

from wakfu_server.combat_resurrection import prepare_resurrection
from wakfu_server.combat_stat_handler import StatExecutionContext


class NativeRestoreKOAuthorityTests(unittest.TestCase):
    def fixture(self):
        actor = N(id=7, hp=0, native_obstacle_id=0, position=(1, 2, 0))
        fight = N(
            native_global_pv_collections={},
            order=[-1],
            native_timeline_removed=[dict(actor_id=7, position=1, modifications=[])],
        )
        registry = N(slots=[dict(identity=["actor", 7], position=[1, 2])])
        return fight, actor, registry

    def prepare(
        self,
        fight,
        actor,
        registry,
        flags,
        *,
        context=None,
        status="OFF_PLAY",
        effect_class=196,
        registered=True
    ):
        guards = dict(
            baF=status == "IN_PLAY",
            baG=status == "OFF_PLAY",
            baK=status == "OUT_OF_PLAY",
        )
        with patch(
            "wakfu_server.combat_global_pv_collections.global_fighter_guards",
            return_value=guards,
        ), patch(
            "wakfu_server.combat_ordinary_death.registered_ordinary_death",
            return_value=registered,
        ), patch(
            "wakfu_server.combat_qi_fight.current_registry", return_value=registry
        ):
            return prepare_resurrection(
                fight,
                actor,
                dict(effect_class=effect_class, native_effect_flags=flags),
                execution_context=context,
            )

    def test_authorized_196_accepts_flags17_empty_or15_with_same_lifecycle(self):
        fight, actor, registry = self.fixture()
        context = StatExecutionContext(True, True, None, False, None)
        for flags in ([17], [], [15]):
            with self.subTest(flags=flags):
                self.assertEqual(
                    self.prepare(fight, actor, registry, flags, context=context),
                    dict(slot=0, removed=fight.native_timeline_removed[0]),
                )

    def test_missing_bcd_execution_authority_and_other_family_reject_before_mutation(
        self,
    ):
        fight, actor, registry = self.fixture()
        before = deepcopy(vars(fight))
        for context, family in (
            (None, 196),
            (StatExecutionContext(False, True, None, False, None), 196),
            (StatExecutionContext(True, False, None, False, None), 196),
            (StatExecutionContext(True, True, None, False, None), 2),
        ):
            with self.subTest(context=context, family=family):
                with self.assertRaisesRegex(ValueError, "authorized native eXO"):
                    self.prepare(
                        fight,
                        actor,
                        registry,
                        [15],
                        context=context,
                        effect_class=family,
                    )
                self.assertEqual(vars(fight), before)

    def test_partial_arithmetic_definition_does_not_project_corpse_population(self):
        fight, actor, registry = self.fixture()
        before = deepcopy(vars(fight))
        self.assertIsNone(prepare_resurrection(fight, actor, {"effect_class": 196}))
        self.assertEqual(vars(fight), before)
        with self.assertRaisesRegex(ValueError, "native eXO effect flags"):
            prepare_resurrection(
                fight, actor, {"effect_class": 196, "native_effect_flags": [True]}
            )

    def test_inplay_healing_outplay_and_absent_manager_never_resurrect(self):
        fight, actor, registry = self.fixture()
        for status in ("IN_PLAY", "OUT_OF_PLAY"):
            self.assertIsNone(self.prepare(fight, actor, registry, [], status=status))
        del fight.native_global_pv_collections
        self.assertIsNone(self.prepare(fight, actor, registry, []))

    def test_fake_corpse_or_lost_qi_reject_without_changing_checkpoint(self):
        fight, actor, registry = self.fixture()
        context = StatExecutionContext(True, True, None, False, None)
        before = deepcopy(vars(fight))
        with self.assertRaisesRegex(ValueError, "owned OFF_PLAY corpse"):
            self.prepare(
                fight, actor, registry, [17], context=context, registered=False
            )
        registry.slots[0]["identity"] = ["actor", 999]
        with self.assertRaisesRegex(ValueError, "QI slot"):
            self.prepare(fight, actor, registry, [17], context=context)
        self.assertEqual(vars(fight), before)
        self.assertEqual(actor.hp, 0)


if __name__ == "__main__":
    unittest.main()
