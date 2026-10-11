"""Owned native effect areas, kept separate from the actor roster (Qs/Qq)."""
from wakfu_server import native_catalog as protocol_catalog
from .combat_state_ledger import StateLedger
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from .combat_effect_area_codec import area_application
from .combat_stat_handler import StatExecutionContext
from .combat_summon_initialization import registered_or_detached_actor
from .combat_npc_initialization import constructor_stat_context
from .combat_area_removal_masks import area_removal_masks
from .combat_area_contracts import AREA_CONTRACTS, SUPPORTED_AREA_CONTRACTS


@lru_cache(maxsize=1)
def native_effect_areas():
    return protocol_catalog.load(DATA_ROOT / "native-effect-areas.json")["areas"]


def remove_owned_hour_area(fight, uid, *, callbacks=None, removal_target_id=None):
    """Qs.b removes only the specified owned record; no lifecycle producer.

    faZ.baE collateral cleanup belongs to the distinct Qq.b owner callback,
    and is deliberately not implied by removal from the area manager.
    """
    areas = getattr(fight, "native_effect_areas", {})
    row = areas.get(uid)
    if row is None:
        return ()
    if (
        row.get("native_hour_contract") is not True
        and row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS
    ):
        raise ValueError("Unsupported native effect-area removal callbacks")
    if callbacks is None and any(row.get("child_effect_uids", {}).values()):
        raise ValueError("Owned area child cleanup provider required")
    retired = getattr(fight, "native_retired_area_managers", {})
    if uid in retired:
        raise ValueError("Duplicate retired native area manager")
    has_registered_obstacle = (
        row.get("native_area_contract") == "faW"
        and row.get("native_faw_constructor", {}).get("obstacle")
    ) or (
        row.get("native_area_contract") == "fbd"
        and row.get("native_wall_constructor", {}).get("obstacle")
    )
    if has_registered_obstacle:
        from .combat_qi_registry import NativeQIRegistry

        if not isinstance(getattr(fight, "native_qi_touched_cells", None), list):
            raise ValueError("Missing native QL touched-cell checkpoint")
        registry = NativeQIRegistry(
            getattr(fight, "native_qi_snapshot", None),
            getattr(fight, "native_qi_slots", None),
            touched_cells=getattr(fight, "native_qi_touched_cells", None),
            byte_topology=getattr(fight, "native_qi_byte_topology", None),
        )
        registry.remove(row.get("native_obstacle_id"), ("effect_area", uid))
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
        fight.native_qi_touched_cells = registry.serialized_cells()
        row["native_obstacle_id"] = -1
        row["native_obstacle_source"] = "QI.g(QK)"
    removed = areas.pop(uid)
    if removed.get("native_faw_constructor", {}).get("kind") == 4:
        from .combat_microbot_network import unregister_microbot

        unregister_microbot(fight, removed)
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import unregister_global_area

        unregister_global_area(fight, uid)
    # Qs.a(Qq,PV) unregisters before delivering event10011.
    if callbacks is not None:
        if removal_target_id is None:
            callbacks.removed(removed)
        else:
            callbacks.removed(removed, target_id=removal_target_id)
    ledger = removed.get("state_ledger")
    has_children = any(
        (
            entry.get("container_kind") == "effect_area"
            and entry.get("container_id") == uid
        )
        or entry.get("manager_id") == uid
        for entry in getattr(fight, "native_retained_records", {}).values()
    )
    if (ledger is not None and ledger.entries) or has_children:
        # Qf and owned Qe/PL identities remain actual objects after Qs unregisters
        # the area. Keep their ledger out of spatial queries and the fighter roster.
        retired = getattr(fight, "native_retired_area_managers", None)
        if retired is None:
            retired = {}
            fight.native_retired_area_managers = retired
        retired[uid] = removed
    return (removed,)


