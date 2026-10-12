"""Native previews cannot reveal unseen opponents through public metrics."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from test_native_session import NativeSession, StubOracle, StubTransport, make_runtime
from wakfu_ai.planning.query_search import _metrics
from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS


class InvisibleObservationTests(unittest.TestCase):
    def session(self, properties, *, allied=False):
        runtime = make_runtime()
        target = runtime.fight.actors[-23]
        target.native_fight_properties = frozenset(properties)
        if allied:
            target.team = runtime.fight.current.team
        session = NativeSession(
            StubOracle(runtime),
            StubTransport(),
            object(),
            policy={},
            policy_version="visibility-test",
            fight_instance_id="test",
        )
        return session, runtime

    def test_hidden_enemy_retains_native_authority_but_no_public_position_or_score(
        self,
    ):
        for properties in ({5}, {18}):
            with self.subTest(properties=properties):
                session, runtime = self.session(properties)
                before = session.describe(session.root)
                self.assertEqual([row["id"] for row in before["actors"]], [101])
                self.assertEqual(before["nativeFacings"], {})
                self.assertIn(-23, session.states[session.root].fight.actors)
                private = deepcopy(runtime)
                private.fight.actors[-23].hp = 0
                private.fight.actors[-23].position = (1, 0, 0)
                # Even a hypothetical reveal must not let the search select
                # its guessed cell by observing private preview consequences.
                private.fight.actors[-23].native_fight_properties = frozenset()
                after = session.describe(session.register(private))
                self.assertEqual(before["actors"], after["actors"])
                self.assertEqual(
                    before["topologyDistances"], after["topologyDistances"]
                )
                self.assertEqual(after["nativeFacings"], {})
                score, _, intent, target = evaluate(
                    _metrics(before, 101),
                    _metrics(after, 101),
                    101,
                    DEFAULT_WEIGHTS,
                    {},
                )
                self.assertEqual(score, 0)
                self.assertIsNone(target)
                self.assertNotIn(intent, ("damage", "finish"))

    def test_allied_invisibility_is_known_but_los_property_is_not_stealth(self):
        for properties, allied in (({5}, True), ({54}, False), (set(), False)):
            with self.subTest(properties=properties, allied=allied):
                session, _ = self.session(properties, allied=allied)
                self.assertEqual(len(session.describe(session.root)["actors"]), 2)

    def test_real_reveal_is_observed_by_fresh_decision(self):
        hidden, runtime = self.session({5})
        runtime.fight.actors[-23].native_fight_properties = frozenset()
        fresh = NativeSession(
            StubOracle(runtime),
            StubTransport(),
            object(),
            policy={},
            policy_version="visibility-test",
            fight_instance_id="test",
        )
        self.assertEqual(len(fresh.describe(fresh.root)["actors"]), 2)

    def test_query_preview_drops_hidden_damage_localization_and_failed_capture(self):
        session, _ = self.session({5})

        def preview_with_evidence(runtime, action):
            private, packets, transaction = session.oracle.preview(runtime, action)
            return private, packets, transaction, []

        session.oracle.preview_with_evidence = preview_with_evidence
        rows = [
            dict(casterId=101, targetId=-23, observedLocalization="BACK"),
            dict(casterId=-23, targetId=101, observedLocalization="FRONT"),
            dict(casterId=101, targetId=101, observedLocalization="SIDE"),
            dict(observationUnavailable=True, detail="private target position"),
        ]
        with patch(
            "wakfu_ai.native.native_damage_observer.evidence", return_value=rows
        ):
            response = session.query(
                dict(
                    id="hidden-evidence",
                    operation="preview",
                    state=session.root,
                    action=dict(type="move", path=[[1, 0, 0]]),
                )
            )
        self.assertTrue(response["supported"])
        self.assertEqual(response["result"]["damageContextEvidence"], [rows[2]])

    def test_canonical_visibility_requires_complete_properties(self):
        runtime = make_runtime()
        runtime.fight.native_global_pv_collections = {}
        with self.assertRaisesRegex(ValueError, "AI visibility properties"):
            NativeSession(
                StubOracle(runtime),
                StubTransport(),
                object(),
                policy={},
                policy_version="visibility-test",
                fight_instance_id="test",
            )

    def test_dead_withdrawn_actor_keeps_roster_without_live_visibility_authority(self):
        runtime = make_runtime()
        runtime.fight.native_global_pv_collections = {}
        runtime.fight.current.native_fight_properties = frozenset()
        corpse = runtime.fight.actors[-23]
        corpse.hp = 0
        corpse.pve_withdrawn = True
        session = NativeSession(
            StubOracle(runtime),
            StubTransport(),
            object(),
            policy={},
            policy_version="visibility-test",
            fight_instance_id="test",
        )
        rows = {row["id"]: row for row in session.describe(session.root)["actors"]}
        self.assertEqual(rows[corpse.id]["hp"], 0)
        self.assertIn(corpse.id, session.states[session.root].fight.actors)

    def test_hidden_opponent_cannot_be_queried_as_rival(self):
        session, _ = self.session({18})
        response = session.query(
            dict(
                id="hidden-rival",
                operation="project_turn",
                state=session.root,
                actorId=-23,
            )
        )
        self.assertFalse(response["supported"])

    def test_hidden_trap_scope_encloses_all_query_paths_and_restores_after_failure(
        self,
    ):
        from wakfu_server.combat_observation_scope import area_is_unobserved

        session, _ = self.session(set())
        session.unobserved_area_ids = frozenset({901})
        for operation in ("preview", "project_turn", "state", "repertoire"):
            with self.subTest(operation=operation):

                def inspect(*args):
                    self.assertTrue(area_is_unobserved(901))
                    raise ValueError("Projection failed")

                with patch.object(session, "_query_unmeasured", side_effect=inspect):
                    with self.assertRaisesRegex(ValueError, "Projection failed"):
                        session._query(operation, session.root, {})
                self.assertFalse(area_is_unobserved(901))

    def test_movement_query_hidden_trap_matches_no_trap_but_real_preview_triggers(self):
        from test_combat_effect_area_events import AreaEventTests

        class TrapOracle(StubOracle):
            def unobserved_areas(self, runtime):
                return (
                    frozenset(runtime.fight.native_effect_areas)
                    if hidden
                    else frozenset()
                )

            def preview(self, runtime, action):
                private, packets, transaction = super().preview(runtime, action)
                for row in private.fight.native_effect_areas.values():
                    events, _, _ = AreaEventTests().fixture("TRAP", entry=(10001,))
                    events.fight = private.fight
                    events.dispatcher.execute = lambda invocation: setattr(
                        private.fight.current, "hp", private.fight.current.hp - 7
                    )
                    with patch(
                        "wakfu_server.combat_trap_area.verified_trap_characteristics"
                    ), patch("wakfu_server.combat_trap_area.retire_exhausted_trap"):
                        events._activate(
                            row, events.definitions["1474"], private.fight.current
                        )
                return private, packets, transaction

        observed = []
        for trap, hidden in ((False, False), (True, True), (True, False)):
            runtime = make_runtime()
            _, row, _ = AreaEventTests().fixture("TRAP", entry=(10001,))
            row.update(
                native_area_contract="fbc", remaining_activations=1, owner_id=-23
            )
            runtime.fight.native_retained_records = {}
            runtime.fight.native_effect_areas = {901: row} if trap else {}
            oracle = TrapOracle(runtime)
            session = NativeSession(
                oracle,
                StubTransport(),
                object(),
                policy={},
                policy_version="visibility-test",
                fight_instance_id="movement-trap",
            )
            action = {"type": "move", "path": [[1, 0, 0]]}
            response = session.query(
                dict(
                    id="movement",
                    operation="preview",
                    state=session.root,
                    action=action,
                )
            )
            self.assertTrue(response["supported"], response)
            observed.append(_metrics(response["result"], 101))
            if trap and hidden:
                forecast = session.states[response["result"]["key"]]
                self.assertEqual(
                    forecast.fight.native_effect_areas[901]["remaining_activations"], 1
                )
                actual, _, _ = oracle.preview(runtime, action)
                self.assertEqual(actual.fight.current.hp, runtime.fight.current.hp - 7)
                self.assertEqual(
                    actual.fight.native_effect_areas[901]["remaining_activations"], 0
                )
                self.assertEqual(
                    runtime.fight.native_effect_areas[901]["remaining_activations"], 1
                )
        self.assertEqual(observed[0], observed[1])
        self.assertNotEqual(observed[0], observed[2])

    def test_only_hidden_hostile_traps_are_unobserved(self):
        from types import SimpleNamespace
        from wakfu_ai.native.native_oracle import NativeOracle
        from test_combat_trap_area import NativeTrapAreaTests

        runtime = make_runtime()
        for parameters, allied, expected in (
            ((1, 0), False, {901}),
            ((1, 0), True, set()),
            ((0, 1), False, set()),
        ):
            with self.subTest(parameters=parameters, allied=allied):
                row, definition = NativeTrapAreaTests().fixture(parameters)
                row.update(uid=901, reference=1474, owner_id=-23)
                runtime.fight.actors[-23].team = (
                    runtime.fight.current.team if allied else -1
                )
                runtime.fight.native_effect_areas = {901: row}
                with patch(
                    "wakfu_server.combat_effect_area.native_effect_areas",
                    return_value={"1474": definition},
                ):
                    actual = NativeOracle.unobserved_areas(SimpleNamespace(), runtime)
                self.assertEqual(actual, frozenset(expected))

    def test_fresh_native_fighters_use_catalog_profiles_and_live_stealth_override(self):
        from test_native_oracle import NativeOracleTests
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.spells import default_deck

        fixture = NativeOracleTests.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        oracle = NativeOracleTests.oracle_for(
            runtime,
            fixture.character,
            fixture.monster,
            default_deck(fixture.character),
        )
        # A missing live override is a valid fresh profile, not absent PB
        # authority. Read its catalog producer rather than invent an empty set.
        fixture.pc.native_fight_properties = None
        fixture.npc.native_fight_properties = None
        properties = oracle.observation_properties(runtime)
        self.assertEqual(set(properties), set(fixture.fight.actors))
        self.assertTrue(
            all(isinstance(value, frozenset) for value in properties.values())
        )
        session = NativeSession(
            oracle,
            StubTransport(),
            object(),
            policy={},
            policy_version="visibility-test",
            fight_instance_id="fresh-native",
        )
        self.assertEqual(session.unobserved_actor_ids, frozenset())
        target = next(
            actor
            for actor in fixture.fight.actors.values()
            if actor.team != fixture.fight.current.team
        )
        target.native_fight_properties = properties[target.id] | {5}
        hidden = NativeSession(
            oracle,
            StubTransport(),
            object(),
            policy={},
            policy_version="visibility-test",
            fight_instance_id="fresh-native",
        )
        self.assertIn(target.id, hidden.unobserved_actor_ids)


if __name__ == "__main__":
    unittest.main()
