"""Actual bootstrap, frozen scene metadata and first native callbacks for five bosses."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from random import Random
from types import SimpleNamespace
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))


class SupremeProductionSceneBootstrapTests(unittest.TestCase):
    def _witness(self, reference, level, map_id):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_tank_witness_fixture import native_tank_fixture
        from ultimate_encounter_scene_recipes import encounter_fixture_factory
        from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
        from wakfu_server.combat_placement_policy import freeze
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
        from wakfu_server.combat_qi_snapshot import NativeQISnapshot
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from test_ultimate_encounter_scene_recipes import (
            UltimateNativePaidProducerTests,
        )

        geometry = json.loads(
            (ROOT / f".runtime/ultimate-scenes-20261021/map-{map_id}.json").read_text()
        )
        scene = resolve_supreme_scene(reference, geometry)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = (
            ROOT
            / f".runtime/ultimate-scenes-20261021/production-bootstrap-{reference}-{stamp}.json"
        )
        receipt = dict(
            reference=reference,
            map_id=map_id,
            status="pending",
            complete_encounter_qualified=False,
        )
        try:
            tank, facts = native_tank_fixture(validator, feca=True)
            db = FrozenPlacementDB(map_id)
            store = SimpleNamespace(lock_character=lambda *args: None)

            def durable(character, members, selected):
                arguments = dict(
                    account_id=character["account_id"],
                    generation=1,
                    character_id=character["id"],
                    fight_id=78,
                    map_id=map_id,
                    instance_id=0,
                    selected_arena=selected,
                    seeds={
                        0: [(character["x"], character["y"], character["z"])],
                        1: [
                            (member["x"], member["y"], member["z"])
                            for member in members
                        ],
                    },
                    db=db,
                )
                first = freeze(store, **arguments)
                db.layout = json.loads(json.dumps(db.layout))
                second = freeze(store, **arguments)
                self.assertEqual(first["validated_cells"], second["validated_cells"])
                self.assertEqual(first["valid_edges"], second["valid_edges"])
                self.assertEqual(first["placement_cells"], second["placement_cells"])
                self.assertEqual(
                    first["native_encounter_scene_layout"],
                    second["native_encounter_scene_layout"],
                )
                self.assertEqual(first["cell_masks"], second["cell_masks"])
                self.assertEqual(db.inserts, 1)
                receipt["durable_json_layout"] = deepcopy(db.layout)
                return second

            fixture, preparation = encounter_fixture_factory(
                validator,
                scene,
                caster_cell=scene["source"],
                player_level=200,
                player_breed=1,
                player_deck=[6972],
                character_constructor=tank.__globals__["_healthy_owned_character"],
                production_bootstrap=True,
                arena_transform=durable,
            )
            with original_bootstrap_publication():
                fight, character, monsters, deck = fixture(
                    reference, level, scene["anchor"], native_lifecycle=False
                )
            receipt.update(preparation=preparation, healthy_native_player=facts)
            self.assertEqual(fight.actors[-200].position, scene["source"])
            self.assertEqual(fight.actors[7].position, scene["anchor"])
            self.assertEqual(
                fight.actors[-200].direction, scene.get("boss_direction", 3)
            )
            npc_wire = preparation["bootstrap_native_actor_wire"][-200]
            self.assertEqual(npc_wire["format"], 2)
            self.assertEqual(npc_wire["direction"], scene.get("boss_direction", 3))
            self.assertGreater(npc_wire["effects_bytes"], 0)
            self.assertEqual(fight.walkable, scene["cells"])
            self.assertEqual(fight.edges, scene["edges"])
            self.assertEqual(
                fight.native_encounter_scene_layout["source"], list(scene["source"])
            )
            self.assertFalse(
                fight.native_encounter_scene_layout["original_world_coordinates"]
            )
            self.assertTrue(
                fight.native_npc_initialization_receipts[-200]["initialized"]
            )
            self.assertEqual(
                fight.native_npc_initialization_receipts[-200]["ref"], reference
            )
            qi = NativeQISnapshot(fight.native_qi_snapshot)
            if reference == 3582:
                from wakfu_server.combat_battleground_border import (
                    verify_battleground_border,
                )

                borders = [
                    row
                    for row in fight.native_effect_areas.values()
                    if row.get("reference") == 909
                ]
                self.assertEqual(len(borders), 1)
                verify_battleground_border(fight, borders[0])
                self.assertEqual(fight.native_border_constructor["reference"], 909)
                receipt["steel_native_border"] = deepcopy(borders[0])
            receipt["qi"] = dict(
                x=qi.x,
                y=qi.y,
                width=qi.width,
                height=qi.height,
                mask_count=len(qi.masks),
                mask_values=sorted(set(qi.masks)),
                surface_provenance=fight.native_qi_surface_provenance,
            )
            receipt["constructor"] = deepcopy(
                fight.native_npc_initialization_receipts[-200]
            )
            with self.assertRaises(ValueError):
                prepare_encounter_scene(
                    dict(character, map_id=map_id + 1),
                    list(monsters.values()),
                    dict(map_id=map_id, instance_id=0),
                    layout=scene,
                )
            rng = Random(0)
            fight, startup = prepare_server_initialization(
                character,
                monsters,
                fight,
                character["account_id"],
                deck,
                action_id=2,
                rng=rng,
                fight_start=True,
                player_characters={7: character},
                deck_blobs={7: deck},
            )
            serializer = UltimateNativePaidProducerTests._serializer(
                character, monsters
            )
            runtime = RuntimeMessages(
                fight,
                runtime_stats_serializer=serializer,
                turn_start_provider=lambda phase, **kwargs: prepare_server_turn_start(
                    character,
                    monsters,
                    phase,
                    deck,
                    rng=rng,
                    native_events=True,
                    area_callbacks=True,
                    **kwargs,
                ),
                turn_end_provider=lambda phase, **kwargs: prepare_server_turn_end(
                    character, monsters, phase, deck, rng=rng, **kwargs
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    monsters,
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            first = runtime.turn_started()
            current = runtime.fight
            if reference == 1988:
                landing_markers = [
                    row
                    for row in current.native_effect_areas.values()
                    if row.get("reference") == 1724
                ]
                self.assertEqual(len(landing_markers), 1)
                marker = landing_markers[0]
                self.assertEqual(tuple(marker["cell"]), (-5, -4, 88))
                self.assertEqual(marker["native_area_contract"], "faY")
                self.assertIsNone(marker["owner_id"])
                self.assertEqual(marker["level"], 0)
                self.assertEqual(
                    marker["native_environment_policy"],
                    "wakemu.crow.reconstructed-main-board-landing.v1",
                )
                receipt["crow_initial_landing_marker"] = deepcopy(marker)
            receipt.update(
                status="production_bootstrap_and_first_native_callbacks_observed",
                startup_packets=len(startup),
                first_turn_packets=len(first),
                table_turn=getattr(current, "native_table_turn", None),
                turn_id=current.turn_id,
                phase=current.phase,
                current_id=None if current.current is None else current.current.id,
                actors={
                    str(identity): dict(
                        hp=actor.hp,
                        position=actor.position,
                        states=[
                            (entry.reference, entry.level)
                            for entry in actor.state_ledger.entries
                        ],
                    )
                    for identity, actor in current.actors.items()
                },
                areas=[
                    dict(reference=row["reference"], cell=row["cell"])
                    for row in current.native_effect_areas.values()
                ],
                pending_ack=runtime.awaiting_ack,
                guide_mechanics_scope="placement_verified_dynamic_actors_and_areas_observed_full_phase_and_victory_unqualified",
            )
            self.assertTrue(startup)
            self.assertTrue(first)
        except Exception as error:
            import traceback

            receipt.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")

    def test_crow_production_bootstrap_and_first_native_turn(self):
        self._witness(1988, 110, 363)

    def test_steel_production_bootstrap_and_first_native_turn(self):
        self._witness(3582, 170, 959)

    def test_dragon_pig_production_bootstrap_and_first_native_turn(self):
        self._witness(2430, 125, 545)

    def test_nogord_production_bootstrap_and_first_native_turn(self):
        self._witness(3433, 200, 1092)

    def test_ombrage_production_bootstrap_and_first_native_turn(self):
        self._witness(4770, 200, 1229)


class FrozenPlacementDB:
    """JSONB transaction adapter; validates production freeze without live writes."""

    def __init__(self, map_id):
        from psycopg.pq import TransactionStatus

        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.map_id = map_id
        self.layout = None
        self.inserts = 0

    def execute(self, sql, params=None):
        if sql.startswith("SELECT status FROM combat_fights"):
            result = {"status": "placement"}
        elif sql.startswith("SELECT 1 FROM combat_fight_participants"):
            result = {"present": 1}
        elif sql.startswith("SELECT map_id,instance_id,layout"):
            result = (
                None
                if self.layout is None
                else dict(map_id=self.map_id, instance_id=0, layout=self.layout)
            )
        elif sql.startswith(
            "SELECT value FROM settings WHERE name='fight_placement_policy'"
        ):
            result = {
                "value": dict(version=1, slots_per_team=12, variation_enabled=True)
            }
        elif sql.startswith("SELECT value FROM settings WHERE name=%s"):
            result = {"value": dict(version=1, pool=[46])}
        elif sql.startswith("INSERT INTO fight_placement_layouts"):
            self.layout = deepcopy(params[-1].obj)
            self.inserts += 1
            result = None
        else:
            raise AssertionError(sql)
        return SimpleNamespace(fetchone=lambda: result)
