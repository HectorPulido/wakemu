"""New native Nemotilus consumer uses common operations without ID dispatch."""
from copy import deepcopy
from pathlib import Path
import json
import hashlib
import inspect
import sys
from types import FunctionType
import unittest

from tools.combat_movement_differential import observe_movement
from wakfu_server.combat_npc_spell import prepare_npc_spell
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import default_deck


def detached_native_world(value):
    """Copy even shared static views for strict branch ownership checking."""
    from wakfu_server.combat_static_catalogs import ImmutableCatalog
    from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet
    from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook

    memo = {}
    seen = set()

    def prepare(item):
        identity = id(item)
        if identity in seen:
            return
        seen.add(identity)
        if type(item) is ImmutableCatalog:
            # Its normal deepcopy intentionally shares read-only static assets.
            # Here the differential guard requires disjoint complete graphs,
            # including the underlying export dictionaries and lazy views.
            memo[identity] = ImmutableCatalog(deepcopy(item._source, memo))
            return
        if type(item) is ImmutableTerrainSet:
            memo[identity] = ImmutableTerrainSet(cell for cell in item)
            return
        if item is ordinary_npc_spellbook:
            if item.__closure__ or item.__defaults__ or item.__kwdefaults__:
                raise AssertionError("Unexpected captured NPC spellbook provider state")
            provider = FunctionType(item.__code__, item.__globals__, item.__name__)
            provider.__qualname__ = item.__qualname__
            provider.__module__ = item.__module__
            memo[identity] = provider
            return
        if isinstance(item, dict):
            children = (*item.keys(), *item.values())
        elif isinstance(item, (list, tuple, set, frozenset)):
            children = tuple(item)
        else:
            children = ()
        if hasattr(item, "__dict__"):
            children = (*children, *vars(item).values())
        for child in children:
            prepare(child)

    prepare(value)
    return deepcopy(value, memo)


