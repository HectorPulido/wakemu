"""Native capability metadata and bounded candidate-generation regressions."""
import copy
import unittest
from types import SimpleNamespace

from wakfu_server.combat_ai_capabilities import classify_roots, target_affinity
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_tactical_ai import NativeProvider, Preview, build_request


class CapabilityMetadataTests(unittest.TestCase):
    def test_classifies_mixed_child_families_without_claiming_effect_magnitudes(self):
        result = classify_roots(
            [100],
            {
                "100": {"effect_class": 910, "children": [101, 102]},
                "101": {"effect_class": 1},
                "102": {"effect_class": 24, "criteria": "TargetIsAlly"},
            },
        )

        self.assertEqual(result["tags"], ["area", "damage", "heal"])
        self.assertTrue(result["conditional"])
        self.assertEqual(result["unknownDependencies"], [])
        self.assertNotIn("damage", result)
        self.assertNotIn("healing", result)

    def test_unknown_and_cyclic_dependencies_remain_explicit(self):
        missing = classify_roots([200], {"200": {"effect_class": 1, "children": [999]}})
        cycle = classify_roots(
            [300],
            {
                "300": {"effect_class": 910, "children": [301]},
                "301": {"effect_class": 910, "children": [300]},
            },
        )

        self.assertEqual(missing["tags"], ["damage", "unknown"])
        self.assertEqual(missing["unknownDependencies"], ["missing_effect:999"])
        self.assertEqual(cycle["tags"], ["area", "unknown"])
        self.assertEqual(cycle["unknownDependencies"], ["cyclic_effect_tree"])

    def test_capability_affinity_prioritizes_wounded_support_target(self):
        caster = SimpleNamespace(team=1)
        wounded_ally = SimpleNamespace(team=1, hp=9, max_hp=30, id=-2)
        full_health_enemy = SimpleNamespace(team=0, hp=30, max_hp=30, id=7)
        heal = {"tags": ["heal"]}

        ranked = sorted(
            [full_health_enemy, wounded_ally],
            key=lambda target: target_affinity(heal, caster, target),
        )

        self.assertIs(ranked[0], wounded_ally)
        self.assertGreater(target_affinity(heal, caster, full_health_enemy)[0], 0)


class FakeCapabilityProvider(NativeProvider):
    """Use metadata and outcomes only; no native catalog compilation needed."""

    def __init__(self, capabilities, *, policy=None, forecast_limits=None):
        super().__init__({}, {}, b"", policy=policy, forecast_limits=forecast_limits)
        self._capabilities = copy.deepcopy(capabilities)

    @property
    def catalog_version(self):
        return "fake-native-capability-catalog-v1"

    def capabilities(self, fight):
        return copy.deepcopy(self._capabilities)

    def preview(self, fight, action, action_id, *, forecast):
        if action["type"] == "move":
            candidate = copy.deepcopy(fight)
            candidate.server_move(
                candidate.current.id, [tuple(cell) for cell in action["path"]]
            )
            return Preview(candidate)

        if action.get("targetId") is None:
            raise ValueError("Fixture cast requires a living actor target")
        candidate = copy.deepcopy(fight)
        caster = candidate.current
        target = candidate.actors[action["targetId"]]
        capability = next(
            row for row in self._capabilities if row["spellId"] == action["spellId"]
        )
        tags = set(capability["tags"])
        if "heal" in tags and target.team == caster.team:
            target.hp = min(target.max_hp, target.hp + capability["fixtureHealing"])
            candidate._sync_resources(target)
        elif "damage" in tags and target.team != caster.team:
            target.hp = max(0, target.hp - capability["fixtureDamage"])
            candidate._sync_resources(target)
        else:
            raise ValueError("No fixture-native outcome for target/family")
        candidate._event("fixture_cast", actor_id=caster.id, target_id=target.id)
        return Preview(candidate)


