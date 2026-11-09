"""Focal tests for detached native trap movement observations."""
import random
import sys
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from wakfu_server.combat_observation_scope import area_is_unobserved
import wakfu_server.combat_expiration_provider as combat_expiration_provider
import wakfu_server.combat_retained_gc_authority as combat_retained_gc_authority
from wakfu_server.wakia_bridge.wakfu_ai.bridge import (
    jondo_trap_observation as observation,
)
from wakfu_server.wakia_bridge.wakfu_ai.bridge import world_sources
from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_trap_observation import (
    capture_area_movement,
    compare_area_movement,
)


def actor(identity, hp=100, armor=0, ap=6, mp=3, max_ap=6, max_mp=3):
    return NS(
        id=identity,
        hp=hp,
        effect_stats={97: armor},
        ap=ap,
        mp=mp,
        max_ap=max_ap,
        max_mp=max_mp,
    )


def dispatcher(fight, callback):
    events = NS(fight=fight, movement=callback)
    return NS(native_area_events=events)


class _Provider:
    def __init__(self):
        self.characters = {7: {"id": 7, "account_id": 3}}


class _Oracle:
    def __init__(self, runtime=None, **kwargs):
        self.runtime = runtime
        self.viewer_id = 7
        self.characters = kwargs.get("characters", {7: {"id": 7, "account_id": 3}})
        self.monsters = kwargs.get("monsters", {-7: {"id": -7}})
        self.decks = kwargs.get("decks", {7: b"deck"})
        self.excluded_decks = kwargs.get("excluded_decks", {7: frozenset()})
        self.flags = kwargs.get("flags", {"native_area_callbacks": True})
        self.outcome_features_provider = kwargs.get("outcome_features", None)


_ORACLE_MODULE = "wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle"
_Oracle.__module__ = _ORACLE_MODULE
_Oracle.__name__ = "NativeOracle"
_ORACLE_AUTHORITY = NS(NativeOracle=_Oracle, _GC_ORACLE_TYPE=_Oracle)


def detached_fixture():
    provider = _Provider()
    fight = NS(rift_wave_state=None, actors={7: actor(7)}, walkable={0})
    runtime = NS(
        fight=fight,
        expiration_runtime_factory=provider,
        clock=time.monotonic,
        awaiting_ack=None,
        pending=False,
    )
    return _Oracle(runtime), provider