def native_world_observation(fight):
    """Capture game state plus the explicit trusted rail-provider rebuild facts."""
    from wakfu_server.combat_reproduction_state import encode_state
    from wakfu_server.combat_summon import RegisteredSummonAuthority
    from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
    from wakfu_server.combat_static_catalogs import ImmutableCatalog
    from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook

    authority = fight.native_rail_movement_authority
    if type(authority) is not RegisteredSummonAuthority or set(vars(authority)) != {
        "ordinary"
    }:
        raise AssertionError("Unknown rail authority rebuild contract")
    ordinary = authority.ordinary
    if type(ordinary) is not OrdinaryActorAuthority:
        raise AssertionError("Unknown ordinary rail authority type")
    facts = dict(vars(ordinary))
    catalog = facts.pop("catalog")
    provider = facts.pop("npc_spellbook")
    if type(catalog) is not ImmutableCatalog or catalog._views:
        raise AssertionError("Unknown rail catalog representation")
    catalog_bytes = json.dumps(
        catalog._source, sort_keys=True, separators=(",", ":")
    ).encode()
    descriptor = {
        "type": type(authority).__module__ + "." + type(authority).__qualname__,
        "ordinary_type": type(ordinary).__module__ + "." + type(ordinary).__qualname__,
        "ordinary_data": encode_state(facts),
        "immutable_catalog_source_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "npc_spellbook": None,
    }
    if provider is not None:
        if (
            type(provider) is not FunctionType
            or provider.__closure__
            or provider.__defaults__
            or provider.__kwdefaults__
            or provider.__code__ is not ordinary_npc_spellbook.__code__
            or vars(provider)
        ):
            raise AssertionError("Unknown captured NPC spellbook provider")
        descriptor["npc_spellbook"] = {
            "module": provider.__module__,
            "qualname": provider.__qualname__,
            "source_sha256": hashlib.sha256(
                inspect.getsource(provider).encode()
            ).hexdigest(),
            "source_file_sha256": hashlib.sha256(
                Path(inspect.getsourcefile(provider)).read_bytes()
            ).hexdigest(),
            "rebuild": "fresh stateless function; exact original code and globals; no closure/defaults/instance state",
        }
    if descriptor["ordinary_data"]["services"]:
        raise AssertionError("Unexpected nested ordinary authority services")
    descriptor["ordinary_data"] = json.dumps(
        descriptor["ordinary_data"],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    state = encode_state(fight)
    if (
        len(state["services"]) != 1
        or state["services"][0]["field"] != "native_rail_movement_authority"
    ):
        raise AssertionError("Unexpected omitted native services")
    return {
        "game_state": json.dumps(
            state,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii"),
        "native_rail_movement_authority": descriptor,
    }


class SpatialPilotNewAttackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Borrow only the genuine native actor/arena constructor, not AI policy.
        ai_root = Path(__file__).resolve().parents[1] / "ai-service"
        for path in (ai_root, ai_root / "tests"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from test_native_oracle import NativeOracleTests
        from wakfu_server.combat_npc_attack import npc_spell_catalog
        from wakfu_server.combat_native_spell_casting import catalog
        from wakfu_server.monsters import native_abilities

        cls.template = NativeOracleTests.wonejo_fixture(
            monster_ref=4157,
            monster_level=42,
        )
        cls.template.fight.order = [cls.template.npc.id, cls.template.pc.id]
        cls.template.fight.turn_index = 0
        cls.native = npc_spell_catalog()
        cls.casting = catalog()["5868"]
        cls.owned = native_abilities(4157, 42)
        cls.evidence = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "combat_spatial_pilot_nemotilus_evidence.json"
            ).read_text()
        )

    def test_unmodified_native_attack_uses_current_spatial_boundary(self):
        from wakfu_server import native_catalog

        self.assertEqual(native_catalog.release(), self.evidence["release"])
        hashes = native_catalog.document_hashes()
        for name, record in self.evidence["documents"].items():
            self.assertEqual(hashes[name], record["sha256"])
        self.assertIn(
            {"spell_id": 5868, "level_parameter": -1, "spell_level": 42},
            self.owned,
        )
        self.assertEqual(self.casting["levels"][41], [1, 1, [186717]])
        self.assertEqual(self.casting["costs"][41], [2, 0, 0])
        effect = self.native["effects"]["186717"]
        for key, value in self.evidence["effect"]["definition"].items():
            self.assertEqual(effect[key], value, key)
        self.assertEqual(effect["effect_class"], 300)
        self.assertEqual(effect["parameters"], [3.0, 0.0, 0.0, 0.0])
        self.assertEqual(effect["native_target_selector"], {"class": "fcE", "mask": 9})
        self.assertEqual(
            self.casting["cast_criterion_raw"], 'not IsBreedId("target", 4152)'
        )
        template = self.template
        initial = snapshot(template.fight)
        initial_ap = template.npc.ap
        target_position = template.pc.position
        results = {}

        def make_world(context):
            return detached_native_world(
                {
                    "fight": template.fight,
                    "character": template.character,
                    "monster": template.monster,
                    "deck": default_deck(template.character),
                }
            )

        def operation():
            def execute(world, inputs, context):
                fight = world["fight"]
                source = snapshot(fight)
                tx = prepare_npc_spell(
                    fight,
                    {
                        "type": "cast",
                        "spellId": 5868,
                        "level": 42,
                        "target": list(target_position),
                        "targetId": template.pc.id,
                    },
                    world["character"],
                    {world["monster"]["id"]: world["monster"]},
                    world["deck"],
                    action_id=11,
                    rng=context.rng,
                )
                self.assertEqual(snapshot(fight), source)
                world["fight"] = tx.fight
                results["current"] = tx
                for event in tx.events:
                    context.event(event)
                for opcode, payload in tx.packets:
                    context.packet(template.pc.id, opcode, payload)
                return {"plan": tx.plan, "outcomes": tx.outcomes}

            return execute

        def project(world):
            return native_world_observation(world["fight"])

        report = observe_movement(
            case_id="new-native-nemotilus-4157-5868",
            make_world=make_world,
            operation=operation(),
            project_state=project,
        )
        self.assertTrue(report["action_succeeded"], report)
        self.assertFalse(report["live_delivery"])
        self.assertEqual(snapshot(template.fight), initial)
        for backend, tx in results.items():
            with self.subTest(backend=backend):
                self.assertEqual(tx.fight.actors[template.npc.id].ap, initial_ap - 2)
                self.assertEqual(tx.fight.actors[template.npc.id].mp, template.npc.mp)
                self.assertEqual(
                    tx.fight.actors[template.npc.id].effect_stats[4],
                    template.npc.effect_stats[4],
                )
                self.assertNotEqual(
                    tx.fight.actors[template.pc.id].position, target_position
                )
                self.assertEqual(
                    tx.fight.actors[template.npc.id].position, template.npc.position
                )
                self.assertEqual(
                    [opcode for opcode, _ in tx.packets[:2]], [12588, 12678]
                )
                self.assertTrue(any(opcode == 12613 for opcode, _ in tx.packets))
                self.assertTrue(tx.outcomes)


if __name__ == "__main__":
    unittest.main()
