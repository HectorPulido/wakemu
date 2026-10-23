"""Actual owned fight producers for fcj and ePI; no effect preparation."""
from wakfu_server import native_catalog as protocol_catalog
from contextlib import contextmanager
from functools import lru_cache
import json
from types import SimpleNamespace

from wakfu_server.paths import DATA_ROOT
from .combat_conditions import UnknownCondition, evaluate_condition
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS
from .combat_pointer_qi_registry import (
    registered_slot,
    registered_terrain,
    registered_population,
)
from .combat_casting_eligibility import (
    NativeCastingFlags,
    native_casting_distance,
    native_casting_eligibility,
    native_use_gate_effect,
    native_pv_cell_distance,
)


@lru_cache(maxsize=1)
def casting_root_catalog():
    data = protocol_catalog.load(DATA_ROOT / "native-class-casting-roots.json")
    if data.get("schema") != "native-class-casting-roots-v1":
        raise ValueError("Missing native fKX casting metadata provenance")
    from wakfu_server.combat_scoped_casting_roots import (
        morph_casting_roots,
        captured_casting_roots,
        merge_casting_roots,
    )

    from .combat_common_spell_catalog import casting_roots as common_casting_roots

    return merge_casting_roots(
        merge_casting_roots(
            merge_casting_roots(data, morph_casting_roots()), captured_casting_roots()
        ),
        common_casting_roots(),
    )


