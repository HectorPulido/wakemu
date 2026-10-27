"""Ready/leader and real dispatcher observer components, not native victory.

Admission and carrier application are isolated in the selection test. Native
9145/933, damage/death and411015 execution have separate native qualification.
"""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_effect_dispatch import (
    EffectDispatcher,
    EffectInvocation,
    run_effect_transaction,
)
from wakfu_server.combat_encounter_objective_spirit import (
    apply_spirit_start,
    deliver_spirit_early_defeat,
    freeze_spirit_participants,
    spirit_result_player,
)


def actor(identity, owner, *, controlled=True, hp=100, uid=None):
    return SimpleNamespace(
        id=identity,
        owner_id=owner,
        controlled=controlled,
        hp=hp,
        pve_withdrawn=False,
        position=(identity, 0, 0),
        state_ledger=SimpleNamespace(
            entries=[]
            if uid is None
            else [
                SimpleNamespace(
                    uid=uid,
                    reference=9145,
                    caster_id=identity,
                    target_id=identity,
                )
            ]
        ),
    )


def scene_fixture(*, granted=False):
    actors = {
        7: actor(7, 3, uid=107 if granted else None),
        8: actor(8, 4, uid=108 if granted else None),
        -200: actor(-200, None, controlled=False),
        -201: actor(-201, None, controlled=False),
    }
    fight = SimpleNamespace(
        id=71,
        phase="active",
        turn_id=1,
        actors=actors,
        order=[7, -200, 8, -201],
        _in_play=lambda value: value.hp > 0 and not value.pve_withdrawn,
    )
    receipt = dict(
        source=dict(
            participant_id=7,
            player_ids=[7],
            original_actor_id=-200,
            admission_digest="a" * 64,
            helper_manifest_digest="b" * 64,
        ),
        status="granted" if granted else "admitted",
        carrier_uids={"7": 107, "8": 108} if granted else {},
    )
    if granted:
        receipt["ready_participants"] = dict(
            source=dict(
                fight_id=71,
                admission_digest="a" * 64,
                players=[
                    dict(actor_id=7, account_id=3),
                    dict(actor_id=8, account_id=4),
                ],
            ),
            source_digest="c" * 64,
        )
    return fight, receipt


def definition():
    return dict(
        effect_class=400,
        parameters=[],
        parameter_count=0,
        probability_base=100,
        probability_per_level=0,
        minimum_level=1,
        maximum_level=200,
        criteria="",
        children=[],
    )


def dispatcher(handler):
    return EffectDispatcher(
        {str(identity): definition() for identity in (90, 91, 92)},
        {400: handler},
        resolve=lambda effect, invocation: (invocation,),
        condition_context=lambda invocation: ConditionContext({}),
        probability_accepts=lambda *args: True,
        group_cells=lambda *args: (),
        actor_position=lambda identity: (identity, 0, 0),
    )


