"""Opt-in original Spirit8497 consumer, independent of Jondo selection."""
from copy import deepcopy
from unittest.mock import patch


def run_component(endpoint=None):
    """Commit an owned8497 after actual Ready; never manufacture its gate."""
    from jondo_earned_scene_native_probe import (
        build_scene,
        _oracle,
        _advance_scene,
        _drain,
    )
    from wakfu_server.combat_npc_attack import npc_runtime_catalog
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server import combat_group_cells
    from wakfu_server import combat_cell_group
    from wakfu_ai.native.native_stats import NativeStats

    scene = build_scene("spirit")
    case = scene.case
    try:
        for _ in range(8):
            if case.fight.current is not None and case.fight.current.id == -7:
                break
            _advance_scene(scene)
        assert case.fight.current.id == -7, "Actual timeline did not reach Spirit"
        oracle = _oracle(scene)
        owned = oracle.owned_spells(case.fight)
        assert 8497 in owned, "Actual Spirit does not own original8497"
        effects = npc_runtime_catalog(imported=True).effects
        definitions = {
            reference: effects[str(reference)] for reference in (411047, 411049)
        }
        for effect in definitions.values():
            assert (effect["area_class"], effect["area_native"]) == (
                "anw",
                "cross-h1b1-g30d30",
            )
        areas = [
            deepcopy(row)
            for row in case.fight.native_effect_areas.values()
            if row.get("reference") == 2131
        ]
        area_facts = [
            dict(
                uid=row["uid"],
                reference=row["reference"],
                ownerId=row["owner_id"],
                cell=list(row["cell"]),
                cells=[list(cell) for cell in row["native_cells_xy"]],
                contract=row.get("native_area_contract"),
            )
            for row in areas
        ]
        actual_area_cells = {
            tuple(cell) for row in areas for cell in row["native_cells_xy"]
        }
        occupied = {
            tuple(cell)
            for actor in case.fight.actors.values()
            if actor.hp > 0
            for cell in footprint(actor.position, actor.physical_radius)
        }
        aims = []
        for actor in case.fight.actors.values():
            if actor.id == -7 or actor.hp <= 0:
                continue
            cells = combat_group_cells.group_cells(
                case.fight, definitions[411047], actor.position, caster_id=-7
            )
            # These are observed geometric gate candidates. The actual native
            # criterion remains responsible for free-cell and LOS authority.
            gate = [
                cell
                for cell in cells
                if cell[:2] in actual_area_cells and cell[:2] not in occupied
            ]
            aims.append(
                dict(
                    targetId=actor.id,
                    target=list(actor.position),
                    gateCells=[list(cell) for cell in gate],
                )
            )
        aims.sort(
            key=lambda row: (
                row["targetId"] != scene.identity,
                -len(row["gateCells"]),
                row["targetId"],
            )
        )
        attempts, observed, populations, costs, accepted_casts = [], [], [], [], []
        accepted = None
        original = combat_group_cells.ordered_offsets
        original_population = combat_cell_group.native_cell_group_population
        original_cast = type(oracle).cast

        def observe(effect, **kwargs):
            offsets = original(effect, **kwargs)
            if (effect.get("area_class"), effect.get("area_native")) == (
                "anw",
                "cross-h1b1-g30d30",
            ):
                observed.append(
                    dict(
                        shape=effect["area_native"],
                        count=len(offsets),
                        first=list(offsets[0]),
                        last=list(offsets[-1]),
                    )
                )
            return offsets

        def observe_population(fight, effect, values, invocation):
            cells = original_population(fight, effect, values, invocation)
            if invocation.reference in definitions:
                populations.append(
                    dict(
                        reference=invocation.reference,
                        cellCount=len(cells),
                        casterId=invocation.caster_id,
                        targetId=invocation.target_id,
                        anchor=None
                        if invocation.cell is None
                        else list(invocation.cell),
                    )
                )
            return cells

        def observe_cast(owner, runtime, action, **kwargs):
            transaction = original_cast(owner, runtime, action, **kwargs)
            costs.append(deepcopy(transaction.plan.get("costs")))
            return transaction

        stats = NativeStats(
            characters=case.characters,
            monsters=case.monsters,
            fight_id=case.fight.id,
            map_id=1134,
        )
        for aim in aims[:3]:
            action = dict(
                type="cast",
                spellId=8497,
                level=owned[8497],
                targetId=aim["targetId"],
                target=aim["target"],
            )
            before = dict(
                ap=case.fight.actors[-7].ap,
                mp=case.fight.actors[-7].mp,
                wp=case.fight.actors[-7].effect_stats.get(4),
                areas=sorted(case.fight.native_effect_areas),
            )
            start = len(observed)
            population_start, cost_start = len(populations), len(costs)
            try:
                # eYk imports ordered_offsets into its own module namespace.
                # Observe that exact callable without changing its result.
                with patch.object(
                    combat_group_cells, "ordered_offsets", observe
                ), patch.object(
                    combat_cell_group, "ordered_offsets", observe
                ), patch.object(
                    combat_cell_group,
                    "native_cell_group_population",
                    observe_population,
                ), patch.object(
                    type(oracle), "cast", observe_cast
                ):
                    packets = oracle.commit(action, stats_serializer=stats)
                    _drain(case)
                accepted = dict(
                    action=action,
                    before=before,
                    after=dict(
                        ap=case.fight.actors[-7].ap,
                        mp=case.fight.actors[-7].mp,
                        wp=case.fight.actors[-7].effect_stats.get(4),
                        areas=sorted(case.fight.native_effect_areas),
                    ),
                    packetCount=len(packets),
                    geometricGateCells=aim["gateCells"],
                    nativeCosts=costs[cost_start:],
                    observedCellPopulations=populations[population_start:],
                    observedConsumerCalls=observed[start:],
                )
                accepted_casts.append(accepted)
                if any(row["count"] == 63 for row in accepted["observedConsumerCalls"]):
                    break
            except (ValueError, KeyError) as error:
                attempts.append(
                    dict(
                        action=action,
                        error=type(error).__name__,
                        detail=str(error),
                        observedConsumerCalls=observed[start:],
                    )
                )
        consumed = accepted is not None and any(
            row["count"] == 63 for row in accepted["observedConsumerCalls"]
        )
        return dict(
            kind="actual_spirit_8497_native_consumer",
            passed=consumed,
            acceptedOriginalCast=accepted,
            rejectedAttempts=attempts,
            acceptedOriginalCasts=accepted_casts,
            actual2131Areas=area_facts,
            hasActual2131Gate=bool(areas),
            originalGroupReferences=[411047, 411049],
            readyPackets=scene.readyPackets,
            setupTimings=scene.setupTimings,
            premiseFailure=None
            if accepted is not None
            else "No bounded actual aim accepted",
            scope="Engine consumer only: owned8497 after genuine Ready; observed original63-cell enumeration. Geometric gate facts do not certify LOS or child effects. No Jondo choice, fabricated areas/states/HP, or encounter victory claim.",
        )
    finally:
        scene.database.doCleanups()