class NativeOwnedCastingContext:
    """One caster/container/cell snapshot, with lazy authoritative QI queries."""

    def __init__(self, adapter, fight, plan, invocation, condition, rule):
        self.adapter, self.fight, self.plan = adapter, fight, plan
        self.invocation, self.condition, self.rule = invocation, condition, rule
        self.source = fight.actors.get(invocation.caster_id)
        if self.source is None:
            raise UnknownCondition("Missing actual native casting caster")
        self.cell = tuple(invocation.cell)
        self.target = None
        self._registry = None
        self.normal_mode = False
        self._portal = None
        self.los_diagnostic = None

    def registry(self):
        if self._registry is None:
            from .combat_qi_fight import current_registry

            self._registry = current_registry(self.fight)
        return self._registry

    def qi(self):
        return self.registry().snapshot()

    def container_present(self):
        return True  # Actual fyG was validated by the calling producer.

    def current_turn_matches(self):
        return (
            self.fight.phase == "active"
            and self.fight.current is not None
            and self.fight.current.id == self.source.id
        )

    def effective_range(self):
        return self.rule["minimum"], self.rule["maximum"]

    def cell_and_qi_present(self):
        # The cell is actual aBn. Missing serialization is unknown, not null QI.
        if not isinstance(getattr(self.fight, "native_qi_snapshot", None), dict):
            raise UnknownCondition("Missing actual native casting QI")
        return True

    def resolve_target_fighter(self):
        registry = self.registry()
        self.target = None
        for slot in registry.ordered_U(*self.cell[:2]):
            row = registered_slot(registry, slot)
            if row is None or row["identity"][0] != "actor":
                continue
            actor = self.fight.actors[row["identity"][1]]
            native_fighter = self.adapter._actor(self.fight, actor).targeting.get(
                "is_eGj"
            )
            if type(native_fighter) is not bool:
                raise UnknownCondition(
                    "Registered casting target is not proven native type"
                )
            if native_fighter:
                self.target = actor
                return

    def range_distance(self):
        return native_casting_distance(self.source.position[:2], self.cell[:2])

    def range_accepts(self, minimum, maximum, allow_self):
        if self.normal_mode and self.normal_area_override():
            return True
        if self.normal_mode:
            portal = self.portal_evaluation()
            if portal is not None and portal.has_entry and portal.range_accepts:
                return True
        distance = self.range_distance()
        return minimum <= distance <= maximum or distance == 0 and allow_self

    def ordinary_range_accepts(self):
        distance = self.range_distance()
        return (
            self.rule["minimum"] <= distance <= self.rule["maximum"]
            or distance == 0
            and self.rule["allow_self"]
        )

    def portal_evaluation(self):
        metadata = casting_root_catalog()["normal_casting_overrides"]
        if metadata["categories"]["txX"] not in self.rule["categories"]:
            return None
        if self._portal is not None:
            return self._portal
        from .combat_global_pv_collections import global_pv_iterator
        from .combat_portal_casting import evaluate_portal_casting

        tuple(global_pv_iterator(self.fight, caster_id=None, caster_only=False))

        def selected(cell):
            if cell is not None and tuple(cell) == self.cell:
                return self.rule
            actual = SimpleNamespace(
                caster_id=self.source.id,
                target_id=None,
                cell=None if cell is None else tuple(cell),
            )
            conditions = cast_cell_condition(
                self.adapter, self.fight, self.plan, self.source.id, cell
            )
            from .combat_native_spell_casting import definition

            return definition(
                self.plan["spell_id"],
                self.plan["evaluation_level"],
                conditions,
                None,
                calculate_costs=False,
            )

        def visible(source, target):
            from .combat_casting_los import native_casting_ray

            instance = self.adapter._actor(self.fight, self.source).native_instance_id
            # fed.i invokes the raw coordinate overload with actual caster
            # height and target offset6, without QI.d/bdM source exclusion.
            return native_casting_ray(
                self.fight,
                self.adapter.actor_authority,
                instance,
                source,
                target,
                source_height=self.source.native_los_height,
                target_height=0,
                ignored_slots=getattr(
                    self.fight, "native_qi_visibility_ignored_slots", None
                ),
            )

        affiliation = getattr(self.source, "native_fight_affiliation", self.source.team)
        self._portal = evaluate_portal_casting(
            tuple(self.fight.native_effect_areas.values()),
            caster_cell=self.source.position,
            caster_affiliation=affiliation,
            target_cell=self.cell,
            minimum=self.rule["minimum"],
            maximum=self.rule["maximum"],
            same_cell_category=metadata["categories"]["tya"] in self.rule["categories"],
            cell_occupants=lambda x, y: frozenset(
                registered_population(self.registry())[1](x, y)
            ),
            los_required=lambda: selected(None)["line_of_sight"],
            linear_required=lambda cell: selected(cell)["linear"],
            visible=visible,
        )
        return self._portal

    def normal_area_override(self):
        """fcO b/c: selected own GATE affiliation or direct-owner AREA type1."""
        from .combat_effect_area_geometry import contains_area_cell

        metadata = casting_root_catalog()["normal_casting_overrides"]
        categories = set(self.rule["categories"])
        if not categories & {
            metadata["categories"]["txZ"],
            metadata["categories"]["tyb"],
        }:
            return False
        from .combat_global_pv_collections import global_pv_iterator

        # This validates the complete Qs population without fabricating an
        # absent area from an incomplete restored fight.
        tuple(global_pv_iterator(self.fight, caster_id=None, caster_only=False))
        source_affiliation = getattr(
            self.source, "native_fight_affiliation", self.source.team
        )
        found = False
        for row in self.fight.native_effect_areas.values():
            if not contains_area_cell(row, self.cell):
                continue
            kind = row.get("native_type_id")
            if type(kind) is not int:
                raise UnknownCondition("Missing actual normal-casting Qs area type")
            if (
                metadata["categories"]["txZ"] in categories
                and kind == metadata["area_types"]["rNX"]
            ):
                affiliation = row.get("native_fight_affiliation")
                if type(affiliation) is not int:
                    raise UnknownCondition("Missing captured casting GATE affiliation")
                if affiliation == source_affiliation:
                    found = True
            if (
                metadata["categories"]["tyb"] in categories
                and kind == metadata["area_types"]["rNI"]
            ):
                if "owner_id" not in row:
                    raise UnknownCondition("Missing actual casting area direct owner")
                if row["owner_id"] == self.source.id:
                    found = True
        return found

    def normal_alignment(self):
        """fcO static alignment first, then exact fee fallback conjunction."""
        portal = self.portal_evaluation()  # fee.a precedes fcO static validation.
        ordinary = self.alignment(path_option=self.rule["path_option"])
        if not self.rule["linear"] and not self.rule["diagonal"]:
            return True
        if portal is None or not portal.has_entry:
            return ordinary
        if portal.alignment_accepts:
            return True
        return self.ordinary_range_accepts() and ordinary

    def qi_in_bounds(self):
        return registered_terrain(self.registry()).aK(*self.cell[:2])

    def qi_p(self):
        return registered_terrain(self.registry()).P(*self.cell[:2])

    def qi_r(self):
        return registered_terrain(self.registry()).R(*self.cell[:2])

    def qi_j(self):
        from .combat_qi_surface_catalog import native_qi_surfaces

        metadata = self.adapter._actor(self.fight, self.source)
        return native_qi_surfaces(metadata.native_instance_id).j(
            registered_terrain(self.registry()), *self.cell
        )

    def criterion_present(self):
        value = self.rule["cast_criterion_native_present"]
        if type(value) is not bool:
            raise UnknownCondition("Missing actual native gtP parse presence")
        return value

    def criterion_cell(self):
        raw = self.rule["cast_criterion_raw"]
        if not isinstance(raw, str) or not raw:
            raise UnknownCondition("Missing native casting criterion text")
        context = cast_cell_condition(
            self.adapter, self.fight, self.plan, self.source.id, self.cell
        )
        return evaluate_condition(raw, context)

    def criterion_objects(self):
        if not self.criterion_present():
            return ()  # The materialized native list has no consumer in this branch.
        # fcb.bak also contains non-QK PVs. QI completeness alone cannot prove
        # this population or fcd's IN_PLAY/OFF_PLAY/Qs/permanent-PV filtering.
        from .combat_global_pv_collections import global_pv_iterator

        order = global_pv_iterator(self.fight, caster_id=None, caster_only=False)
        candidates = []
        for identity in order:
            if identity in self.fight.actors:
                actor = self.fight.actors.get(identity)
                if (
                    native_pv_cell_distance(
                        actor.position, actor.physical_radius, self.cell
                    )
                    == 0
                ):
                    candidates.append(("actor", identity))
            elif identity in self.fight.native_effect_areas:
                row = self.fight.native_effect_areas.get(identity)
                # fcb.b uses PV.bcL, not the effect-area activation geometry.
                # All current registered Qq PV creation contracts have bcL=0.
                if native_pv_cell_distance(row["cell"], 0, self.cell) == 0:
                    candidates.append(("effect_area", identity))
            else:
                raise UnknownCondition("Unsupported actual native casting PV kind")
        return tuple(candidates)

    def criterion_fighter_exempt(self, obj):
        kind, identity = obj
        if kind != "actor":
            return False
        metadata = self.adapter._actor(self.fight, self.fight.actors[identity])
        value = metadata.targeting.get("fqx")
        if type(value) is not bool:
            raise UnknownCondition("Missing actual native eGj.fqx casting exemption")
        return value

    def criterion_object(self, obj):
        kind, identity = obj
        context = self.adapter.condition(
            self.fight,
            self.plan,
            None,
            SimpleNamespace(
                caster_id=self.source.id, target_id=identity, cell=self.cell
            ),
        )
        return evaluate_condition(self.rule["cast_criterion_raw"], context)

    def roots(self):
        return self.rule["roots"]

    def root_record(self, root):
        record = casting_root_catalog()["roots"].get(str(root))
        if record is None:
            from wakfu_server.native_casting_roots import supplemental_root

            record = supplemental_root(root, spell_reference=self.plan["spell_id"])
        if not isinstance(record, dict):
            raise UnknownCondition("Missing native casting root fKX/aZF metadata")
        return record

    def root_has_shape(self, root):
        record = self.root_record(root)
        if "native_casting_collision_area" not in record:
            raise UnknownCondition("Missing native casting fKX null presence")
        return record["native_casting_collision_area"] is not None

    def root_has_selector(self, root):
        return self.root_record(root)["native_selector_present"]

    def root_collision_clear(self, root):
        from .combat_effect_targets import area_offsets

        area = self.root_record(root)["native_casting_collision_area"]
        offsets = area_offsets(
            area,
            origin=self.cell,
            reference=self.source.position,
            direction=self.source.direction,
        )
        registry = self.registry()
        qi, occupants = registered_population(registry)
        for dx, dy in offsets:
            from .combat_casting_range import int32

            x, y = int32(self.cell[0] + dx), int32(self.cell[1] + dy)
            # QI.V is non-null iff its first QL byte resolves an actual QK;
            # current_registry proves all indexed bytes resolve a live slot.
            if not qi.R(x, y) or occupants(x, y):
                return False
        return True

    def qi_g(self):
        registry = self.registry()
        qi, occupants = registered_population(registry)
        if not qi.aK(*self.cell[:2]) or qi.Z(*self.cell[:2]):
            return True
        override = getattr(self.fight, "native_qi_movement_override", None)
        ignored = getattr(self.fight, "native_qi_ignored_slots", None)
        if type(override) is not bool or not isinstance(ignored, (list, tuple)):
            raise UnknownCondition("Missing actual native QI.g override/exclusions")
        if override:
            return False
        return any(
            slot not in ignored and registered_slot(registry, slot)["movement_blocking"]
            for slot in occupants(*self.cell[:2])
        )

    def target_fighter_present(self):
        return self.target is not None

    def properties(self, actor):
        query = getattr(self.adapter.actor_authority, "properties", None)
        values = (
            query(self.fight, actor)
            if callable(query)
            else getattr(actor, "native_fight_properties", None)
        )
        if not isinstance(values, (tuple, list, set, frozenset)):
            raise UnknownCondition("Missing actual native casting fight properties")
        return frozenset(values)

    def target_sd_r_other(self):
        number = casting_root_catalog()["fight_properties"]["sdR"]
        return (
            number in self.properties(self.target) and self.target.id != self.source.id
        )

    def caster_sd_g_lower_level(self):
        number = casting_root_catalog()["fight_properties"]["sdG"]
        return (
            number in self.properties(self.source)
            and self.source.effective_level < self.target.effective_level
        )

    def root_selector_accepts(self, root):
        from .combat_effect_targets import (
            native_selector_policy,
            target_relation,
            _native_target_valid,
        )

        effect = self.root_record(root)
        if "native_target_selector" not in effect:
            raise UnknownCondition("Missing native casting root selector definition")
        policy = native_selector_policy(effect)
        contexts = {}
        actors = []
        for actor in (self.source, self.target):
            metadata = self.adapter._actor(self.fight, actor)
            contexts[actor.id] = metadata.targeting
            affiliation = getattr(actor, "native_fight_affiliation", actor.team)
            actors.append(SimpleNamespace(id=actor.id, team=affiliation))
        caster, target = actors
        if target_relation(caster, target) not in policy["relations"]:
            return False
        return _native_target_valid(
            effect["native_target_selector"]["mask"],
            caster,
            target,
            contexts,
            include_fah=False,
        )

    def native_los(self):
        from .combat_casting_los import native_casting_los

        if self.normal_mode and self.normal_area_override():
            return True
        if self.normal_mode:
            portal = self.portal_evaluation()
            if portal is not None and portal.has_entry:
                if portal.los_accepts:
                    return True
                if not self.ordinary_range_accepts() or not self.alignment(
                    path_option=False
                ):
                    return False
        try:
            self.los_diagnostic = {}
            return native_casting_los(
                self.fight,
                self.adapter.actor_authority,
                self.source.id,
                self.cell,
                self.target,
                diagnostic=self.los_diagnostic,
            )
        finally:
            # Actual fcr.a calls QI.bdM even when its ray operation fails.
            self.fight.native_qi_visibility_ignored_slots = []

    def alignment(self, *, path_option=False):
        from .combat_casting_alignment import native_casting_alignment

        def path_query(option):
            from .combat_sn_path import NativeSnColumns, NativeSnPathAuthority

            metadata = self.adapter._actor(self.fight, self.source)
            columns = NativeSnColumns.from_published(metadata.native_instance_id)
            target = self.target

            @contextmanager
            def exclusion():
                # Native QI.b temporarily adds the target slot to biN. Sn with
                # a QI environment consumes QI.Z masks, not QI.g slot blockers.
                slot = target.native_obstacle_id
                from .combat_pointer_qi_registry import PointerRegistryCompatibility

                registry = self.registry()
                if isinstance(registry, PointerRegistryCompatibility):
                    registry.validate_exclusion_target(target)
                elif registered_slot(registry, slot)["identity"] != [
                    "actor",
                    target.id,
                ]:
                    raise UnknownCondition("Missing actual Sn target QK registration")
                ignored = getattr(self.fight, "native_qi_ignored_slots", None)
                if not isinstance(ignored, list):
                    raise UnknownCondition("Missing actual Sn QI.biN population")
                self.fight.native_qi_ignored_slots = list(
                    dict.fromkeys(ignored + [slot])
                )
                yield

            authority = NativeSnPathAuthority(
                source=getattr(self.source, "native_physical_position", None),
                target=self.cell,
                height=self.source.native_los_height,
                radius=self.source.physical_radius,
                jump=getattr(self.source, "native_jump_height", None),
                physical_column=columns.column,
                qi_z=registered_terrain(self.registry()).Z,
                is_qi=True,
                target_obstacle_present=target is not None,
                target_exclusion=exclusion if target is not None else None,
            )
            try:
                return authority(option)
            finally:
                # Native fcj.a calls QI.bdK after Sn, clearing biN entirely.
                self.fight.native_qi_ignored_slots = []

        return native_casting_alignment(
            self.source.position,
            self.cell,
            linear=self.rule["linear"],
            diagonal=self.rule["diagonal"],
            linear_path=self.rule["linear_path"],
            path_option=path_option,
            path_query=path_query,
        )

    def eligibility(self, *, trace=None):
        flags = NativeCastingFlags(
            line_of_sight=self.rule["line_of_sight"],
            free_cell=self.rule["free_cell"],
            forbid_qi_p=self.rule["forbid_QI_P"],
            allow_self=self.rule["allow_self"],
        )
        result = native_casting_eligibility(self, flags, trace=trace)
        if trace is not None and self.los_diagnostic is not None:
            trace.append(dict(stage="native_los_detail", value=self.los_diagnostic))
        return result


