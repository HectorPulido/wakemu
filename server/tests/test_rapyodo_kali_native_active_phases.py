"""Bounded native protection transitions on configured original room terrain.

Native gear/aptitudes are declared before Ready. No in-fight HP, state,
resource, area, clock or callback-result assignment is allowed. NPC movement
intents are explicit component inputs, not a Jondo/full-fight qualification.
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase

FIXTURES = Path(__file__).with_name("fixtures") / "native_active_boss_phases"


class NativeActiveProtectionPhases(PostgresCase):
    def setUp(self):
        super().setUp()
        from postgres_owned_schema_cleanup import empty_owned_schema

        with self.store.connection() as db:
            schema = db.execute("SELECT current_schema() AS name").fetchone()["name"]
        self.addCleanup(empty_owned_schema, self.store, schema)
        self.trace = []
        self.events = []

    @staticmethod
    def facts(fight):
        boss = fight.actors.get(-200)
        return dict(
            table=getattr(fight, "native_table_turn", None),
            current=None if fight.current is None else fight.current.id,
            hp=None if boss is None else boss.hp,
            max_hp=None if boss is None else boss.max_hp,
            minimum=None if boss is None else boss.effect_minima.get(1, 0),
            states=[]
            if boss is None
            else sorted(entry.reference for entry in boss.state_ledger.entries),
            actors={
                str(identity): dict(team=actor.team, hp=actor.hp, cell=actor.position)
                for identity, actor in fight.actors.items()
            },
            areas={
                str(ref): [
                    dict(uid=uid, cell=row["cell"])
                    for uid, row in getattr(fight, "native_effect_areas", {}).items()
                    if row["reference"] == ref
                ]
                for ref in (843, 879, 880, 882)
            },
        )

    def build(self, definition, reference):
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            native_paid_party_fixture,
        )
        from native_supreme_paid_component_runtime import PaidComponentRuntime
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.dungeon_runtime_config import level_selector
        from wakfu_server.monsters import reference as native_monster

        config = json.loads(
            (FIXTURES / f"native_dungeon_{definition}.json").read_text()
        )
        roster_room = next(
            room
            for room in config["compiled_plan"]["rooms"]
            if any(m["ref_id"] == reference for m in room["monsters"])
        )
        roster = next(m for m in roster_room["monsters"] if m["ref_id"] == reference)
        room = next(
            room
            for room in config["topology"]["rooms"]
            if room["order"] == roster_room["order"]
        )
        cells = set(map(tuple, room["cells"]))
        map_id = config["route"]["start_map_id"]
        geometry = map_geometry(map_id)
        level = level_selector(config, room_order=room["order"])(
            native_monster(reference),
            dict(
                min_level=roster["native_min_level"],
                max_level=roster["native_max_level"],
            ),
        )
        scene = dict(
            map_id=map_id,
            reference=reference,
            level=level,
            cells=cells,
            edges={
                (tuple(a), tuple(b))
                for a, b in geometry["edges"]
                if tuple(a) in cells and tuple(b) in cells
            },
            anchor=tuple(room["anchor"]),
        )
        fight, characters, monsters, decks, _, _, receipt = native_paid_party_fixture(
            self.store,
            scene,
            (native_endgame_iop_build(),),
            (tuple(room["anchor"]),),
            name_prefix={96: "Rapyodo", 121: "Kali"}[definition],
            fight_id=definition,
            initialization_seed=17,
            production_scene=True,
        )
        case = PaidComponentRuntime(
            fight, characters, monsters, decks, map_id=map_id, seed=17
        )
        case.runtime.turn_started(arm_deadline=False)
        receipt.update(
            configuration_version=config["version"],
            room_order=room["order"],
            reference=reference,
            full_roster=False,
            actual_room_scope=True,
        )
        self.setup_receipt = receipt
        return case

    def observer(self, original, watched):
        def observe(dispatcher, invocation, **kwargs):
            selected = invocation.reference in watched
            fight = dispatcher.native_retention.fight if selected else None
            before = self.facts(fight) if selected else None
            result = original(dispatcher, invocation, **kwargs)
            if selected:
                self.events.append(
                    dict(
                        effect=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        cell=invocation.cell,
                        result=bool(result),
                        before=before,
                        after=self.facts(fight),
                    )
                )
            return result

        return observe

    @staticmethod
    def drain(case):
        import struct

        for _ in range(64):
            if case.runtime.awaiting_ack is None:
                return
            case.runtime.acknowledge_turn(struct.pack(">i", case.runtime.awaiting_ack))
        raise AssertionError("Actual native ACK chain did not drain")

    def walk_player_to(self, case, accepts):
        actor = case.fight.current
        path = case.path_to(actor.id, accepts)
        if path and case.player_move_prefix(actor.id, path):
            self.drain(case)
            return True
        return False

    def paid_hit(self, case):
        from native_visible_target_fixture import visible_target_cells
        from wakfu_server.combat_server_spell import server_runtime

        actor, boss = case.fight.current, case.fight.actors[-200]
        path = case.cast_path(actor.id, -200, 1, 1, visible_footprint=True)
        if path and case.player_move_prefix(actor.id, path):
            self.drain(case)
            return True
        _, adapter = server_runtime(
            case.characters[actor.id],
            case.monsters,
            case.decks[actor.id],
            action_id=case.runtime.action_id + 1,
            critical=False,
            **case.common,
        )
        targets = visible_target_cells(
            case.fight,
            adapter.actor_authority,
            case.map_id,
            actor,
            boss,
            minimum=1,
            maximum=1,
        )
        if not targets:
            return False
        rejected = []
        for spell in (4777, 4780):
            try:
                payment = case.cast(actor.id, spell, -200, aim_cell=targets[0])
                self.assertGreater(payment["costs"]["ap"], 0)
                self.drain(case)
                return True
            except ValueError as error:
                rejected.append(dict(spell=spell, error=str(error)))
        self.trace.append(dict(rejected_owned_casts=rejected))
        return False

    def emit(self, name, case, *, passed):
        directory = os.environ.get("WAKFU_ACTIVE_PHASE_RECEIPTS")
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)
            evidence = dict(
                reference=case.monsters[-200]["ref"],
                passed=passed,
                setup=self.setup_receipt,
                final=self.facts(case.fight),
                events=self.events,
                trace=self.trace,
                payments=case.payments,
                awaiting_ack=case.runtime.awaiting_ack,
                in_battle_assignments=False,
                earned_victory=False,
                full_dungeon=False,
                npc_intents="bounded authored component inputs, not Jondo AI",
            )
            (Path(directory) / f"{name}.json").write_text(
                json.dumps(evidence, indent=2, default=str) + "\n"
            )

    def test_rapyodo_native_areas_paid_threshold_and_floor_removal(self):
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        watched = {
            148468,
            148469,
            148596,
            148474,
            149077,
            148476,
            148477,
            148478,
            148483,
            148484,
            148485,
            148487,
        }
        original = EffectDispatcher._execute_scoped
        with original_bootstrap_publication(), patch.object(
            EffectDispatcher, "_execute_scoped", self.observer(original, watched)
        ):
            case = self.build(96, 3399)
            self.assertTrue(
                case.fight.native_npc_initialization_receipts[-200]["initialized"]
            )
            self.assertNotIn(3255, self.facts(case.fight)["states"])
            initial_max = case.fight.actors[-200].max_hp
            passed = False
            completed = False
            try:
                for step in range(240):
                    fact = self.facts(case.fight)
                    self.trace.append(fact)
                    self.assertEqual(fact["max_hp"], initial_max)
                    if 3404 in fact["states"] and any(
                        e["effect"] == 148487 and e["result"] for e in self.events
                    ):
                        self.assertLess(fact["minimum"], initial_max // 2)
                        completed = True
                        break
                    current = case.fight.current
                    acted = False
                    if current.id in case.characters:
                        points = {tuple(row["cell"]) for row in fact["areas"]["879"]}
                        if 3402 in fact["states"] and points:
                            acted = self.walk_player_to(
                                case,
                                lambda cell: cell in points
                                and cell != current.position,
                            )
                        elif 3403 in fact["states"]:
                            acted = self.paid_hit(case)
                    elif current.id == -200 and 3403 in fact["states"]:
                        # Move only through the actual owned NPC movement/cost producer.
                        from wakfu_server.combat_obstacle_condition import footprint

                        blocked = {
                            tuple(cell)
                            for row in getattr(
                                case.fight, "native_effect_areas", {}
                            ).values()
                            if row["reference"] in (843, 882)
                            for cell in row["native_cells_xy"]
                        }
                        if (
                            set(footprint(current.position, current.physical_radius))
                            & blocked
                        ):
                            path = case.path_to(
                                -200,
                                lambda cell: not (
                                    set(footprint(cell, current.physical_radius))
                                    & blocked
                                ),
                            )
                            if path and current.mp > 0:
                                case.npc_move(path[: current.mp])
                                self.drain(case)
                                acted = True
                    if not acted:
                        case.advance()
                self.assertTrue(
                    completed,
                    "Native Rapyodo active transition did not finish: "
                    + repr(self.trace[-5:]),
                )
                self.assertTrue(
                    any(e["effect"] == 148596 and e["result"] for e in self.events),
                    "No original879 birth witnessed",
                )
                self.assertTrue(
                    any(e["effect"] == 149077 and e["result"] for e in self.events),
                    "No original879→880 entry callback witnessed",
                )
                self.assertTrue(
                    any(e["effect"] == 148477 and e["result"] for e in self.events),
                    "No original3402 removal witnessed",
                )
                self.assertTrue(
                    any(e["effect"] == 148478 and e["result"] for e in self.events),
                    "No original3403 installation witnessed",
                )
                self.assertTrue(
                    any(
                        p["kind"] == "player_cast"
                        and p["after"]["hp"] < p["before"]["hp"]
                        for p in case.payments
                    )
                )
                self.assertIsNone(case.runtime.awaiting_ack)
                passed = True
            finally:
                self.emit("rapyodo3399-active-phases", case, passed=passed)

    def test_kali_paid_half_hp_actual_own_start_removes_floor_and_calls7475(self):
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        watched = {
            330022,
            330023,
            330024,
            330025,
            330043,
            330031,
            330035,
            330039,
            330032,
            330036,
            330040,
        }
        original = EffectDispatcher._execute_scoped
        with original_bootstrap_publication(), patch.object(
            EffectDispatcher, "_execute_scoped", self.observer(original, watched)
        ):
            case = self.build(121, 4217)
            self.assertTrue(
                case.fight.native_npc_initialization_receipts[-200]["initialized"]
            )
            self.assertNotIn(7200, self.facts(case.fight)["states"])
            initial_max = case.fight.actors[-200].max_hp
            passed = False
            completed = False
            try:
                for step in range(160):
                    fact = self.facts(case.fight)
                    self.trace.append(fact)
                    self.assertEqual(fact["max_hp"], initial_max)
                    floor_removed = any(
                        e["effect"] == 330025 and e["result"] for e in self.events
                    )
                    callback = any(
                        e["effect"] == 330043 and e["result"] for e in self.events
                    )
                    native_roots = any(
                        e["effect"] in (330031, 330035, 330039) and e["result"]
                        for e in self.events
                    )
                    if floor_removed and callback and native_roots:
                        self.assertLess(fact["minimum"], initial_max // 2)
                        completed = True
                        break
                    acted = False
                    if (
                        case.fight.current.id in case.characters
                        and fact["hp"] > fact["minimum"]
                    ):
                        acted = self.paid_hit(case)
                    if not acted:
                        case.advance()
                self.assertTrue(
                    completed,
                    "Native Kali threshold/own-start callback did not finish: "
                    + repr(self.trace[-5:]),
                )
                self.assertTrue(
                    any(e["effect"] == 330022 and e["result"] for e in self.events),
                    "No native opening floor observed",
                )
                self.assertTrue(
                    any(
                        p["kind"] == "player_cast"
                        and p["after"]["hp"] < p["before"]["hp"]
                        for p in case.payments
                    )
                )
                self.assertIsNone(case.runtime.awaiting_ack)
                passed = True
            finally:
                self.emit("kali4217-active-phase", case, passed=passed)

    def test_rapyodo_opening_and_last879_boundary_diagnostic(self):
        """Stop at the first consumed population; do not replay idle tables."""
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        watched = {
            148467,
            148468,
            148469,
            148472,
            148595,
            148596,
            148474,
            149076,
            149077,
            148476,
            148477,
            148478,
        }
        original = EffectDispatcher._execute_scoped
        with original_bootstrap_publication(), patch.object(
            EffectDispatcher, "_execute_scoped", self.observer(original, watched)
        ):
            case = self.build(96, 3399)
            passed = False
            try:
                for _ in range(40):
                    fact = self.facts(case.fight)
                    self.trace.append(fact)
                    births = any(
                        event["effect"] == 148596 and event["result"]
                        for event in self.events
                    )
                    consumed = any(
                        event["effect"] == 149077 and event["result"]
                        for event in self.events
                    )
                    if births and consumed and not fact["areas"]["879"]:
                        # Capture the immediate subsequent genuine clock boundary.
                        case.advance()
                        self.trace.append(self.facts(case.fight))
                        break
                    if not births and fact["table"] >= 3:
                        break
                    points = {tuple(row["cell"]) for row in fact["areas"]["879"]}
                    actor = case.fight.current
                    moved = (
                        actor.id in case.characters
                        and points
                        and self.walk_player_to(
                            case, lambda cell: cell in points and cell != actor.position
                        )
                    )
                    if not moved:
                        case.advance()
                self.assertTrue(births, "Original879 constructor was not observed")
                self.assertTrue(consumed, "Original879 entry callback was not observed")
                self.assertFalse(
                    self.facts(case.fight)["areas"]["879"],
                    "Bounded native path has not consumed the population",
                )
                passed = True
            finally:
                self.emit("rapyodo3399-first-empty879-boundary", case, passed=passed)