class SpiritReadyAndLeadershipTests(unittest.TestCase):
    def test_ready_includes_legitimate_later_hero_and_excludes_native_dependant(self):
        fight, receipt = scene_fixture()
        fight.actors[901] = actor(901, 3)
        sources = {
            identity: dict(id=identity, account_id=owner)
            for identity, owner in ((7, 3), (8, 4), (901, 3))
        }
        original = deepcopy(receipt["source"])
        with patch(
            "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
            return_value=receipt,
        ), patch(
            "wakfu_server.combat_companions.registered_companion_ids",
            return_value={901},
        ), patch(
            "wakfu_server.combat_terminal_metadata.registered_summon_actor_ids",
            return_value=set(),
        ):
            ready = freeze_spirit_participants(fight, sources)
        self.assertEqual(
            [row["actor_id"] for row in ready["source"]["players"]], [7, 8]
        )
        self.assertEqual(fight.native_spirit_scene_admission["source"], original)

    def test_ready_rejects_missing_or_foreign_hero_source_before_any_grant(self):
        for source in (
            {7: dict(id=7, account_id=3)},
            {7: dict(id=7, account_id=3), 8: dict(id=8, account_id=99)},
        ):
            fight, receipt = scene_fixture()
            with patch(
                "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
                return_value=receipt,
            ), patch(
                "wakfu_server.combat_companions.registered_companion_ids",
                return_value=set(),
            ), patch(
                "wakfu_server.combat_terminal_metadata.registered_summon_actor_ids",
                return_value=set(),
            ):
                with self.assertRaisesRegex(ValueError, "actual owned human"):
                    freeze_spirit_participants(fight, source)
            self.assertFalse(hasattr(fight, "native_spirit_scene_admission"))
            self.assertTrue(
                all(not a.state_ledger.entries for a in fight.actors.values())
            )

    def test_grant_selection_uses_complete_ready_roster_not_initial_principal_only(
        self,
    ):
        fight, receipt = scene_fixture(granted=True)
        receipt["status"], receipt["carrier_uids"] = "admitted", {}
        for value in fight.actors.values():
            value.state_ledger.entries = []
        seen = []

        def apply(handler, invocation, reference, level, **kwargs):
            seen.append((invocation.caster_id, invocation.target_id, reference))
            identity = invocation.target_id
            fight.actors[identity].state_ledger.entries.append(
                SimpleNamespace(
                    uid=1000 + identity,
                    reference=reference,
                    caster_id=identity,
                    target_id=identity,
                )
            )
            return True

        handler = SimpleNamespace(fight=fight, catalog={})
        retention = SimpleNamespace(fight=fight, apply_state_reference=apply)
        runtime = SimpleNamespace(
            native_retention=retention, native_state_handler=handler
        )
        with patch(
            "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
            return_value=receipt,
        ), patch("wakfu_server.combat_encounter_actor_contract.bind_actor_role"), patch(
            "wakfu_server.combat_encounter_actor_contract.validate_actor_bindings"
        ), patch(
            "wakfu_server.combat_encounter_scene_helpers.bind_scene_helper_controls"
        ), patch(
            "wakfu_server.combat_definitions.state_profile",
            return_value=dict(
                effects=[410217, 410946], duration=-1, realtime_duration=0
            ),
        ):
            self.assertTrue(apply_spirit_start(fight, lambda *args: (runtime, []), []))
        self.assertEqual(seen, [(7, 7, 9145), (8, 8, 9145)])
        self.assertEqual(
            set(fight.native_spirit_scene_admission["carrier_uids"]), {"7", "8"}
        )

    def test_departed_principal_handoff_is_journaled_once_without_admission_rewrite(
        self,
    ):
        fight, receipt = scene_fixture(granted=True)
        before = deepcopy(receipt)
        with patch(
            "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
            return_value=receipt,
        ):
            self.assertIs(spirit_result_player(fight), fight.actors[7])
            fight.actors[7].pve_withdrawn = True
            self.assertIs(spirit_result_player(fight), fight.actors[8])
            self.assertIs(spirit_result_player(fight), fight.actors[8])
        self.assertEqual(receipt, before)
        self.assertEqual(len(fight.native_spirit_result_leadership["handoffs"]), 1)
        self.assertEqual(
            fight.native_spirit_result_leadership["handoffs"][0]["from_actor_id"], 7
        )

    def test_foreign_owner_or_replaced_carrier_cannot_inherit_result(self):
        for mutation in ("owner", "carrier"):
            fight, receipt = scene_fixture(granted=True)
            fight.actors[7].pve_withdrawn = True
            if mutation == "owner":
                fight.actors[8].owner_id = 99
            else:
                fight.actors[8].state_ledger.entries[0].uid = 999
            with patch(
                "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
                return_value=receipt,
            ):
                self.assertIsNone(spirit_result_player(fight))
            self.assertFalse(hasattr(fight, "native_spirit_result_leadership"))


class SpiritPostRootObserverTests(unittest.TestCase):
    def test_native_activation_ancestry_reset_does_not_publish_nested_observer(self):
        events, native = [], None

        def handler(effect, values, invocation):
            events.append(invocation.reference)
            if invocation.reference == 90:
                native.execute_activation(
                    EffectInvocation(91, 1, 7, 7, (0, 0, 0)),
                    source=None,
                    condition_context=lambda *args: ConditionContext({}),
                    executable=True,
                    allocate_uid=lambda: 700,
                )
            return True

        native = dispatcher(handler)
        native.native_scene_root_observer = lambda: (events.append("observer") or False)
        self.assertTrue(native.execute(EffectInvocation(90, 1, 7, 7, (0, 0, 0))))
        self.assertEqual(events, [90, 91, "observer"])

    def test_optional_observer_runs_once_after_children_and_not_on_nested_observer_execution(
        self,
    ):
        events, native = [], None

        def handler(effect, values, invocation):
            events.append(invocation.reference)
            if invocation.reference == 90:
                native.execute(EffectInvocation(91, 1, 7, 7, (0, 0, 0)))
            return True

        native = dispatcher(handler)

        def observe():
            events.append("observer")
            native.execute(EffectInvocation(92, 1, 7, 7, (0, 0, 0)))
            return False

        native.native_scene_root_observer = observe
        self.assertTrue(native.execute(EffectInvocation(90, 1, 7, 7, (0, 0, 0))))
        self.assertEqual(events, [90, 91, "observer", 92])

    def test_observer_failure_discards_private_transaction(self):
        class Domain:
            def __init__(self):
                self.events = []

            @contextmanager
            def effect_resolution(self):
                yield

        source = Domain()

        def factory(preview):
            native = dispatcher(lambda *args: (preview.events.append("effect") or True))

            def observe():
                preview.events.append("observer")
                raise ValueError("qualified scene failure rejected")

            native.native_scene_root_observer = observe
            return native

        with self.assertRaisesRegex(ValueError, "scene failure rejected"):
            run_effect_transaction(
                source, (EffectInvocation(90, 1, 7, 7, (0, 0, 0)),), factory
            )
        self.assertEqual(source.events, [])

    def test_unadmitted_fight_keeps_unrelated_positive_hp_floor_helper_untouched(self):
        helper = SimpleNamespace(hp=1, effect_minima={1: 1})
        fight = SimpleNamespace(phase="active", actors={-200: helper})
        native = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        with patch(
            "wakfu_server.combat_encounter_objective_spirit.spirit_admission",
            side_effect=AssertionError("unadmitted fight consulted scene authority"),
        ):
            self.assertFalse(deliver_spirit_early_defeat(native))
        self.assertEqual((helper.hp, helper.effect_minima), (1, {1: 1}))