def use_gate_effect(adapter, fight, plan, effect, invocation, *, trigger_source=None):
    """ePI's real runner/container prerequisites, then both casting decisions."""
    if effect is None:
        return False  # Actual pre-cast fyG context is not a running eZR.
    if trigger_source is None and invocation.state_uid is not None:
        return False  # Actual running container is fyW, not fyG.
    direct = (
        trigger_source["casting_container"]
        if trigger_source is not None
        else invocation.native_retained_container
        or plan.get("native_retained_container")
    )
    if direct is not None:
        if type(direct.get("present")) is not bool:
            raise UnknownCondition("Missing native UseGateEffect container presence")
        if not direct["present"]:
            return False
        if type(direct.get("is_spell")) is not bool:
            raise UnknownCondition("Missing native UseGateEffect fyG type")
        if not direct["is_spell"]:
            return False
        reference, level = direct.get("spell_id"), direct.get("level")
        if type(reference) is not int:
            raise UnknownCondition("Missing actual native fyG spell reference")
    else:
        reference, level = plan.get("spell_id"), plan.get("evaluation_level")
    source = fight.actors.get(invocation.caster_id)
    if source is None:
        return False
    metadata = adapter._actor(fight, source)
    if metadata.targeting.get("is_eGj") is False:
        return False
    if metadata.targeting.get("is_eGj") is not True:
        raise UnknownCondition("Missing native UseGateEffect caster type")
    if (
        trigger_source is None
        and invocation.target_id is not None
        and invocation.target_id not in fight.actors
    ):
        area = getattr(fight, "native_effect_areas", {}).get(invocation.target_id)
        if area is not None:
            if area.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS:
                return False  # Actual non-faV Qq PV is not eHg.
        elif trigger_source is None:
            raise UnknownCondition("Unknown native UseGateEffect target identity")
    cell = (
        trigger_source["cell"]
        if trigger_source is not None
        else invocation.cell
        if invocation.target_id is None
        else fight.actors[invocation.target_id].position
        if invocation.target_id in fight.actors
        else fight.native_effect_areas[invocation.target_id]["cell"]
    )
    if cell is None:
        return False
    actual = SimpleNamespace(
        caster_id=source.id, target_id=invocation.target_id, cell=tuple(cell)
    )
    selection_argument = (
        actual
        if trigger_source is None
        else SimpleNamespace(
            caster_id=source.id, target_id=invocation.target_id, cell=invocation.cell
        )
    )
    condition = adapter.condition(fight, plan, None, selection_argument)
    from .combat_native_spell_casting import definition
    from .combat_casting_range import resolve_range

    rule = resolve_range(
        definition(
            reference,
            level,
            condition,
            source.spell_ap_cost_modifiers,
            calculate_costs=False,
        ),
        source,
        condition,
    )
    context = NativeOwnedCastingContext(adapter, fight, plan, actual, condition, rule)

    # Native ePI resolves the static target independently even if fcj rejects.
    def alignment():
        context.resolve_target_fighter()
        return context.alignment(path_option=False)

    return native_use_gate_effect(context.eligibility, alignment)


