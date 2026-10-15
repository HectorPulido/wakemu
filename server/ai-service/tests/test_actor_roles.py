"""Bounded role usefulness from actor-bound native repertoire evidence."""
import json
from copy import deepcopy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_EXAMPLES = Path(__file__).resolve().parent / "fixtures/actor_role_native_examples.json"

from wakfu_ai.bridge.actor_repertoires import actor_repertoires
from wakfu_ai.planning.actor_roles import actor_role_profile
from test_query_search import FakeNativeSession, actor, run_search


def native_fixture_modules(data):
    """Patch catalog loaders with the bounded native extraction fixture."""
    casting = ModuleType("wakfu_server.combat_native_spell_casting")

    def native_casting_table(spell, level):
        record = data["casting"][str(spell)]
        if level != data["_provenance"]["tested_level"]:
            raise ValueError("Fixture has no native level row")
        return record, 0

    casting.native_casting_table = native_casting_table
    npc_attack = ModuleType("wakfu_server.combat_npc_attack")
    npc_attack.npc_runtime_catalog = lambda: SimpleNamespace(
        effects=data["effects"], source_states=data["states"]
    )
    damage = ModuleType("wakfu_server.combat_damage_healing")
    damage.DAMAGE_FAMILIES = (1, 2, 3, 4, 5, 917, 1083)
    damage.HEAL_ELEMENTS = {24: None, 25: 1, 251: 5, 253: 3, 258: 4, 259: 2, 1084: 6}
    displacement = ModuleType("wakfu_server.combat_displacement")
    displacement.FAMILIES = ()
    return {
        "wakfu_server.combat_native_spell_casting": casting,
        "wakfu_server.combat_npc_attack": npc_attack,
        "wakfu_server.combat_damage_healing": damage,
        "wakfu_server.combat_displacement": displacement,
    }


def native_capability_factory(data):
    from wakfu_server.combat_ai_capabilities import classify_roots

    def describe(spell_id, level):
        row = data["casting"][str(spell_id)]
        if level != data["_provenance"]["tested_level"]:
            raise ValueError("Fixture has no native capability row")
        minimum, maximum, roots = row["levels"][0]
        semantic = classify_roots(
            roots,
            data["effects"],
            states=data["states"],
            registry={},
            level=level,
        )
        return dict(
            spellId=spell_id,
            level=level,
            minimum=minimum,
            maximum=maximum,
            **semantic,
        )

    return describe


def actor_row(
    identity, team, position, *, hp=100, max_hp=100, ap=6, mp=3, wp=1, armor=0
):
    result = actor(identity, team, position, hp=hp, max_hp=max_hp, ap=ap, mp=mp, wp=wp)
    result["armor"] = armor
    return result


class ActorRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = json.loads(_EXAMPLES.read_text())

    def build_repertoires(self, actors, owned, *, source="root-state", revision=97):
        modules = native_fixture_modules(self.native)
        fight_actors = {
            row["id"]: SimpleNamespace(spell_ap_cost_modifiers={}) for row in actors
        }
        fight = SimpleNamespace(sequence=revision, actors=fight_actors)

        class Oracle:
            def owned_spells(self, _fight, identity):
                return owned.get(identity, {})

        from wakfu_ai.bridge.actor_repertoires import allied_healing_scope

        allied_healing_scope.cache_clear()
        with patch.dict(sys.modules, modules):
            records = actor_repertoires(
                Oracle(),
                fight,
                actors,
                source_state=source,
                capabilities=native_capability_factory(self.native),
            )
        allied_healing_scope.cache_clear()
        return records

    def test_native_41_healer_and_3_damage_roles_survive_bridge_to_profiles(self):
        actors = [
            actor_row(1, 1, (1, 0, 0)),
            actor_row(2, 1, (2, 0, 0), ap=4),
            actor_row(3, 1, (0, 2, 0), ap=3),
            actor_row(4, 1, (4, 4, 0), hp=10),
            actor_row(9, 0, (0, 0, 0), hp=10),
        ]
        records = self.build_repertoires(actors, {2: {5771: 14}, 3: {5773: 14}})
        healer_spell = records["2"]["spells"][0]
        damage_spell = records["3"]["spells"][0]
        self.assertIn("heal", healer_spell["advisoryCapabilities"]["tags"])
        self.assertTrue(healer_spell["advisoryCapabilities"]["allyTarget"])
        self.assertIn("damage", damage_spell["advisoryCapabilities"]["tags"])
        self.assertEqual(records["2"]["sourceState"], "root-state")
        self.assertEqual(records["3"]["stateRevision"], 97)

        state = dict(
            actors=actors, actorRepertoires=records, key="root-state", stateRevision=97
        )
        healer = actor_role_profile(state, 2)
        damage = actor_role_profile(state, 3)
        self.assertIn("healer", healer["useful_roles"])
        self.assertIn("damage_melee", damage["useful_roles"])
        self.assertGreater(healer["protection_value"], 0)
        self.assertGreater(damage["protection_value"], 0)
        self.assertFalse(healer["cast_legality_verified"])
        self.assertFalse(damage["cast_legality_verified"])

    def test_exhausted_healer_full_allies_and_self_only_heal_have_no_ally_utility(self):
        actors = [
            actor_row(2, 1, (0, 0, 0), hp=20, ap=4),
            actor_row(3, 1, (2, 0, 0)),
            actor_row(9, 0, (4, 0, 0)),
        ]
        records = self.build_repertoires(actors, {2: {5771: 14}})
        state = dict(
            actors=actors, actorRepertoires=records, key="root-state", stateRevision=97
        )
        self_only = records["2"]["spells"][0]
        self_only["advisoryCapabilities"].update(allyTarget=False, selfTarget=True)
        profile = actor_role_profile(state, 2)
        self.assertNotIn("healer", profile["useful_roles"])
        self.assertEqual(profile["protection_value"], 0)

        self_only["advisoryCapabilities"].update(allyTarget=True, selfTarget=False)
        actors[0]["hp"] = actors[0]["max_hp"]
        self.assertNotIn("healer", actor_role_profile(state, 2)["useful_roles"])

        actors[0]["hp"] = 20
        actors[0]["ap"] = 3
        self.assertIn("healer", actor_role_profile(state, 2)["intrinsic_roles"])
        self.assertNotIn("healer", actor_role_profile(state, 2)["usable_roles"])
        self.assertNotIn("healer", actor_role_profile(state, 2)["useful_roles"])

    def test_role_metadata_is_actor_and_state_bound_and_hybrid_utility_is_not_stacked(
        self,
    ):
        actors = [
            actor_row(1, 1, (0, 0, 0)),
            actor_row(2, 1, (1, 0, 0), hp=50, ap=6),
            actor_row(9, 0, (2, 0, 0), hp=50),
        ]
        dual = {
            "actorId": 2,
            "sourceState": "root-state",
            "stateRevision": 97,
            "spells": [
                {
                    "spellId": 5,
                    "level": 1,
                    "costOptions": [{"ap": 1, "mp": 0, "wp": 0}],
                    "advisoryCapabilities": {
                        "spellId": 5,
                        "level": 1,
                        "minimum": 0,
                        "maximum": 2,
                        "tags": ["damage", "heal"],
                        "allyTarget": True,
                        "unknownDependencies": [],
                        "conditional": False,
                    },
                }
            ],
        }
        state = dict(
            actors=actors,
            key="root-state",
            stateRevision=97,
            actorRepertoires={"2": dual},
        )
        profile = actor_role_profile(state, 2)
        self.assertIn("healer", profile["intrinsic_roles"])
        self.assertIn("damage_melee", profile["intrinsic_roles"])
        self.assertEqual(
            profile["protection_value"], max(profile["role_utilities"].values())
        )
        stale = deepcopy(state)
        stale["stateRevision"] += 1
        self.assertEqual(
            actor_role_profile(stale, 2)["data_gaps"], ["stale_actor_repertoire"]
        )
        wrong_owner = deepcopy(state)
        wrong_owner["actorRepertoires"]["2"]["actorId"] = 9
        self.assertIn(
            "missing_actor_bound_repertoire",
            actor_role_profile(wrong_owner, 2)["data_gaps"],
        )

    def test_bridge_queries_only_visible_living_actors_and_omits_dead_or_hidden_records(
        self,
    ):
        observed = [actor_row(2, 1, (0, 0, 0)), actor_row(3, 1, (1, 0, 0), hp=0)]
        calls = []
        modules = native_fixture_modules(self.native)
        fight = SimpleNamespace(
            sequence=97,
            actors={
                2: SimpleNamespace(spell_ap_cost_modifiers={}),
                3: SimpleNamespace(spell_ap_cost_modifiers={}),
            },
        )

        class Oracle:
            def owned_spells(self, _fight, identity):
                calls.append(identity)
                return {5771: 14}

        from wakfu_ai.bridge.actor_repertoires import allied_healing_scope

        allied_healing_scope.cache_clear()
        with patch.dict(sys.modules, modules):
            records = actor_repertoires(
                Oracle(),
                fight,
                observed,
                source_state="visible-state",
                capabilities=native_capability_factory(self.native),
            )
        allied_healing_scope.cache_clear()
        self.assertEqual(calls, [2])
        self.assertEqual(set(records), {"2"})
        self.assertEqual(records["2"]["sourceState"], "visible-state")

    def test_selected_action_prefers_healer_or_available_damage_dealer_by_current_demand(
        self,
    ):
        cells = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0), (0, 2, 0), (2, 1, 0)]
        pairs = [
            ((0, 0, 0), (1, 0, 0)),
            ((1, 0, 0), (2, 0, 0)),
            ((0, 0, 0), (0, 1, 0)),
            ((0, 1, 0), (0, 2, 0)),
            ((1, 0, 0), (0, 1, 0)),
            ((1, 0, 0), (2, 1, 0)),
        ]
        edges = pairs + [(end, start) for start, end in pairs]
        rows = [
            actor_row(1, 1, (1, 0, 0), ap=0, mp=2),
            actor_row(2, 1, (2, 0, 0), ap=4),
            actor_row(3, 1, (0, 2, 0), ap=0),
            actor_row(4, 1, (4, 4, 0), hp=10),
            actor_row(9, 0, (0, 0, 0), hp=10, mp=1),
        ]
        repertoires = self.build_repertoires(rows, {2: {5771: 14}, 3: {5773: 14}})

        def run_case(healer_ap, damage_ap, *, guard_hp=100):
            session = FakeNativeSession(spells=[], cells=cells, edges=edges)
            session.root_actors = deepcopy(rows)
            session.root_state["actors"] = deepcopy(rows)
            session.root_state["actorRepertoires"] = deepcopy(repertoires)
            session.envelope["root"] = session.root_state
            session.root_state["actors"][1]["ap"] = healer_ap
            session.root_state["actors"][2]["ap"] = damage_ap
            session.root_state["actors"][0]["hp"] = guard_hp
            session.root_state["actorRepertoires"] = deepcopy(repertoires)
            session.envelope["root"] = session.root_state
            original = session.request

            def request(query):
                response = original(query)
                if query["operation"] == "preview" and response.get("supported"):
                    public = response["result"]
                    records = deepcopy(repertoires)
                    for record in records.values():
                        record["sourceState"] = public["key"]
                        record["stateRevision"] = public["stateRevision"]
                    public["actorRepertoires"] = records
                return response

            session.request = request
            with patch(
                "wakfu_ai.planning.query_search.attacked_this_turn", return_value=True
            ):
                return run_search(session)

        # The same actor, geometry, and rival remain fixed. Only actor resources
        # swap which protected ally has an affordable, currently useful role.
        healer_plan = run_case(4, 0)
        damage_plan = run_case(0, 3)
        wounded_guard_plan = run_case(4, 0, guard_hp=5)
        self.assertEqual(healer_plan["action"]["type"], "end_turn")
        self.assertEqual(
            healer_plan["teamPosture"]["selected"]["protectedAllyIds"], [2]
        )
        healer_roles = healer_plan["teamPosture"]["selected"]["protectedAllyRoles"]
        self.assertIn("healer", healer_roles[2]["useful_roles"])
        self.assertEqual(damage_plan["action"]["type"], "move")
        self.assertEqual(
            damage_plan["teamPosture"]["selected"]["protectedAllyIds"], [3]
        )
        self.assertEqual(damage_plan["action"]["path"][-1], [0, 1, 0])
        damage_roles = damage_plan["teamPosture"]["selected"]["protectedAllyRoles"]
        self.assertIn("damage_melee", damage_roles[3]["useful_roles"])
        self.assertEqual(wounded_guard_plan["teamPosture"]["root"]["mode"], "retreat")
        self.assertEqual(wounded_guard_plan["action"]["type"], "move")


if __name__ == "__main__":
    unittest.main()