class NativeEffectAreaHandler:
    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        context,
        container,
        area_affiliation=None,
        area_obstacle_register=None,
        actor_authority=None,
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.container = context, container
        self.actor_authority = actor_authority
        self.area_affiliation = area_affiliation
        self.area_obstacle_register = area_obstacle_register
        self.on_created = None
        self.target_aura_construction = None
        self.target_aura_applied = None

    def __call__(self, effect, values, invocation):
        from .combat_delivery_owners import owner_catalog, native_owner_flags

        family = effect["effect_class"]
        row = owner_catalog()["effects"].get(str(family))
        if not isinstance(row, dict) or row.get("runner") not in (
            "eYQ",
            "eYS",
            "eYU",
            "eYJ",
            "eYW",
        ):
            raise ValueError("Missing native configured eYQ area runner")
        actor_delivery, cell_delivery = native_owner_flags(effect)
        if not cell_delivery or (
            invocation.target_id is not None and not actor_delivery
        ):
            raise ValueError("Native eYQ recipient violates configured owner flags")
        if (
            invocation.target_id is not None
            and invocation.target_id not in self.fight.actors
            and not constructor_stat_context(self.fight, invocation)
        ):
            from .combat_state_managers import registered_area_pv

            if registered_area_pv(self.fight, invocation.target_id) is None:
                raise ValueError("Unregistered native eYQ actor recipient")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native effect-area execution authority")
        if not ctx.executable:
            return False
        target_aura = row["runner"] == "eYJ"
        constructor = None
        if target_aura:
            from .combat_target_aura import NativeTargetAuraConstruction

            if not callable(self.target_aura_construction):
                raise ValueError("Missing native eYJ constructor producer")
            constructor = self.target_aura_construction(invocation)
            if not isinstance(constructor, NativeTargetAuraConstruction):
                raise ValueError("Unregistered native eYJ constructor")
        elif invocation.native_running_uid is not None:
            raise ValueError("Native retained area effect removal is unaudited")
        p = values["parameters"]
        if not p:
            raise ValueError("Missing native area reference")
        # eYS inherits eZR.n: C computes the reference, then eVt may
        # override that runner amount before area creation.
        from .combat_value_transfer import apply_context_value

        ref = (
            p[0]
            if target_aura
            else apply_context_value(
                p[0],
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        definition = native_effect_areas().get(str(ref))
        if (
            definition is None
            or definition["type"] not in AREA_CONTRACTS
            or type(definition.get("raw_bde")) is not int
            or (
                self.on_created is None
                and (
                    not definition.get("native_hour_contract")
                    or definition["effect_ids"]
                    or definition["entry_masks"]
                    or definition["exit_masks"]
                    or definition["native_shape_class"] != "anD"
                )
            )
        ):
            raise ValueError(
                "Native area callbacks or shape are unaudited: "
                f"reference={ref!r}, definition={definition!r}"
            )
        faw = None
        grade = None
        wall = None
        if target_aura and definition["type"] != "AURA":
            raise ValueError("Native eYJ requires actual faN prototype")
        level = (
            invocation.level
            if target_aura
            else (((p[1] + 32768) % 65536) - 32768 if len(p) > 1 else invocation.level)
        )
        if definition["type"] == "ENUTROF_DEPOSIT":
            from .combat_area_contracts import deposit_grade

            grade = deposit_grade(definition)
        if definition["type"] == "FAKE_FIGHTER":
            from .combat_fake_fighter import fake_fighter_constructor

            faw = fake_fighter_constructor(definition)
            if faw["obstacle"] and not callable(self.area_obstacle_register):
                raise ValueError("Missing native faW QI registration provider")
            if faw["obstacle"]:
                # Explicit producer preflight validates complete QK authority
                # before either area/effect UID; it must not reserve a slot.
                self.area_obstacle_register(self.fight, None, faw)
        if definition["type"] == "WALL":
            from .combat_wall_area import wall_constructor

            wall = wall_constructor(definition, level)
            if wall["obstacle"] and not callable(self.area_obstacle_register):
                raise ValueError("Missing native fbd wall QI registration provider")
            if wall["obstacle"]:
                self.area_obstacle_register(self.fight, None, wall)
        if definition["type"] == "GATE" and (
            definition.get("native_class") != "bcS"
            or definition.get("native_type_id") != 19
            or definition["effect_ids"]
            or definition["entry_masks"]
            or definition["exit_masks"]
        ):
            raise ValueError("Unaudited native faX gate callback/prototype contract")
        creator_id = invocation.caster_id
        if target_aura:
            if invocation.target_id not in self.fight.actors:
                raise ValueError(
                    "Native faN target anchor is not a registered fighter PV"
                )
            creator_id = invocation.target_id
        if row["runner"] == "eYS":
            from .combat_original_controller_area import (
                original_controller_area_creator,
            )

            creator_id = original_controller_area_creator(
                self.fight, invocation.caster_id, self.actor_authority
            )
        if faw is not None and faw["kind"] == 4:
            from .combat_microbot_network import preflight_microbot_owner
            from .combat_microbot_path import microbot_path_projection

            preflight_microbot_owner(self.fight, creator_id)
            microbot_path_projection(self.fight)
        affiliation = None
        if callable(self.area_affiliation):
            affiliation = self.area_affiliation(self.fight, creator_id)
            if type(affiliation) is not int or not -128 <= affiliation <= 127:
                raise ValueError("Missing native faV captured bcM affiliation")
        elif definition["type"] in ("GATE", "FAKE_FIGHTER"):
            raise ValueError("Missing native faX creation affiliation authority")
        removal_masks = area_removal_masks(definition)
        if removal_masks and self.on_created is None:
            raise ValueError("Native area removal masks require callback authority")
        keep = False if target_aura else len(p) > 2 and p[2] == 1
        if row["runner"] == "eYU":
            keep = True
        direction = (
            None if target_aura else (p[3] if len(p) > 3 and 0 <= p[3] <= 7 else None)
        )
        caster = registered_or_detached_actor(self.fight, invocation.caster_id)
        orientation_owner = self.fight.actors[creator_id] if target_aura else caster
        effective_direction = (
            direction
            if direction is not None
            else getattr(orientation_owner, "direction", 7)
        )
        if type(effective_direction) is not int or not 0 <= effective_direction <= 7:
            raise ValueError("Missing native area orientation")
        from .combat_effect_area_geometry import registered_area_cells

        geometry_reference = (
            tuple(invocation.cell)
            if orientation_owner is None
            else tuple(orientation_owner.position)
        )
        cells = registered_area_cells(
            definition,
            invocation.cell,
            effective_direction,
            reference=geometry_reference,
        )
        area_uid = constructor.area_uid if target_aura else self.allocate_uid()
        uid = constructor.runner_uid if target_aura else self.allocate_uid()
        owner, owner_id = self.container(invocation)
        if target_aura:
            from .combat_target_aura import target_aura_application

            packet = target_aura_application(
                self.fight.id,
                self.action_id,
                invocation=invocation,
                constructor=constructor,
                value=ref,
                timing_payload=ctx.timing_payload,
                owner=owner,
                owner_id=owner_id,
            )
        else:
            packet = area_application(
                self.fight.id,
                self.action_id,
                uid=uid,
                effect_class=family,
                execute_immediate=not ctx.retained,
                target_id=invocation.target_id,
                base_uid=invocation.base_uid,
                effect_reference=invocation.reference,
                area_reference=ref,
                area_uid=area_uid,
                level=level,
                keep_after=keep,
                direction=direction,
                caster_id=invocation.caster_id,
                cell=invocation.cell,
                timing_payload=ctx.timing_payload,
                container_type=owner["container_type"],
                container_id=owner_id,
                context_payload=None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        areas = getattr(self.fight, "native_effect_areas", None)
        if areas is None:
            areas = {}
            self.fight.native_effect_areas = areas
        if area_uid in areas:
            raise ValueError("Duplicate native area UID")
        areas[area_uid] = dict(
            uid=area_uid,
            reference=ref,
            level=level,
            cell=tuple(invocation.cell),
            owner_id=creator_id,
            # eYQ constructs fbm without M(byte); constructor bgW is -1.
            # A later actual QI registration may assign an obstacle slot.
            native_obstacle_id=-1,
            native_obstacle_source="fbm.constructor",
            direction=effective_direction,
            keep_after=keep,
            native_hour_contract=definition["type"] == "HOUR",
            native_area_contract=AREA_CONTRACTS[definition["type"]],
            # Fresh Qq construction initializes bhi=false. Qs unregistering
            # does not run Qq.b and must preserve this explicit authority.
            native_qq_bhi=False,
            native_qq_guard_source="Qq.constructor",
            native_type_id=definition["native_type_id"],
            native_removal_masks=tuple(sorted(removal_masks)),
            native_cells_xy=cells,
            native_geometry_reference=geometry_reference,
            native_geometry_reference_source="Qq.bcT.bcU_bcV_bcW",
            remaining_activations=definition["raw_bde"],
            native_running_effect_manager=(
                faw["running_effect_manager"]
                if faw is not None
                else wall["running_effect_manager"]
                if wall is not None
                else 12 in definition["native_area_properties"]
            ),
            child_effect_uids={},
            executing=False,
            effect_uid=uid,
            effect_class=family,
            target_id=invocation.target_id,
            effect_reference=invocation.reference,
        )
        if affiliation is not None:
            areas[area_uid]["native_fight_affiliation"] = affiliation
            areas[area_uid]["native_fight_affiliation_source"] = "faV.j(PV).bcM"
        if grade is not None:
            areas[area_uid]["native_deposit_grade"] = grade
            areas[area_uid]["native_deposit_grade_source"] = "faU.fTu.Qr_bdh0"
        if faw is not None:
            areas[area_uid]["native_faw_constructor"] = faw
            if faw["obstacle"]:
                slot = self.area_obstacle_register(self.fight, areas[area_uid], faw)
                if type(slot) is not int or not 0 <= slot <= 126:
                    raise ValueError("Native faW QI obstacle capacity unavailable")
                areas[area_uid]["native_obstacle_id"] = slot
                areas[area_uid]["native_obstacle_source"] = "QI.f(QK)"
            if faw["kind"] == 4:
                from .combat_microbot_network import register_microbot

                register_microbot(self.fight, areas[area_uid])
        if wall is not None:
            areas[area_uid]["native_wall_constructor"] = wall
            areas[area_uid]["native_wall_hp_current"] = wall["hp_initial"]
            areas[area_uid]["native_wall_hp_source"] = "fbd.PA.sgC.aYS"
            if wall["obstacle"]:
                slot = self.area_obstacle_register(self.fight, areas[area_uid], wall)
                if type(slot) is not int or not 0 <= slot <= 126:
                    raise ValueError("Native fbd wall QI obstacle capacity unavailable")
                areas[area_uid]["native_obstacle_id"] = slot
                areas[area_uid]["native_obstacle_source"] = "QI.f(QK)"
        if definition["type"] == "TRAP":
            from .combat_trap_area import install_trap_characteristics

            install_trap_characteristics(areas[area_uid], definition)
        if definition["type"] == "AURA":
            areas[area_uid]["native_anchor_id"] = creator_id
            areas[area_uid]["native_anchor_source"] = "faN.bgZ"
            from .combat_effect_area_geometry import refresh_area_geometry

            refresh_area_geometry(self.fight, areas[area_uid])
        if areas[area_uid]["native_running_effect_manager"]:
            areas[area_uid]["state_ledger"] = StateLedger(area_uid)
        if ctx.retained:
            owned = getattr(self.fight, "native_owned_area_effects", None)
            if owned is None:
                owned = {}
                self.fight.native_owned_area_effects = owned
            owned[uid] = dict(
                uid=uid,
                area_uid=area_uid,
                effect_class=family,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                state_uid=invocation.state_uid,
                payload=packet[1][18:].hex(),
                keep_after=keep,
                executed=True,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        if target_aura:
            if ctx.retained:
                if not callable(self.target_aura_applied):
                    raise ValueError("Missing native retained eYJ registration")
                self.target_aura_applied(effect, invocation, uid)
            self.packets.append(packet)
        if hasattr(self.fight, "native_global_pv_collections"):
            from .combat_global_pv_collections import register_global_area

            register_global_area(self.fight, area_uid)
        if not target_aura:
            self.packets.append(packet)
        if self.on_created is None and definition["effect_ids"]:
            raise ValueError("Native effect-area callback provider required")
        created_area = areas[
            area_uid
        ]  # Native oAP survives callbacks removing Qs membership.
        if self.on_created is not None:
            self.on_created(created_area)
        if row["runner"] == "eYW":
            from .combat_area_damage_snapshot import copy_area_damage_snapshot

            # Native eYW.c calls super.c (including creation callbacks) first.
            copy_area_damage_snapshot(
                created_area,
                definition,
                source_stats=getattr(caster, "effect_stats", None),
                container_type=owner.get("container_type"),
            )
        if row["runner"] == "eYU":
            from .combat_directional_area import directional_area_orientation

            final_direction = directional_area_orientation(
                caster.position, invocation.cell
            )
            areas[area_uid]["direction"] = final_direction
            areas[area_uid]["native_cells_xy"] = registered_area_cells(
                definition,
                invocation.cell,
                final_direction,
                reference=geometry_reference,
            )
        return True