def enemy_cell_affiliations(adapter, fight, caster_id, cell):
    """eNM's actual aBn branch: fk enemy footprints, then first QI.V eHg."""
    from .combat_global_pv_collections import global_pv_iterator
    from .combat_qi_fight import current_registry

    source = fight.actors[caster_id]
    affiliation = getattr(source, "native_fight_affiliation", source.team)
    for identity in global_pv_iterator(fight, caster_id=None, caster_only=False):
        actor = fight.actors.get(identity)
        if actor is None:
            continue
        metadata = adapter._actor(fight, actor)
        if metadata.targeting.get("is_eGj") is not True:
            raise UnknownCondition("Missing actual native enemy-cell fighter type")
        other = getattr(actor, "native_fight_affiliation", actor.team)
        if other == affiliation:
            continue
        radius = actor.physical_radius
        if type(radius) is not int or not -128 <= radius <= 127:
            raise UnknownCondition("Missing actual eNM fighter radius")
        inside = (
            tuple(actor.position) == tuple(cell)
            if radius <= 0
            else native_pv_cell_distance(actor.position, radius, cell) == 0
        )
        if inside:
            return (other,)
    registry = current_registry(fight)
    order = registry.ordered_U(*cell[:2])
    if not order:
        return ()
    row = registered_slot(registry, order[0])
    if row is None or row["identity"][0] != "actor":
        return ()  # Actual Qq QK is not eHg.
    actor = fight.actors[row["identity"][1]]
    metadata = adapter._actor(fight, actor)
    if metadata.targeting.get("is_eGj") is not True:
        raise UnknownCondition("Missing actual first QI.V eHg authority")
    return (getattr(actor, "native_fight_affiliation", actor.team),)