class CapabilityGenerationTests(unittest.TestCase):
    def fight(self, *, npc_position=0, enemy_position=5, ally=None, mp=3):
        cells = {(x, 0, 0) for x in range(7)}
        edges = {
            (source, target)
            for source in cells
            for target in cells
            if abs(source[0] - target[0]) == 1
        }
        npc = Actor(-10, 1, (npc_position, 0, 0), 20, 6, mp, 10, 1)
        actors = [npc]
        if ally is not None:
            ally_x, ally_hp, ally_max = ally
            actors.append(
                Actor(-11, 1, (ally_x, 0, 0), ally_hp, 6, 3, 5, 1, max_hp=ally_max)
            )
        enemy = Actor(7, 0, (enemy_position, 0, 0), 30, 6, 3, 0, 1, 20, True)
        actors.append(enemy)
        for actor in actors:
            actor.effect_stats = {1: actor.hp, 2: actor.ap, 3: actor.mp, 4: 2, 97: 0}
            actor.effect_maxima = {1: actor.max_hp, 4: 2}
        fight = Fight(
            77,
            actors,
            cells,
            {0: set(cells), 1: set(cells)},
            edges,
        )
        fight.ready(20)
        return RuntimeMessages(fight)

    @staticmethod
    def cap(spell, tags, minimum, maximum, **fixture_effect):
        return dict(
            spellId=spell,
            level=1,
            minimum=minimum,
            maximum=maximum,
            tags=list(tags),
            conditional=False,
            unknownDependencies=[],
            **fixture_effect,
        )

    @staticmethod
    def root_transitions(request):
        root = next(
            state for state in request["states"] if state["key"] == request["rootState"]
        )
        return [row["action"] for row in root["transitions"]]

    def test_budget_round_robins_support_attack_and_movement_candidates(self):
        runtime = self.fight(ally=(2, 9, 30))
        provider = FakeCapabilityProvider(
            [
                self.cap(101, ["heal"], 0, 4, fixtureHealing=15),
                self.cap(202, ["damage"], 1, 6, fixtureDamage=8),
            ]
        )

        request = build_request(
            runtime, provider, max_previews=3, budget_ms=1000, depth=1
        )
        actions = self.root_transitions(request)
        result = self.decide(request)

        self.assertEqual(request["producerTrace"]["previews"], 3)
        self.assertEqual(actions[0]["type"], "cast")
        self.assertEqual((actions[0]["spellId"], actions[0]["targetId"]), (101, -11))
        self.assertEqual((actions[1]["spellId"], actions[1]["targetId"]), (202, 7))
        self.assertEqual(actions[2]["type"], "move")
        self.assertEqual(result["decision"]["intent"], "heal")
        self.assertEqual(result["decision"]["target_id"], -11)

    def test_ranged_repertoire_moves_only_to_first_legal_casting_distance(self):
        runtime = self.fight(npc_position=0, enemy_position=4, mp=3)
        provider = FakeCapabilityProvider(
            [self.cap(303, ["damage"], 2, 3, fixtureDamage=12)]
        )

        request = build_request(
            runtime, provider, max_previews=32, budget_ms=1000, depth=2
        )
        result = self.decide(request)
        first = result["decision"]["actions"][0]

        self.assertEqual(first, {"type": "move", "path": [[1, 0, 0]]})
        self.assertEqual(len(result["decision"]["actions"]), 2)
        self.assertEqual(result["decision"]["actions"][1]["spellId"], 303)
        self.assertEqual(result["decision"]["actions"][1]["targetId"], 7)

    def test_heal_only_capability_does_not_chase_a_full_health_enemy(self):
        runtime = self.fight(npc_position=0, enemy_position=5, ally=(2, 30, 30), mp=3)
        provider = FakeCapabilityProvider(
            [self.cap(404, ["heal"], 0, 5, fixtureHealing=10)]
        )

        request = build_request(
            runtime, provider, max_previews=32, budget_ms=1000, depth=1
        )
        result = self.decide(request)

        self.assertTrue(
            all(
                action.get("targetId") != 7 for action in self.root_transitions(request)
            )
        )
        self.assertEqual(result["decision"]["actions"], [{"type": "end_turn"}])

    def test_movement_shortlist_preserves_back_and_side_cells_for_all_directions(self):
        from types import SimpleNamespace
        from wakfu_server.combat_ordinary_authority import native_facing

        cells = {(x, y, 0) for x in range(11) for y in range(11)}
        edges = set()
        for source in cells:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                target = (source[0] + dx, source[1] + dy, 0)
                if target in cells:
                    edges.add((source, target))
        npc = Actor(-10, 1, (0, 0, 0), 20, 6, 20, 10, 1)
        enemy = Actor(7, 0, (5, 5, 0), 30, 6, 3, 0, 1, 20, True)
        npc.effect_stats = {1: 20, 2: 6, 3: 20, 4: 2, 97: 0}
        enemy.effect_stats = {1: 30, 2: 6, 3: 3, 4: 0, 97: 0}
        npc.effect_maxima = {1: 20, 4: 2}
        enemy.effect_maxima = {1: 30, 4: 0}
        fight = Fight(88, [npc, enemy], cells, {0: set(cells), 1: set(cells)}, edges)
        fight.ready(20)
        provider = FakeCapabilityProvider(
            [self.cap(505, ["damage"], 1, 10, fixtureDamage=1)]
        )

        for direction in range(8):
            enemy.direction = direction
            movement_actions = [
                action for action in provider.actions(fight) if action["type"] == "move"
            ]
            localizations = {
                native_facing(
                    SimpleNamespace(position=tuple(action["path"][-1])), enemy
                )
                for action in movement_actions
            }
            with self.subTest(direction=direction):
                self.assertIn("BACK", localizations)
                self.assertIn("SIDE", localizations)

    def test_geometric_pressure_feature_rewards_retreat_without_fabricated_damage(self):
        runtime = self.fight(npc_position=2, enemy_position=4, mp=2)
        provider = FakeCapabilityProvider(
            [],
            policy={"featureWeights": {"geometric_threat_cells": -1}},
        )

        def geometry(state):
            npc = state.current
            enemies = [
                actor for actor in state.actors.values() if actor.team != npc.team
            ]
            return sum(
                abs(npc.position[0] - enemy.position[0])
                + abs(npc.position[1] - enemy.position[1])
                <= 2
                for enemy in enemies
            )

        provider.outcome_features = lambda state: {
            "positionValue": 0,
            "outcomeFeatures": {"geometric_threat_cells": geometry(state)},
        }
        original_hp = {
            identity: actor.hp for identity, actor in runtime.fight.actors.items()
        }

        request = build_request(
            runtime, provider, max_previews=16, budget_ms=1000, depth=1
        )
        result = self.decide(request)

        self.assertEqual(result["decision"]["actions"][0]["type"], "move")
        self.assertGreater(
            result["decision"]["score_components"]["feature:geometric_threat_cells"], 0
        )
        self.assertEqual(result["decision"]["score_components"]["damage"], 0)
        self.assertEqual(
            {identity: actor.hp for identity, actor in runtime.fight.actors.items()},
            original_hp,
        )

    @staticmethod
    def decide(request):
        from tests.test_ai_service import planner

        return planner.decide(request)


if __name__ == "__main__":
    unittest.main()
