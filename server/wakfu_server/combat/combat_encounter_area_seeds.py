"""Explicit Wakemu encounter setup through native typed area constructors."""
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json


@dataclass(frozen=True)
class NativeEncounterAreaSeed:
    area_reference: int
    effect_reference: int
    level: int
    cell: tuple
    program_reference: int | None = None
    state_reference: int | None = None
    state_effect_reference: int | None = None

    def plain(self):
        if (
            any(
                type(value) is not int or value <= 0
                for value in (self.area_reference, self.effect_reference, self.level)
            )
            or not 1 <= self.level <= 32767
            or type(self.cell) is not tuple
            or len(self.cell) != 3
            or any(type(value) is not int for value in self.cell)
        ):
            raise ValueError("Malformed native encounter area seed")
        result = dict(
            area_reference=self.area_reference,
            effect_reference=self.effect_reference,
            level=self.level,
            cell=list(self.cell),
        )
        program = (
            self.program_reference,
            self.state_reference,
            self.state_effect_reference,
        )
        if any(value is not None for value in program):
            if any(type(value) is not int or value <= 0 for value in program):
                raise ValueError("Incomplete native encounter seed program")
            result.update(
                program_reference=self.program_reference,
                state_reference=self.state_reference,
                state_effect_reference=self.state_effect_reference,
            )
        return result