class TrapObservationTests(unittest.TestCase):
    def setUp(self):
        self.caster = actor(7)
        self.enemy = actor(8)
        self.ally = actor(9, hp=80, armor=4, ap=4, mp=2, max_ap=4, max_mp=2)
        self.enemy.state_ledger = NS(entries=[{"reference": 5, "level": 1}])
        self.fight = NS(
            actors={7: self.caster, 8: self.enemy, 9: self.ally},
            owned_stat_effects={12: {"actorId": 8, "stat": 97, "amount": 4}},
            native_retained_records={20: {"timer": 1}},
            native_owned_area_effects={40: {"stateId": 5}},
        )

    def test_captures_signed_deltas_and_retention_changes_without_claiming_completeness(
        self,
    ):
        def movement(actor_id, *, from_cell, to_cell):
            self.assertEqual((actor_id, from_cell, to_cell), (7, (0, 0, 0), (1, 0, 0)))
            self.caster.hp -= 3
            self.caster.effect_stats[97] += 2
            self.caster.ap -= 2
            self.caster.mp += 1
            self.caster.max_ap -= 1
            self.enemy.hp -= 5
            self.enemy.ap -= 2
            self.ally.hp -= 1
            self.enemy.state_ledger.entries.append({"reference": 6, "level": 1})
            self.fight.owned_stat_effects[12] = {"actorId": 8, "stat": 97, "amount": 6}
            self.fight.owned_stat_effects[13] = {"actorId": 8, "stat": 1, "amount": -2}
            self.fight.native_retained_records[20]["timer"] = 2
            self.fight.native_retained_records[21] = object()
            del self.fight.native_owned_area_effects[40]
            return ((), (True,), ())

        result = capture_area_movement(
            dispatcher(self.fight, movement), 7, (0, 0, 0), (1, 0, 0)
        )
        self.assertFalse(result["complete"])
        self.assertEqual(result["certainty"], "one_native_counterfactual_route")
        self.assertEqual(result["outcome"], ((), (True,), ()))
        self.assertEqual(
            result["deltas"],
            [
                {
                    "actorId": 7,
                    "hp": -3,
                    "armor": 2,
                    "ap": -2,
                    "mp": 1,
                    "maxAp": -1,
                    "maxMp": 0,
                },
                {
                    "actorId": 8,
                    "hp": -5,
                    "armor": 0,
                    "ap": -2,
                    "mp": 0,
                    "maxAp": 0,
                    "maxMp": 0,
                },
                {
                    "actorId": 9,
                    "hp": -1,
                    "armor": 0,
                    "ap": 0,
                    "mp": 0,
                    "maxAp": 0,
                    "maxMp": 0,
                },
            ],
        )
        self.assertEqual(
            result["changedStatEffects"],
            {
                12: {"actorId": 8, "stat": 97, "amount": 6},
                13: {"actorId": 8, "stat": 1, "amount": -2},
            },
        )
        self.assertEqual(result["removedStatEffects"], [])
        self.assertEqual(result["newRetainedIds"], [21])
        self.assertEqual(result["removedRetainedIds"], [])
        self.assertEqual(result["changedRetainedIds"], [20])
        self.assertEqual(result["changedStateActorIds"], [8])
        self.assertEqual(result["removedAreaEffects"], {40: {"stateId": 5}})

    def test_captures_timeline_round_before_and_after_native_callback(self):
        self.fight.native_timeline_round = 4

        def movement(*_args, **_kwargs):
            self.fight.native_timeline_round = 5

        result = capture_area_movement(
            dispatcher(self.fight, movement), 7, (0, 0, 0), (1, 0, 0)
        )
        self.assertEqual(result["timelineRoundBefore"], 4)
        self.assertEqual(result["timelineRoundAfter"], 5)

    def test_rejects_dead_or_unregistered_trigger_and_roster_changes(self):
        with self.assertRaisesRegex(ValueError, "living registered actor"):
            capture_area_movement(
                dispatcher(self.fight, lambda *_a, **_k: None), 99, (0, 0, 0), (1, 0, 0)
            )

        def roster_change(*_args, **_kwargs):
            del self.fight.actors[9]

        with self.assertRaisesRegex(ValueError, "living actor roster"):
            capture_area_movement(
                dispatcher(self.fight, roster_change), 7, (0, 0, 0), (1, 0, 0)
            )

    def test_rejects_unknown_resource_types_before_recording(self):
        self.enemy.ap = True
        with self.assertRaisesRegex(ValueError, "Unknown native resources"):
            capture_area_movement(
                dispatcher(self.fight, lambda *_a, **_k: None), 7, (0, 0, 0), (1, 0, 0)
            )

    def test_bounds_actor_count(self):
        actors = {i: actor(i) for i in range(33)}
        fight = NS(actors=actors, owned_stat_effects={}, native_retained_records={})
        with self.assertRaisesRegex(ValueError, "Too many actors"):
            capture_area_movement(
                dispatcher(fight, lambda *_a, **_k: None), 0, (0, 0, 0), (1, 0, 0)
            )

    def test_comparison_uses_same_rng_and_private_observed_control_branches(self):
        area_id = 1000
        self.fight.native_effect_areas = {area_id: {"uid": area_id}}
        initial = {
            identity: (row.hp, row.ap, row.mp)
            for identity, row in self.fight.actors.items()
        }
        rng = random.Random(71)
        rng_state = rng.getstate()
        factory_rng_states = []

        class Oracle:
            def factory(inner, private, _action_id, random_source):
                factory_rng_states.append(random_source.getstate())

                def movement(actor_id, *, from_cell, to_cell):
                    if not area_is_unobserved(area_id):
                        private.actors[8].hp -= 6
                        private.actors[8].ap -= 1
                        private.native_retained_records[31] = object()
                    return ((), (True,), ())

                return (
                    lambda _fight, _options: (dispatcher(private, movement), None),
                    None,
                )

        result = compare_area_movement(
            Oracle(),
            self.fight,
            area_id,
            7,
            (0, 0, 0),
            (1, 0, 0),
            action_id=20,
            rng_state=rng_state,
        )
        self.assertEqual(factory_rng_states, [rng_state, rng_state])
        self.assertFalse(result["complete"])
        self.assertEqual(result["certainty"], "one_native_counterfactual_route")
        self.assertEqual(
            result["deltas"],
            [
                {
                    "actorId": 8,
                    "hp": -6,
                    "armor": 0,
                    "ap": -1,
                    "mp": 0,
                    "maxAp": 0,
                    "maxMp": 0,
                },
            ],
        )
        self.assertEqual(result["observed"]["newRetainedIds"], [31])
        self.assertEqual(result["control"]["newRetainedIds"], [])
        self.assertEqual(
            {
                identity: (row.hp, row.ap, row.mp)
                for identity, row in self.fight.actors.items()
            },
            initial,
        )

    def test_comparison_rejects_missing_or_expired_area_identity(self):
        self.fight.native_effect_areas = {}

        class Oracle:
            def factory(self, *_args):
                raise AssertionError("must reject identity before building branches")

        with self.assertRaisesRegex(ValueError, "Missing observed native area"):
            compare_area_movement(
                Oracle(),
                self.fight,
                1000,
                7,
                (0, 0, 0),
                (1, 0, 0),
                action_id=1,
                rng_state=None,
            )

    def test_rejects_mismatched_registry_identity(self):
        self.enemy.id = 80
        with self.assertRaisesRegex(ValueError, "Unknown actor identity"):
            capture_area_movement(
                dispatcher(self.fight, lambda *_a, **_k: None), 7, (0, 0, 0), (1, 0, 0)
            )

    def test_detached_oracle_admits_verified_source_and_binds_private_copy(self):
        source, provider = detached_fixture()
        bound = []

        def bind(private, session):
            private.bound_session = session
            bound.append(session)

        with patch.dict(sys.modules, {_ORACLE_MODULE: _ORACLE_AUTHORITY}), patch.object(
            combat_expiration_provider, "OwnedExpirationFactory", _Provider
        ), patch.object(
            combat_retained_gc_authority,
            "capture_native_callbacks",
            return_value=object(),
        ), patch.object(
            world_sources, "bind_private_sources", side_effect=bind
        ):
            detached = observation.detached_oracle(source)

        self.assertIsInstance(detached, _Oracle)
        self.assertIsNot(detached.runtime, source.runtime)
        self.assertIsNot(detached.runtime.fight, source.runtime.fight)
        self.assertIsNot(detached.runtime.expiration_runtime_factory, provider)
        self.assertEqual(detached.runtime.bound_session.character_id, 7)
        self.assertEqual(detached.runtime.bound_session.account_id, 3)
        self.assertEqual(source.runtime.fight.actors[7].hp, 100)
        self.assertEqual(len(bound), 1)

    def test_detached_oracle_rejects_unverified_source_surfaces(self):
        mutations = (
            lambda oracle: setattr(oracle.runtime, "clock", lambda: 1),
            lambda oracle: setattr(
                oracle.runtime.fight, "rift_wave_state", {"wave": 1}
            ),
            lambda oracle: setattr(oracle.runtime, "awaiting_ack", 4),
            lambda oracle: setattr(oracle.runtime, "pending", {"action": "move"}),
            lambda oracle: setattr(
                oracle, "outcome_features_provider", lambda *_: None
            ),
            lambda oracle: setattr(
                oracle.runtime, "expiration_runtime_factory", object()
            ),
            lambda oracle: setattr(
                oracle.runtime.fight, "actors", {i: actor(i) for i in range(9)}
            ),
            lambda oracle: setattr(oracle.runtime.fight, "walkable", range(8193)),
            lambda oracle: oracle.runtime.expiration_runtime_factory.characters.__setitem__(
                7, {"id": 7}
            ),
        )
        with patch.dict(sys.modules, {_ORACLE_MODULE: _ORACLE_AUTHORITY}), patch.object(
            combat_expiration_provider, "OwnedExpirationFactory", _Provider
        ), patch.object(
            combat_retained_gc_authority,
            "capture_native_callbacks",
            return_value=object(),
        ), patch.object(
            world_sources, "bind_private_sources"
        ):
            for mutate in mutations:
                oracle, _ = detached_fixture()
                mutate(oracle)
                with self.subTest(mutation=mutate), self.assertRaisesRegex(
                    ValueError,
                    "Unsupported native oracle authority|Unsupported native trap preview source|Missing native trap preview viewer",
                ):
                    observation.detached_oracle(oracle)

    def test_detached_oracle_rejects_missing_callback_or_wrong_oracle_type(self):
        oracle, _ = detached_fixture()
        with patch.dict(sys.modules, {_ORACLE_MODULE: _ORACLE_AUTHORITY}), patch.object(
            combat_expiration_provider, "OwnedExpirationFactory", _Provider
        ), patch.object(
            combat_retained_gc_authority, "capture_native_callbacks", return_value=None
        ), patch.object(
            world_sources, "bind_private_sources"
        ):
            with self.assertRaisesRegex(
                ValueError, "Unsupported native trap preview source"
            ):
                observation.detached_oracle(oracle)

        with patch.dict(sys.modules, {_ORACLE_MODULE: _ORACLE_AUTHORITY}), patch.object(
            combat_expiration_provider, "OwnedExpirationFactory", _Provider
        ), patch.object(
            combat_retained_gc_authority,
            "capture_native_callbacks",
            return_value=object(),
        ):
            with self.assertRaisesRegex(
                ValueError, "Unsupported native oracle authority"
            ):
                observation.detached_oracle(NS(runtime=oracle.runtime))


if __name__ == "__main__":
    unittest.main()
