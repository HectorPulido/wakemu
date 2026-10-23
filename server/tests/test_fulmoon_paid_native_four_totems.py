"""Four original Moon totems earn4227 through paid hammer and small owned hits."""
import json
from pathlib import Path

from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]


class FulMoonPaidNativeFourTotemsTests(PostgresCase):
    def test_four_living_original_totems_earn_4227_without_hp_or_state_gifts(self):
        from native_paid_party_fixture import (
            NativePartyBuild,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_supreme_paid_component_runtime import PaidComponentRuntime
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
        )

        scene = reconstructed_fulmoon_scene(
            json.loads(
                (
                    ROOT / ".runtime/parallel-readiness-20261021/"
                    "supreme-entry-staging/map-1056.json"
                ).read_text()
            )
        )
        scene.update(reference=3870, level=185)
        # Declared component approach only, before actual actors/Ready/QI exist.
        # Native terrain, boss source, original point outputs and border stay intact.
        positions = (
            (-2, 3, 0),
            (5, 1, 0),
            (-1, 6, 0),
            (6, 5, 0),
            (4, 3, 0),
            (-3, 2, 0),
        )
        self.assertTrue(set(positions) <= set(scene["cells"]))
        self.assertFalse(
            set(positions)
            & (
                set(scene["glyph_cells"])
                | set(scene["boss_footprint"])
                | set(scene["native_border_cells"])
            )
        )
        scene["party_placement_cells"] = positions
        scene["anchor"] = positions[0]
        # Bare ordinary200 characters: real native aptitude budgets, no damage gear.
        # 4780 is an owned2AP range1..3 action, already paid in the Agonia witness.
        build = NativePartyBuild(
            8,
            200,
            (4780,),
            ((1, 50), (23, 50), (19, 50), (2, 1), (3, 1), (4, 1), (8, 1)),
        )
        receipt = dict(
            scope="four_actual_Ready_totems_positive_4227_component",
            full_phase_or_victory=False,
            injected_hp_states_resources=False,
            rng_search=False,
            small_spell=4780,
            placements=positions,
            boundaries=[],
            hits=[],
            threshold_sources=[],
            hammer_targets=[],
        )
        output = (
            ROOT
            / ".runtime/ultimate-scenes-20261021/fulmoon-four-native-totems-positive4227.json"
        )
        case = None
        try:
            with original_bootstrap_publication():
                (
                    fight,
                    characters,
                    monsters,
                    decks,
                    resources,
                    generations,
                    premise,
                ) = native_paid_party_fixture(
                    self.store,
                    scene,
                    (build,) * 6,
                    positions,
                    name_prefix="moon-four-totems",
                    encounter_layout=scene,
                )
            receipt["premise"] = premise
            case = PaidComponentRuntime(
                fight, characters, monsters, decks, map_id=1056, seed=0
            )
            children = {
                identity: row["authority"]["breed_id"]
                for identity, row in fight.native_summon_registrations.items()
                if identity in fight.actors
                and row["authority"]["breed_id"] in (3993, 3995, 3996, 3997)
            }
            self.assertCountEqual(children.values(), (3993, 3995, 3996, 3997))
            targets = tuple(sorted(children))
            for identity in targets:
                actor = fight.actors[identity]
                self.assertEqual((actor.hp, actor.max_hp), (5000, 5000))
                self.assertIn(
                    4226, {entry.reference for entry in actor.state_ledger.entries}
                )
                self.assertNotIn(
                    4227, {entry.reference for entry in actor.state_ledger.entries}
                )
            initial_ids = set(fight.actors)
            hammered = set()
            case.runtime.turn_started(arm_deadline=False)

            def marked(identity):
                return any(
                    entry.reference == 4227
                    for entry in case.fight.actors[identity].state_ledger.entries
                )

            for _ in range(64):
                current = case.fight
                receipt["boundaries"].append(
                    dict(
                        turn=current.turn_id,
                        table=getattr(current, "native_table_turn", None),
                        current=None if current.current is None else current.current.id,
                        totems={
                            identity: dict(
                                hp=current.actors[identity].hp, marked=marked(identity)
                            )
                            for identity in targets
                        },
                    )
                )
                if all(marked(identity) for identity in targets):
                    for identity in targets:
                        actor = current.actors[identity]
                        self.assertGreater(actor.hp, 0)
                        self.assertLessEqual(actor.hp * 100, actor.max_hp * 20)
                    self.assertEqual(set(current.actors), initial_ids)
                    self.assertEqual(len(hammered), 4)
                    self.assertTrue(receipt["hits"])
                    self.assertTrue(
                        set(targets)
                        <= {event["actor_id"] for event in receipt["threshold_sources"]}
                    )
                    receipt.update(
                        status="all_four_original_living_totems_earned_4227",
                        final_hp={
                            identity: current.actors[identity].hp
                            for identity in targets
                        },
                    )
                    return
                self.assertEqual(current.phase, "active")
                self.assertIsNotNone(current.current)
                identity = current.current.id
                if identity == -200:
                    if current.current.position == tuple(scene["source"]):
                        # Two paid native steps put all four original props in range9.
                        before = current.current.mp
                        case.npc_move(((0, 1, 0), (1, 1, 0)))
                        self.assertEqual(case.fight.actors[-200].mp, before - 2)
                    for target in (
                        candidate for candidate in targets if candidate not in hammered
                    ):
                        if (
                            len(
                                [
                                    row
                                    for row in case.payments
                                    if row.get("kind") == "npc_cast"
                                    and row.get("turn") == case.fight.turn_id
                                ]
                            )
                            >= 2
                        ):
                            break
                        # Native per-target/per-turn limits remain enforced by preparation.
                        event_start = len(case.fight.events)
                        row = case.npc_cast(5693, target)
                        row["turn"] = case.fight.turn_id
                        self.assertEqual(row["costs"]["ap"], 2)
                        self.assertEqual(row["after"]["ap"], row["before"]["ap"] - 2)
                        self.assertEqual(row["before"]["hp"], 5000)
                        self.assertGreater(row["after"]["hp"], 0)
                        self.assertLess(row["after"]["hp"], 5000)
                        # Native critical/block rolls may already cross20%.
                        # Preserve that earned result, rather than force1330HP.
                        self.assertEqual(
                            marked(target), row["after"]["hp"] * 100 <= 5000 * 20
                        )
                        receipt["threshold_sources"].extend(
                            event
                            for event in case.fight.events[event_start:]
                            if event.get("kind") == "state_applied"
                            and event.get("state_id") == 4227
                        )
                        hammered.add(target)
                        receipt["hammer_targets"].append(target)
                elif identity in characters and len(hammered) == 4:
                    # Let the boss finish both paid hammer turns before any
                    # player approach can legitimately occlude a later ray.
                    for _cast in range(4):
                        actor = case.fight.actors[identity]
                        if actor.ap < 2:
                            break
                        candidates = [
                            candidate
                            for candidate in targets
                            if candidate in hammered and not marked(candidate)
                        ]
                        if not candidates:
                            break
                        candidates.sort(
                            key=lambda target: (
                                abs(
                                    actor.position[0]
                                    - case.fight.actors[target].position[0]
                                )
                                + abs(
                                    actor.position[1]
                                    - case.fight.actors[target].position[1]
                                ),
                                target,
                            )
                        )
                        selected = None
                        for target in candidates:
                            path = case.cast_path(identity, target, 1, 3)
                            if path is None:
                                continue
                            if path:
                                case.player_move_prefix(identity, path)
                                path = case.cast_path(identity, target, 1, 3)
                            if path == ():
                                selected = target
                                break
                        if selected is None:
                            break
                        before = case.fight.actors[selected].hp
                        event_start = len(case.fight.events)
                        row = case.cast(identity, 4780, selected)
                        self.assertEqual(row["costs"]["ap"], 2)
                        self.assertEqual(row["after"]["ap"], row["before"]["ap"] - 2)
                        after = case.fight.actors[selected].hp
                        self.assertLess(after, before, row)
                        self.assertGreater(
                            after, 0, "Small native hit killed/reset a totem"
                        )
                        self.assertEqual(marked(selected), after * 100 <= 5000 * 20)
                        receipt["threshold_sources"].extend(
                            event
                            for event in case.fight.events[event_start:]
                            if event.get("kind") == "state_applied"
                            and event.get("state_id") == 4227
                        )
                        receipt["hits"].append(
                            dict(
                                actor=identity,
                                target=selected,
                                breed=children[selected],
                                before=before,
                                after=after,
                                marked=marked(selected),
                                costs=row["costs"],
                            )
                        )
                        self.assertLessEqual(len(receipt["hits"]), 64)
                case.advance()
            self.fail("Bounded four-totem producer sequence did not earn all4227")
        except Exception as error:
            receipt.update(
                status="failed", error_type=type(error).__name__, error=str(error)
            )
            raise
        finally:
            if case is not None:
                receipt["payments"] = case.payments
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