def install_native_area_seeds(dispatcher, *, policy, creator_id, seeds, provenance):
    """Install once inside the caller's unpublished initialization preview.

    Native lifecycle/removal and packets remain owned by this exact dispatcher.
    The caller must discard the whole preview and outbox on any exception.
    """
    fight = dispatcher.native_retention.fight
    from .combat_definitions import effect_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_effects import _integer
    from .combat_obstacle_condition import footprint

    if (
        type(policy) is not str
        or not policy
        or type(creator_id) is not int
        or creator_id == 0
        or not isinstance(provenance, dict)
        or type(seeds) is not tuple
        or not seeds
        or any(type(seed) is not NativeEncounterAreaSeed for seed in seeds)
    ):
        raise ValueError("Missing typed native encounter area setup")
    plan = [seed.plain() for seed in seeds]
    payload = dict(
        policy=policy,
        creator_id=creator_id,
        seeds=plan,
        provenance=deepcopy(provenance),
    )
    checksum = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    previous = getattr(fight, "native_encounter_area_setups", {}).get(policy)
    if previous is not None:
        if (
            not isinstance(previous, dict)
            or previous.get("schema") != "wakemu-native-area-setup-v1"
            or previous.get("sha256") != checksum
            or previous.get("plan") != payload
        ):
            raise ValueError("Encounter setup differs from its committed initial plan")
        return False
    creator = fight.actors.get(creator_id)
    if (
        fight.phase != "active"
        or creator is None
        or creator.hp <= 0
        or getattr(fight, "native_start_event_delivered", False)
    ):
        raise ValueError("Native encounter seeds require a live pre-start creator")
    cells = {tuple(seed.cell) for seed in seeds}
    columns = {(cell[0], cell[1]) for cell in cells}
    if (
        len(cells) != len(seeds)
        or len(columns) != len(seeds)
        or not cells <= fight.walkable
    ):
        raise ValueError("Native encounter seed cells are duplicate or outside terrain")
    occupied = {
        point
        for actor in fight.actors.values()
        if actor.hp > 0
        for point in footprint(actor.position, actor.physical_radius)
    }
    if columns & occupied:
        raise ValueError("Native encounter seeds overlap actual fighter footprints")
    existing = getattr(fight, "native_effect_areas", {})
    if any(tuple(row["cell"]) in cells for row in existing.values()):
        raise ValueError("Native encounter seed cell already contains an area")
    for seed in seeds:
        effect = dispatcher.effects.get(str(seed.effect_reference))
        if not isinstance(effect, dict) and not hasattr(effect, "get"):
            raise ValueError("Native encounter seed creator definition is absent")
        values = effect_profile(effect, seed.level)
        parameters = values.get("parameters", ())
        if (
            effect.get("effect_class") != 315
            or effect.get("criteria")
            or len(parameters) < 3
            or tuple(parameters[:3]) != (seed.area_reference, seed.level, 1)
            or effect.get("children")
        ):
            raise ValueError("Native encounter seed creator contract changed")
        if seed.program_reference is not None:
            parent = dispatcher.effects.get(str(seed.program_reference))
            companion = dispatcher.effects.get(str(seed.state_effect_reference))
            if (
                parent is None
                or companion is None
                or parent.get("effect_class") != 349
                or tuple(parent.get("children", ()))
                != (seed.effect_reference, seed.state_effect_reference)
                or companion.get("effect_class") != 304
                or companion.get("criteria")
                or companion.get("children")
            ):
                raise ValueError("Native encounter seed ordered program changed")
            state_parameters = effect_profile(companion, seed.level).get(
                "parameters", ()
            )
            if len(state_parameters) < 2 or tuple(state_parameters[:2]) != (
                seed.state_reference,
                seed.level,
            ):
                raise ValueError("Native encounter seed state program changed")
    preview = fight
    created = []
    with preview.effect_resolution():
        for seed in seeds:
            before = set(getattr(preview, "native_effect_areas", {}))
            # The policy has selected a real free native cell once. All native
            # constructor, Qq registration and callback work stays in315.
            if seed.program_reference is None:
                applied = dispatcher.execute(
                    EffectInvocation(
                        seed.effect_reference,
                        seed.level,
                        creator_id,
                        None,
                        seed.cell,
                        native_preselected_target=True,
                        native_target_cell_argument=True,
                        native_retained_container={"present": False},
                    )
                )
            else:
                # Only the reconstructed candidate population is supplied by
                # scene policy. Native349 still evaluates its original criterion
                # and executes its ordered children with native retained context.
                # In particular,304 selects afresh after315 registers the Qq.
                original_cells = dispatcher.group_cells

                def selected_population(effect, invocation):
                    if (
                        invocation.reference == seed.program_reference
                        and invocation.caster_id == creator_id
                        and tuple(invocation.cell) == seed.cell
                    ):
                        return (seed.cell,)
                    return original_cells(effect, invocation)

                dispatcher.group_cells = selected_population
                try:
                    root = EffectInvocation(
                        seed.program_reference,
                        seed.level,
                        creator_id,
                        None,
                        seed.cell,
                        # Native flag16 transmits SP/PL, not invocation.level.
                        # The manifest supplies SP, never a fictitious container.
                        native_context_hex=_integer(4, seed.level).hex(),
                        native_target_cell_argument=True,
                        native_retained_container={"present": False},
                    )
                    parent = dispatcher.effects[str(seed.program_reference)]
                    level, context = dispatcher.native_retention.child_level_context(
                        parent,
                        effect_profile(parent, seed.level),
                        root,
                        default_level=seed.level,
                    )
                    if level != seed.level:
                        raise ValueError(
                            "Native seed program did not transmit its initial level"
                        )
                    # Construct the complete original eVt, including default
                    # probability flags, through the existing native factory.
                    applied = dispatcher.execute(
                        replace(root, native_context_hex=context.hex())
                    )
                finally:
                    dispatcher.group_cells = original_cells
            added = set(preview.native_effect_areas) - before
            if not applied or len(added) != 1:
                raise ValueError("Native encounter constructor did not create one area")
            uid = next(iter(added))
            area = preview.native_effect_areas[uid]
            if (
                area["reference"] != seed.area_reference
                or tuple(area["cell"]) != seed.cell
            ):
                raise ValueError(
                    "Native encounter constructor changed selected area identity"
                )
            if seed.program_reference is not None:
                ledger = area.get("state_ledger")
                entries = () if ledger is None else ledger.entries
                if not any(
                    entry.reference == seed.state_reference
                    and entry.level == seed.level
                    for entry in entries
                ):
                    raise ValueError(
                        "Native seed program did not initialize its created Qq state: "
                        f"program={seed.program_reference}, area={seed.area_reference}, "
                        f"uid={uid}, state={seed.state_reference}, level={seed.level}, "
                        f"actual={[(entry.reference, entry.level) for entry in entries]}"
                    )
            created.append(uid)
    receipts = dict(getattr(preview, "native_encounter_area_setups", {}))
    receipts[policy] = dict(
        schema="wakemu-native-area-setup-v1",
        sha256=checksum,
        plan=payload,
        created_area_uids=created,
    )
    preview.native_encounter_area_setups = receipts
    return True


def initialize_native_area_seeds(
    fight, runtime_factory, *, policy, creator_id, seeds, provenance
):
    """Stage a complete atomic seed transaction without mutating its source."""
    preview = deepcopy(fight)
    dispatcher, packets = runtime_factory(
        preview,
        {"native_retained_container": {"present": False}},
    )
    install_native_area_seeds(
        dispatcher,
        policy=policy,
        creator_id=creator_id,
        seeds=seeds,
        provenance=provenance,
    )
    return preview, tuple(packets)