def cast_cell_condition(
    adapter, fight, plan, caster_id, cell, *, return_invocation=False
):
    """Actual aBn argument with independently resolved eII actor aliases."""
    actual = SimpleNamespace(
        caster_id=caster_id,
        target_id=None,
        cell=None if cell is None else tuple(cell),
        native_target_cell_argument=True,
    )
    if cell is not None:
        temporary = NativeOwnedCastingContext(adapter, fight, plan, actual, None, {})
        temporary.resolve_target_fighter()
        actual.target_id = None if temporary.target is None else temporary.target.id
    conditions = adapter.condition(fight, plan, None, actual)
    return (conditions, actual) if return_invocation else conditions


def resolve_criterion_cell_invocation(adapter, fight, invocation):
    """Keep raw aBn marker and resolve eII's actual first QI fighter separately."""
    from dataclasses import replace
    from .combat_qi_fight import current_registry

    target_id = None
    if invocation.cell is not None:
        registry = current_registry(fight)
        for slot in registry.ordered_U(*invocation.cell[:2]):
            row = registered_slot(registry, slot)
            if row is None or row["identity"][0] != "actor":
                continue
            actor = fight.actors[row["identity"][1]]
            kind = adapter._actor(fight, actor).targeting.get("is_eGj")
            if type(kind) is not bool:
                raise UnknownCondition(
                    "Missing actual criterion cell target native type"
                )
            if kind:
                target_id = actor.id
                break
    return replace(invocation, target_id=target_id)


def use_gate_triggering_effect(adapter, fight, plan, effect, invocation):
    """ePJ overrides only ePI's source-container and evaluated coordinate."""
    if effect is None:
        return False  # Not an actual running eZR criterion context.
    source = getattr(invocation, "native_trigger_context", None)
    if source is None:
        return False  # eII.aU is proven null at external event boundary.
    if not isinstance(source, dict) or source.get("native_events_verified") is not True:
        raise UnknownCondition("Missing actual triggering eZR authority")
    from .combat_active_spell import active_spell_container

    container = active_spell_container(fight)
    if not container["present"]:
        return False  # ePJ.g sees a proven null PN.bah, independently of trigger.
    cell = source.get("cell")
    if (
        not isinstance(cell, (tuple, list))
        or len(cell) != 3
        or any(type(v) is not int for v in cell)
    ):
        raise UnknownCondition("Missing actual triggering eZR.bbd coordinate")
    return use_gate_effect(
        adapter,
        fight,
        plan,
        effect,
        invocation,
        trigger_source=dict(source, casting_container=container),
    )
