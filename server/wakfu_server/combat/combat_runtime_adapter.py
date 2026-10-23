"""Server adapter for the common native runtime, using live preview snapshots.

Native properties are not inferred from player/NPC IDs. The authority must
supply ff e/Qq metadata, deck/breed/summon context and execution decisions.
Events, cell routing, facing/block, state clocks and healing-resistance guards
remain explicit policies. Unknown fcE/effect flags still fail in the resolver
or handlers. This adapter never sends packets or mutates the original fight.
"""
from dataclasses import dataclass
from .combat_effect_runtime import NativeRuntimeContexts
import time
from .combat_conditions import ConditionContext, ConditionCell
from .combat_damage_handler import _snapshot
from .combat_native_actor_lookup import native_actor, native_actor_population
from .combat_original_controller import CURRENT_TARGET, original_target_controller
from .combat_native_death_status import native_is_dead as current_native_is_dead
from .combat_departure_predicates import query as native_departure_flag
from .combat_input_observation import wall_time_ns
from wakfu_server import world_clock


@dataclass(frozen=True)
class NativeActorAuthority:
    targeting: dict
    is_player: bool
    deck_spell_ids: frozenset
    excluded_deck_spell_ids: frozenset
    is_carried: bool
    breed_id: int
    summon_count: int | None
    summon_counts_by_breed: dict | None
    occupant_blocks: bool
    is_summon: bool | None = None
    summon_root_id: int | None = None
    is_carrying: bool | None = (
        None  # Explicit eGj.frA/pGV authority, never inferred from buX.
    )
    is_challenger: bool | None = (
        None  # eHh player/companion membership explicitly supplied.
    )
    native_real_level: int | None = None  # biB progression drm, NPC cmZ.
    native_instance_id: int | None = None  # POSITION rE.Vp -> eGt.zm -> eGj.fE/arM.
    native_controller_id: int | None = (
        None  # Authoritative eHg.dTD lookup in current fbX.
    )
    native_spellbook: object = None  # Explicit eGj.dok/dsx/fzf authority.
    native_constructor_in_fight: bool | None = None  # Fresh big.dnz before aQc.
    native_in_play: bool | None = (
        None  # fdy sax membership, attested by creation/death lifecycle.
    )
    native_ai_control_baseline: bool | None = (
        None  # Actual eGj.dpR source implementation.
    )
    native_controlled_by_ai: bool | None = (
        None  # eGj.fqL/eGz.pHH, never player inference.
    )
    native_summoned_from_symbiot: bool | None = None  # Exact eHg.dTC producer.
    native_summon_counts_complete: bool = False  # Complete GF breed histogram.
    native_is_ehp: bool | None = None  # Actual biB/eHP source type.
    native_captured_roster: object = (
        None  # Owned eHP.drI component, not a profile catalog.
    )
    native_actor_type: int | None = (
        None  # Actual eGj.asQ/aGJ byte, not breed or control.
    )
    native_account_id: int | None = None  # Actual eGj.ePn/Xi creation account.
    native_primary_character_id: int | None = None  # Owned fkJ.sS snapshot.
    native_social_context: object = (
        None  # Typed owned SQL component admission snapshot.
    )
    native_sex: int | None = None  # Actual eGj.aXz, never inferred from actor type.
    native_selected_cosmetics: dict | None = (
        None  # eSU selected values, explicit component snapshot.
    )
    native_npc_prototype_ref: int | None = None  # Actual bje.lJL/blj identity.
    native_copied_equipment_operand: int | None = None  # Actual inherited eGj.dsK.
    native_active_cosmetics: dict | None = (
        None  # eSP lists; {} is known empty, None is unknown.
    )


@dataclass(frozen=True)
class NativeCastAuthority:
    # Every policy reads the same current preview, effect and invocation.
    resolution: object
    cell_eligible: object
    group_cells: object
    damage: object
    healing: object
    stat: object
    state: object
    # Cell obstacle metadata cannot be inferred from terrain walkability.
    cell_obstacle: object
    probability_accepts: object
    random_fraction: object
    damage_block: object = None
    random_number: object = None


class NativeServerRuntimeAdapter:
    """Bind authoritative actor metadata and cast policies to a runtime factory.

    actor_authority(preview, actor) must read current properties (including
    state-driven changes), rather than cache a pre-cast ConditionActor.
    Snapshot statistics, ledger entries and coordinates always come from the
    preview. UID sequence must already have been initialized at placement.
    RNG is owned by the caller's transaction; callers that require RNG rollback
    must clone its state together with the fight before constructing authority.
    """

    def __init__(self, *, actor_authority, cast, viewer_id=None):
        if not callable(actor_authority) or not isinstance(cast, NativeCastAuthority):
            raise ValueError("Missing authoritative actor/cast provider")
        if any(
            not callable(value)
            for name, value in vars(cast).items()
            if name not in ("damage_block", "random_number")
        ) or any(
            value is not None and not callable(value)
            for value in (cast.damage_block, cast.random_number)
        ):
            raise ValueError("Every native cast policy must be explicit")
        if viewer_id is not None and (type(viewer_id) is not int or viewer_id == 0):
            raise ValueError("Invalid explicit native viewer identity")
        self.viewer_id = viewer_id
        self.actor_authority, self.cast = actor_authority, cast

    def _area_identity_query(self, preview, invocation, name, value):
        from .combat_area_predicates import (
            is_area_type,
            is_specific_area,
            is_own_deposit,
            is_own_area,
        )

        from .combat_state_managers import retained_area_pv_row, registered_area_pv

        identity = invocation.target_id
        if getattr(invocation, "native_target_cell_argument", False):
            identity = None
            kind = "null" if invocation.cell is None else "cell"
        elif identity is None:
            kind = "null" if invocation.cell is None else "cell"
        elif identity in preview.actors:
            kind = "actor"
        elif retained_area_pv_row(preview, identity) is not None:
            registered_area_pv(preview, identity)
            kind = "area"
        else:
            raise ValueError("Unknown native area criterion target identity")
        args = dict(target_kind=kind, target_id=identity, cell=invocation.cell)
        if name == "HasEffectAreaProperty":
            from .combat_area_predicates import has_effect_area_property

            return has_effect_area_property(preview, property_id=value, **args)
        if name == "IsAreaType":
            return is_area_type(preview, area_type=value, **args)
        if name == "IsSpecificArea":
            return is_specific_area(preview, reference=value, **args)
        if name not in ("IsOwnDeposit", "IsOwnArea"):
            raise ValueError("Unknown native area identity predicate")

        def pv_owner(identity, seen=frozenset()):
            if identity is None:
                return None
            if type(identity) is not int or identity in seen:
                raise ValueError("Missing native canonical PV owner identity")
            actor = native_actor(preview, identity)
            if actor is not None:
                metadata = self.actor_authority(preview, actor)
                targeting = metadata.targeting
                if targeting.get("is_eGj") is not True or "dpu_id" not in targeting:
                    raise ValueError("Missing native eGj.dpu PV authority")
                owner = targeting["dpu_id"]
                if owner is None:
                    return None
                if type(owner) is not int or owner not in preview.actors:
                    raise ValueError("Missing registered native dpu PV owner")
                return owner  # eII.aT returns eGj.dpu directly, not recursively.
            row = retained_area_pv_row(preview, identity)
            if not isinstance(row, dict) or "owner_id" not in row:
                raise ValueError("Missing native Qp.bch PV authority")
            return pv_owner(row["owner_id"], seen | {identity})

        predicate = is_own_area if name == "IsOwnArea" else is_own_deposit
        return predicate(
            preview,
            source_id=invocation.caster_id,
            pv_owner_query=pv_owner,
            exclude_center=value,
            **args,
        )

    def _actor(self, preview, actor, *, projected_authority=None):
        _snapshot(actor)
        if not isinstance(actor.effect_minima, dict):
            raise ValueError("Missing native characteristic minima")
        value = (
            self.actor_authority(preview, actor)
            if projected_authority is None
            else projected_authority
        )
        if not isinstance(value, NativeActorAuthority):
            raise ValueError("Missing native actor property authority")
        if any(
            type(v) is not bool
            for v in (value.is_player, value.is_carried, value.occupant_blocks)
        ):
            raise ValueError("Unknown native actor type/carry/occupancy")
        if type(value.breed_id) is not int or (
            value.summon_count is not None
            and (type(value.summon_count) is not int or value.summon_count < 0)
        ):
            raise ValueError("Unknown native breed/summon context")
        if not isinstance(value.targeting, dict):
            raise ValueError("Missing fcE actor metadata")
        return value

    def condition(
        self,
        preview,
        plan,
        effect,
        invocation,
        *,
        native_original_target_id=CURRENT_TARGET,
        native_original_caster_id=CURRENT_TARGET,
    ):
        aliases = {}
        null_aliases = set()
        # Alias roles can identify the same PV. A pure cell-filter scope may
        # reuse this projection; outside it every evaluation starts fresh.
        from .combat_condition_selection_scope import current_condition_actor_cache

        condition_actor_by_identity = current_condition_actor_cache(self, preview)
        if condition_actor_by_identity is None:
            condition_actor_by_identity = {}

        def authority_for(actor):
            key = ("authority", actor.id)
            if key not in condition_actor_by_identity:
                from .combat_ordinary_authority import OrdinaryActorAuthority
                from .combat_summon import RegisteredSummonAuthority

                if type(self.actor_authority) in (
                    OrdinaryActorAuthority,
                    RegisteredSummonAuthority,
                ):
                    authority, world, fight = self.actor_authority.condition_projection(
                        preview, actor
                    )
                    condition_actor_by_identity[key] = self._actor(
                        preview, actor, projected_authority=authority
                    )
                    condition_actor_by_identity[("properties", actor.id)] = (
                        world,
                        fight,
                    )
                else:
                    condition_actor_by_identity[key] = self._actor(preview, actor)
            return condition_actor_by_identity[key]

        from .combat_table_condition_context import table_only_condition_context

        table_context = table_only_condition_context(
            preview, effect, invocation, authority_for
        )
        if table_context is not None:
            return table_context

        from .combat_challenger_condition_context import challenger_condition_context

        challenger_context = challenger_condition_context(
            preview, effect, invocation, authority_for
        )
        if challenger_context is not None:
            return challenger_context

        from .combat_retained_runtime import native_retained_condition_reader

        # Alias construction is read-only. Validate its complete Qf population
        # once, then discard this lazy reader before another condition/effect.
        alias_retained_effects = native_retained_condition_reader(preview)
        native_cell_argument = getattr(invocation, "native_target_cell_argument", False)
        if native_cell_argument:
            from dataclasses import is_dataclass

            if is_dataclass(invocation):
                from .combat_casting_context import resolve_criterion_cell_invocation

                invocation = resolve_criterion_cell_invocation(
                    self, preview, invocation
                )
        caster_actor = native_actor(preview, invocation.caster_id)
        controller_id = (
            authority_for(caster_actor).native_controller_id
            if caster_actor is not None
            else None
        )
        selected_identities = [
            ("caster", invocation.caster_id),
            ("target", invocation.target_id),
            ("castercontroller", controller_id),
        ]
        selected_trigger = getattr(invocation, "native_trigger_context", None)
        for role in ("caster", "target"):
            if selected_trigger is None:
                selected_identities.append(("triggering" + role, None))
            elif role + "_id" in selected_trigger:
                selected_identities.append(
                    (
                        "triggering" + role,
                        selected_trigger[role + "_id"],
                    )
                )
        for name, identity in selected_identities:
            if identity is None:
                if name != "castercontroller":
                    null_aliases.add(name)
                continue
            if identity in condition_actor_by_identity:
                aliases[name] = condition_actor_by_identity[identity]
                continue
            actor = native_actor(preview, identity)
            if actor is None:
                from .combat_state_managers import registered_area_pv
                from .combat_conditions import ConditionActor

                area = registered_area_pv(preview, identity)
                if area is None:
                    raise ValueError("Unregistered non-null native criterion recipient")
                retained_ids = frozenset()
                retained_actions = frozenset()
                if area.native_running_effect_manager:
                    try:
                        retained_rows = alias_retained_effects(identity)
                    except ValueError:
                        retained_ids = None
                        retained_actions = None
                    else:
                        retained_ids = frozenset(row[0] for row in retained_rows)
                        retained_actions = frozenset(row[1] for row in retained_rows)
                typed = dict(
                    # Registered faW/bcQ area PV is not a biB player.
                    is_player=False,
                    # faV.a(eHh) reports EFFECT_AREA, never a player/companion.
                    is_challenger=False,
                    is_native_fighter=False,
                    is_native_ehg=True,
                    is_character=False,
                    # eNZ calls eHg.dnz; every supported faV subtype
                    # inherits literal true, including a retained Qq pointer.
                    # registered_area_pv above proves the actual PV identity.
                    in_fight=True,
                    is_carried=False,
                    is_carrying=False,
                    retained_effect_ids=retained_ids,
                    retained_action_ids=retained_actions,
                    fight_properties=area.native_fight_properties,
                    # faV captures bcM at creation; owner affiliation may change.
                    fight_affiliation=getattr(area, "native_fight_affiliation", None),
                )
                if area.state_ledger is not None:
                    aliases[name] = area.state_ledger.condition_actor(**typed)
                else:
                    aliases[name] = ConditionActor(
                        actor_id=identity,
                        state_ids=frozenset(),
                        state_levels=(),
                        state_sources=(),
                        **typed,
                    )
                condition_actor_by_identity[identity] = aliases[name]
                continue
            authority = authority_for(actor)
            from .combat_characteristic_conditions import characteristic_ids

            ids = characteristic_ids()
            affiliation = getattr(actor, "native_fight_affiliation", actor.team)
            if type(affiliation) is not int or not -128 <= affiliation < 128:
                raise ValueError("Missing native signed-byte bcM affiliation")
            try:
                retained_rows = alias_retained_effects(actor.id)
                retained_ids = frozenset(row[0] for row in retained_rows)
                retained_actions = frozenset(row[1] for row in retained_rows)
            except ValueError:
                # Unverified populations are unknown, never authoritatively empty.
                # Only a condition needing this information rejects the cast.
                retained_ids = None
                retained_actions = None
            from .combat_native_actor_lookup import detached_authority

            aliases[name] = actor.state_ledger.condition_actor(
                is_player=authority.is_player,
                deck_spell_ids=authority.deck_spell_ids,
                excluded_deck_spell_ids=authority.excluded_deck_spell_ids,
                is_carried=authority.is_carried,
                is_carrying=authority.is_carrying,
                breed_id=authority.breed_id,
                effective_level=actor.effective_level,
                real_level=authority.native_real_level,
                is_challenger=authority.is_challenger,
                fight_affiliation=affiliation,
                is_native_fighter=authority.targeting.get("is_eGj"),
                # eGj.a(eHh) explicitly identifies CHARACTER. Other native
                # actor implementations need their own kind attestation.
                is_character=True
                if authority.targeting.get("is_eGj") is True
                else None,
                is_abandonning=native_departure_flag(actor, "abandonning"),
                is_fleeing=native_departure_flag(actor, "fleeing"),
                is_off_play=authority.targeting.get("baG"),
                is_out_of_play=authority.targeting.get("baK"),
                is_native_ehg=authority.targeting.get("is_eGj"),
                is_in_play=authority.targeting.get("baF"),
                is_dead=(
                    getattr(actor, "native_is_dead", None)
                    if getattr(actor, "native_is_dead", None) is not None
                    else current_native_is_dead(actor)
                ),
                is_summoned_from_symbiot=authority.native_summoned_from_symbiot,
                native_sex=authority.native_sex,
                native_social_context=authority.native_social_context,
                native_account_id=authority.native_account_id,
                is_summon=authority.is_summon,
                summon_root_id=authority.summon_root_id,
                retained_effect_ids=retained_ids,
                retained_action_ids=retained_actions,
                # This entry only attests ordinary actors registered in an
                # active Fight. Other lifecycle contexts need their own proof.
                in_fight=(
                    authority.native_constructor_in_fight
                    if detached_authority(preview, actor) is authority
                    else True
                    if preview.phase == "active"
                    else None
                ),
                physical_radius=actor.physical_radius,
                direction=actor.direction,
                native_instance_id=authority.native_instance_id,
                world_properties=(
                    condition_actor_by_identity[("properties", actor.id)][0]
                    if ("properties", actor.id) in condition_actor_by_identity
                    else frozenset(
                        self.actor_authority.world_properties(preview, actor)
                    )
                    if callable(getattr(self.actor_authority, "world_properties", None))
                    else getattr(actor, "native_world_properties", None)
                ),
                world_property_since_ms=getattr(
                    actor, "native_world_property_since_ms", None
                ),
                fight_properties=(
                    condition_actor_by_identity[("properties", actor.id)][1]
                    if ("properties", actor.id) in condition_actor_by_identity
                    else frozenset(self.actor_authority.properties(preview, actor))
                    if callable(getattr(self.actor_authority, "properties", None))
                    else getattr(actor, "native_fight_properties", None)
                ),
                summon_count=authority.summon_count,
                summon_counts_by_breed=authority.summon_counts_by_breed,
                summon_counts_complete=authority.native_summon_counts_complete,
                characteristics={
                    key: actor.effect_stats[identity]
                    for key, identity in ids.items()
                    if identity in actor.effect_stats
                },
                characteristic_maxima={
                    key: actor.effect_maxima[identity]
                    for key, identity in ids.items()
                    if identity in actor.effect_maxima
                },
            )
            condition_actor_by_identity[identity] = aliases[name]
        source = native_actor(preview, invocation.caster_id)
        target = native_actor(preview, invocation.target_id)
        if source is None:
            from .combat_effect_area_targets import (
                area_target,
                retained_area_source_target,
            )

            source = area_target(preview, invocation.caster_id)
            if source is None:
                source = retained_area_source_target(preview, invocation.caster_id)
            if source is None:
                raise ValueError("Missing actual criterion source PV")
        from .combat_condition_distance import (
            DistanceActor,
            native_caster_target_distance,
        )

        distance = native_caster_target_distance(
            DistanceActor(*source.position[:2], source.physical_radius),
            DistanceActor(*target.position[:2], target.physical_radius)
            if target is not None and not native_cell_argument
            else invocation.cell,
        )
        from .combat_condition_diagonal import native_diagonal
        from .combat_condition_alignment import native_alignment

        if invocation.target_id is None or native_cell_argument:
            diagonal_target = invocation.cell  # Actual eZR.I target aBn or null.
        elif target is not None:
            diagonal_target = target.position
        else:
            from .combat_state_managers import registered_area_pv

            diagonal_area = registered_area_pv(preview, invocation.target_id)
            if diagonal_area is None:
                raise ValueError("Unknown non-null native diagonal target PV")
            # eII.d returns positions only for aBn/eHg targets. A registered
            # Qq/faV PV has a cell but is not an eHg and resolves to native null.
            diagonal_target = None
        diagonal = native_diagonal(source.position, diagonal_target)
        alignment = native_alignment(source.position, diagonal_target)
        from .combat_summon_initialization import detached_actor

        constructor_without_qi = (
            detached_actor(preview, invocation.caster_id) is source
            and source is not None
            and getattr(preview, "native_qi_slots", None) is None
        )
        # A missing constructor QI is unknown, not an empty cell. Criteria
        # that actually consume eOV still reject the missing ConditionCell.
        obstacle = (
            None
            if constructor_without_qi
            else self.cast.cell_obstacle(preview, plan, effect, invocation)
        )
        if obstacle is not None and type(obstacle) is not bool:
            raise ValueError("Invalid native cell obstacle")
        # eOV's cell branch reads Qs.bdm Qq occupants, then QI.V.
        # Retired actors retain identity/state ledgers but are not Qs occupants.
        from .combat_effect_area_targets import area_targets_at_cell

        occupants = tuple(
            area.native_movement_blocking
            for area in area_targets_at_cell(preview, invocation.cell)
        )
        cell = (
            None
            if obstacle is None or invocation.cell is None
            else ConditionCell(invocation.cell in preview.walkable, obstacle, occupants)
        )
        # Actor branches use native eHg.bcM. A cell criterion needs fbX.fk
        # footprint + QI.V affiliations; missing cell metadata stays unknown.
        from .combat_trigger_identifiers import condition_identifiers
        from .combat_activation_conditions import current_activation

        triggering = condition_identifiers(
            getattr(invocation, "native_trigger_context", None)
        )
        trigger_source = getattr(invocation, "native_trigger_context", None)
        for role in ("caster", "target"):
            if trigger_source is None or (
                role + "_id" in trigger_source and trigger_source[role + "_id"] is None
            ):
                null_aliases.add("triggering" + role)

        def triggering_actor_alias(role):
            if trigger_source is None:
                return None
            field = role + "_id"
            if field not in trigger_source:
                raise ValueError("Missing native source relationship: " + field)
            identity = trigger_source[field]
            if identity is None:
                return None
            if type(identity) is not int or not -(1 << 63) <= identity < (1 << 63):
                raise ValueError("Invalid native source PV identity")
            selected = aliases.get("triggering" + role)
            if selected is None or selected.actor_id != identity:
                raise ValueError("Unregistered native triggering PV: " + str(identity))
            return selected

        # eLL compares actual registered PV identity, not transient Python views.
        # The aliases above bind each non-null source ID to its validated PV.
        if trigger_source is None:
            triggering["triggering_caster_is_same"] = False
        elif "caster_id" in trigger_source:
            identity = trigger_source["caster_id"]
            if identity is None:
                triggering["triggering_caster_is_same"] = False
            else:
                selected = triggering_actor_alias("caster")
                caster_alias = aliases.get("caster")
                if selected is not None and caster_alias is not None:
                    triggering["triggering_caster_is_same"] = (
                        selected.actor_id == caster_alias.actor_id
                    )
        if trigger_source is not None:
            trigger_caster = native_actor(preview, trigger_source.get("caster_id"))
            trigger_target = native_actor(preview, trigger_source.get("target_id"))
            # Qe sources may target a real registered/retained Qq, not only eGj.
            # Its validated native view supplies Qq.bcL=0, never a guessed size.
            from .combat_state_managers import selected_native_area_entity

            if trigger_caster is None and trigger_source.get("caster_id") is not None:
                trigger_caster = selected_native_area_entity(
                    preview, trigger_source["caster_id"]
                )
            if trigger_target is None and trigger_source.get("target_id") is not None:
                trigger_target = selected_native_area_entity(
                    preview, trigger_source["target_id"]
                )
            if trigger_caster is not None and trigger_target is not None:
                triggering["triggering_melee_distance"] = native_caster_target_distance(
                    DistanceActor(
                        *trigger_caster.position[:2], trigger_caster.physical_radius
                    ),
                    DistanceActor(
                        *trigger_target.position[:2], trigger_target.physical_radius
                    ),
                )
            for role in ("caster", "target"):
                if role + "_id" not in trigger_source:
                    continue
                identity = trigger_source[role + "_id"]
                if identity is None:
                    triggering["triggering_effect_" + role + "_id"] = -1
                else:
                    selected = triggering_actor_alias(role)
                    if selected is not None and (
                        selected.is_native_ehg is True
                        or selected.is_native_fighter is True
                    ):
                        triggering[
                            "triggering_effect_" + role + "_id"
                        ] = selected.actor_id
                # A PV without proven eHg authority remains unknown.

        boundary = getattr(invocation, "native_cast_boundary_context", None)
        if boundary is not None and trigger_source is None:
            from .combat_cast_events import validate_cast_boundary_context
            from .combat_active_spell import active_spell_id

            validate_cast_boundary_context(boundary)
            if (
                boundary["spell_id"] != active_spell_id(preview)
                or boundary["caster_id"] not in preview.actors
            ):
                raise ValueError("Cast boundary facts differ from actual active spell")
            # Explicit Wakemu policy supplies validated pre-cast distance and
            # casting identity without inventing a native triggering runner.
            same_caster = boundary["caster_id"] == invocation.caster_id
            if same_caster:
                distance = boundary["distance"]
            triggering["triggering_caster_is_same"] = same_caster

        turn_boundary = getattr(invocation, "native_turn_boundary_context", None)
        if turn_boundary is not None:
            from .combat_turn_events import validate_turn_boundary_context

            validate_turn_boundary_context(turn_boundary, fight=preview)
            if trigger_source is not None or boundary is not None:
                raise ValueError(
                    "Owned turn facts cannot replace a native triggering runner"
                )
            # Explicit server policy qualifies whose turn this is. The native
            # triggering Qe and its caster/target aliases remain null.
            triggering["triggering_caster_is_same"] = (
                turn_boundary["actor_id"] == invocation.caster_id
            )

        def native_range_query(
            minimum,
            maximum,
            selector,
            aligned,
            los,
            *,
            relation="enemy",
            in_play=True,
            state_reference=None,
            state_level=-1,
            owner="",
            breed_reference=None,
            world_property_reference=None,
            own_team_states=False,
            human_only=False,
        ):
            from .combat_range_conditions import (
                RangeFighter,
                range_count,
                fighters_breed_count,
                registered_state_carriers,
                attest_state_area_population,
                own_team_state_carriers,
            )
            from .combat_los import static_visible

            key = selector.lower()
            if key == "caster":
                center = source.position
            elif selector == "target" and target is None:
                center = invocation.cell
            elif key == "target":
                center = None if target is None else target.position
            elif key in (
                "triggeringcaster",
                "triggeringtarget",
                "castercontroller",
                "eventtarget",
            ):
                raise ValueError("Missing native range center relationship authority")
            else:
                center = None  # eII.a: an unrecognized selector has no actor.
            retained_reader = None
            if relation == "state":
                from .combat_retained_runtime import native_retained_condition_reader
                from .combat_native_actor_lookup import detached_authority
                from .combat_native_criterion_failure import (
                    NativeCriterionRuntimeFailure,
                )

                if (
                    source is not None
                    and detached_authority(preview, source) is not None
                ):
                    # eKn.d -> eII.o: fresh bje/eZQ has no fbX. The native
                    # alA aborts the entire criterion; eZR.I maps it to false.
                    raise NativeCriterionRuntimeFailure(
                        "Native eKn criterion has no constructor combat context"
                    )
                # Range evaluation is read-only. Share this validation only
                # inside this call, then discard it before any effect mutates.
                retained_reader = native_retained_condition_reader(preview)
                area_state_rows = attest_state_area_population(
                    preview, retained_reader=retained_reader
                )
                if owner.lower() == "caster":
                    state_caster = source.id
                elif owner.lower() == "target":
                    state_caster = None if target is None else target.id
                elif owner.lower() in (
                    "triggeringcaster",
                    "triggeringtarget",
                    "castercontroller",
                    "eventtarget",
                ):
                    raise ValueError(
                        "Missing native range state-caster relationship authority"
                    )
                else:
                    state_caster = None
            else:
                state_caster = None
            state_affiliations = None
            if own_team_states:
                state_affiliations = {
                    candidate.id: getattr(
                        candidate, "native_fight_affiliation", candidate.team
                    )
                    for candidate in preview.actors.values()
                    if not getattr(candidate, "pve_withdrawn", False)
                }
                affiliation = getattr(source, "native_fight_affiliation", source.team)
                area_state_rows = tuple(
                    (
                        position,
                        own_team_state_carriers(
                            states, affiliation, state_affiliations
                        ),
                    )
                    for position, states in area_state_rows
                )
            rows = []
            for candidate in preview.actors.values():
                if getattr(candidate, "pve_withdrawn", False):
                    continue
                metadata = self._actor(preview, candidate)
                if human_only:
                    from .combat_team_count_conditions import human_actor_type

                    if type(metadata.native_in_play) is not bool:
                        raise ValueError("Missing native human-range membership")
                    if not metadata.native_in_play:
                        continue
                    if not human_actor_type(metadata.native_actor_type):
                        continue
                properties = self.actor_authority.properties(preview, candidate)
                if relation == "world_property":
                    world = self.actor_authority.world_properties(preview, candidate)
                    if world_property_reference not in world:
                        continue
                states = (
                    registered_state_carriers(
                        preview, candidate, retained_reader=retained_reader
                    )
                    if relation == "state"
                    else ()
                )
                if own_team_states:
                    states = own_team_state_carriers(
                        states, affiliation, state_affiliations
                    )
                rows.append(
                    RangeFighter(
                        candidate.position,
                        candidate.physical_radius,
                        getattr(candidate, "native_fight_affiliation", candidate.team),
                        metadata.native_in_play,
                        42 in properties,
                        metadata.breed_id == 3794 and metadata.is_carried,
                        114 in properties,
                        states,
                        metadata.breed_id,
                    )
                )
            if relation == "breed":
                return fighters_breed_count(
                    tuple(rows), center=center, maximum=maximum, breed=breed_reference
                )
            map_id = self._actor(preview, source).native_instance_id
            result = range_count(
                tuple(rows),
                relation=relation,
                in_play=in_play,
                state_reference=state_reference,
                state_level=state_level,
                state_caster=state_caster,
                affiliation=getattr(source, "native_fight_affiliation", source.team),
                center=center,
                minimum=minimum,
                maximum=maximum,
                aligned=aligned,
                los=los,
                visible=lambda a, b: static_visible(map_id, a, b),
            )

            if relation == "state":
                from .combat_range_conditions import area_state_count

                result += area_state_count(
                    area_state_rows,
                    center=center,
                    minimum=minimum,
                    maximum=maximum,
                    reference=state_reference,
                    level=state_level,
                    caster=state_caster,
                    aligned=aligned,
                    los=los,
                    visible=lambda a, b: static_visible(map_id, a, b),
                )
            return result

        def own_specific_area_query(reference, selector):
            from .combat_effect_area_queries import own_specific_area

            return own_specific_area(
                preview,
                reference=reference,
                selector=selector,
                caster_id=invocation.caster_id,
                target_id=invocation.target_id,
                cell=invocation.cell,
            )

        def valid_path_query(options, limit):
            from .combat_valid_path_policy import admitted_route
            from .combat_summon_initialization import detached_actor

            if options is not None or limit not in (None, 2):
                raise ValueError("Unsupported Wakemu valid-path options or limit")
            if source is None or detached_actor(preview, source.id) is not None:
                raise ValueError("Missing owned combat path-witness caster")
            if self._actor(preview, source).targeting.get("is_eGj") is not True:
                raise ValueError("Path-witness source is not an actual fighter")
            endpoint = (
                invocation.cell
                if native_cell_argument or target is None
                else target.position
            )
            if limit is None:
                from .combat_valid_path_native import native_default_valid_path

                return native_default_valid_path(preview, source, endpoint)
            return admitted_route(preview, source.id, endpoint, limit=limit) is not None

        def line_of_sight_query():
            from .combat_condition_los import native_condition_los

            return native_condition_los(
                preview,
                self._actor,
                invocation.caster_id,
                invocation.target_id,
                invocation.cell,
                actor_property_authority=self.actor_authority,
                target_is_cell=native_cell_argument,
            )

        def owned_summon_breed_rows():
            from .combat_summon_conditions import SummonBreedRow

            rows = []
            for actor in native_actor_population(preview):
                if getattr(actor, "pve_withdrawn", False):
                    continue
                metadata = self._actor(preview, actor)
                if (
                    metadata.targeting.get("is_eGj") is not True
                    or "dpu_id" not in metadata.targeting
                ):
                    raise ValueError("Missing native fUQ/dpu actor population")
                # eGj.b(fcb,actor): absent relation -> the actor itself.
                owner = metadata.targeting["dpu_id"]
                owner = actor.id if owner is None else owner
                if type(owner) is not int or native_actor(preview, owner) is None:
                    raise ValueError("Missing registered native dpu owner")
                rows.append(
                    SummonBreedRow(actor.id, metadata.breed_id, owner, actor.position)
                )
            return rows

        def has_summon_breed_query(reference):
            from .combat_summon_conditions import has_summon_with_breed

            return has_summon_with_breed(
                owned_summon_breed_rows(),
                caller_id=invocation.caster_id,
                breed=reference,
            )

        def surrounding_own_summon_query(selector, breed, mode):
            from .combat_summon_conditions import surrounding_own_summon

            center_role = "target" if selector.lower() == "target" else "caster"
            center = tuple(coordinate_query(axis, center_role) for axis in "xyz")
            if -(1 << 63) in center:
                return False
            return surrounding_own_summon(
                owned_summon_breed_rows(),
                caller_id=invocation.caster_id,
                center=center,
                breed=breed,
                mode=mode,
            )

        def fighters_breed_range_query(maximum, selector, reference):
            return native_range_query(
                0,
                maximum,
                selector,
                False,
                False,
                relation="breed",
                in_play=False,
                breed_reference=reference,
            )

        def fighters_world_property_range_query(maximum, selector, reference):
            from .combat_world_properties import registry

            reference = ((reference + (1 << 31)) % (1 << 32)) - (1 << 31)
            if str(reference) not in registry():
                return 0  # eKu: eHQ.Qm returned null.
            return native_range_query(
                0,
                maximum,
                selector,
                False,
                False,
                relation="world_property",
                in_play=False,
                world_property_reference=reference,
            )

        def fighters_max_level_query(kind, in_play_only):
            from .combat_max_level_conditions import fighters_max_level
            from .combat_summon_initialization import detached_actor

            if source is not None and detached_actor(preview, source.id) is not None:
                raise ValueError("Native fighter maximum requires actual fight context")
            rows = []
            for candidate in native_actor_population(preview):
                metadata = self._actor(preview, candidate)
                rows.append(
                    (
                        metadata.native_actor_type,
                        metadata.native_in_play,
                        self.actor_authority.properties(preview, candidate),
                        candidate.effective_level,
                    )
                )
            return fighters_max_level(rows, kind, in_play_only)

        def fighters_min_level_query(kind, in_play_only):
            from .combat_max_level_conditions import fighters_min_level
            from .combat_summon_initialization import detached_actor

            if source is not None and detached_actor(preview, source.id) is not None:
                raise ValueError("Native fighter minimum requires actual fight context")
            rows = []
            for candidate in native_actor_population(preview):
                metadata = self._actor(preview, candidate)
                rows.append(
                    (
                        metadata.native_actor_type,
                        metadata.native_in_play,
                        self.actor_authority.properties(preview, candidate),
                        candidate.effective_level,
                    )
                )
            return fighters_min_level(rows, kind, in_play_only)

        def player_max_level_query():
            from .combat_max_level_conditions import player_max_level

            return player_max_level(preview)

        def enemy_range_query(minimum, maximum, selector, aligned, los):
            return native_range_query(minimum, maximum, selector, aligned, los)

        def human_enemies_range_query(minimum, maximum, selector, aligned, los):
            # eKe inherits eKn and selects in-play enemy aGJ types0/5.
            return native_range_query(
                minimum,
                maximum,
                selector,
                aligned,
                los,
                relation="enemy",
                in_play=True,
                human_only=True,
            )

        def human_allies_range_query(minimum, maximum, selector, aligned, los):
            return native_range_query(
                minimum,
                maximum,
                selector,
                aligned,
                los,
                relation="ally",
                in_play=True,
                human_only=True,
            )

        def allies_count_query(selector):
            from .combat_team_count_conditions import allies_membership

            selected = target if selector.lower() == "target" else source
            if selected is None:
                raise ValueError("Missing native allies-count reference actor")
            affiliation = getattr(selected, "native_fight_affiliation", selected.team)
            count = 0
            for candidate in native_actor_population(preview):
                metadata = self._actor(preview, candidate)
                properties = self.actor_authority.properties(preview, candidate)
                if allies_membership(
                    metadata.native_in_play,
                    getattr(candidate, "native_fight_affiliation", candidate.team),
                    affiliation,
                    properties,
                ):
                    count += 1
            return count

        def monsters_count_query(team=-1, breed=-1):
            from .combat_team_count_conditions import monsters_count
            from .combat_summon_initialization import detached_actor

            if source is not None and detached_actor(preview, source.id) is not None:
                raise ValueError("Native monster count requires actual fight context")
            rows = []
            for candidate in native_actor_population(preview):
                if getattr(candidate, "pve_withdrawn", False):
                    continue
                metadata = self._actor(preview, candidate)
                rows.append(
                    (
                        metadata.native_actor_type,
                        metadata.native_in_play,
                        getattr(candidate, "native_fight_affiliation", candidate.team),
                        metadata.breed_id,
                    )
                )
            return monsters_count(rows, team, breed)

        def allies_range_query(minimum, maximum, selector, aligned, los, in_play=True):
            return native_range_query(
                minimum,
                maximum,
                selector,
                aligned,
                los,
                relation="ally",
                in_play=in_play,
            )

        def state_range_query(maximum, selector, reference, level, in_play, owner):
            return native_range_query(
                0,
                maximum,
                selector,
                False,
                False,
                relation="state",
                in_play=in_play,
                state_reference=reference,
                state_level=level,
                owner=owner,
            )

        def own_team_state_range_query(
            maximum, selector, reference, level, in_play, owner
        ):
            return native_range_query(
                0,
                maximum,
                selector,
                False,
                False,
                relation="state",
                in_play=in_play,
                state_reference=reference,
                state_level=level,
                owner=owner,
                own_team_states=True,
            )

        def specific_area_range_query(selector, reference, minimum, maximum, owned):
            from .combat_effect_area_queries import specific_area_count

            if selector.lower() == "target":
                center = invocation.cell if target is None else target.position
            else:
                center = None if source is None else source.position
            return specific_area_count(
                preview,
                source_id=invocation.caster_id,
                center=center,
                area_reference=reference,
                minimum=minimum,
                maximum=maximum,
                owned=owned,
            )

        def valid_gate_for_tp_query(selector, minimum, maximum):
            from .combat_gate_conditions import has_valid_gate_for_tp
            from .combat_effect_area_queries import _rows

            caster = aliases.get("caster")
            if caster is None:
                if "caster" in null_aliases:
                    return True  # eMT actual absent caster returns native0.
                raise ValueError("Missing native valid-gate caster PV")
            if type(caster.fight_affiliation) is not int:
                raise ValueError("Missing native valid-gate caster bcM")
            if selector.lower() == "target":
                if invocation.target_id is None:
                    center = invocation.cell  # eZR.I passes bft as actual aBn.
                elif invocation.target_id in preview.actors:
                    center = native_actor(preview, invocation.target_id).position
                else:
                    from .combat_state_managers import registered_area_pv

                    area = registered_area_pv(preview, invocation.target_id)
                    if area is None:
                        raise ValueError("Missing native valid-gate target PV")
                    center = area.position
            else:
                center = source.position
            occupancy = getattr(self.cast, "gate_cell_affiliations", None)
            return has_valid_gate_for_tp(
                _rows(preview),
                caster_id=invocation.caster_id,
                caster_affiliation=caster.fight_affiliation,
                center=center,
                minimum=minimum,
                maximum=maximum,
                cell_affiliations=(
                    None
                    if not callable(occupancy)
                    else lambda x, y: occupancy(preview, plan, x, y)
                ),
            )

        def nearest_ally_beacon_query():
            from .combat_nearest_ally_beacon import nearest_ally_beacon_distance

            caster = aliases.get("caster")
            if caster is None:
                if "caster" in null_aliases:
                    return -1
                raise ValueError("Missing native nearest-beacon caster eHg")
            if caster.is_native_fighter is False and caster.is_native_ehg is False:
                return -1
            if (
                caster.is_native_fighter is not True
                and caster.is_native_ehg is not True
            ):
                raise ValueError("Missing native nearest-beacon caster eHg type")
            from .combat_summon_initialization import detached_actor
            from .combat_nearest_ally_beacon import require_beacon_combat_context

            require_beacon_combat_context(
                detached=source is not None
                and detached_actor(preview, source.id) is not None
            )
            return nearest_ally_beacon_distance(
                preview,
                caster_affiliation=caster.fight_affiliation,
                target_position=invocation.cell
                if native_cell_argument or target is None
                else target.position,
            )

        def closest_specific_area_query(selector, reference, use_path, owner_selector):
            from .combat_effect_area_queries import closest_specific_area_distance

            # ePF.tw is case sensitive. Other selector/fallback contexts need
            # their actual native event payload, not a lowercased actor guess.
            if selector not in ("caster", "target"):
                raise ValueError("Missing native closest-area ePF selector authority")
            identity = selected_relationship_id(selector)
            selected = aliases.get(selector)
            if selected is None:
                if selector not in null_aliases:
                    raise ValueError("Missing native closest-area selected PV")
                return -1  # eIw returns before resolving owner/fight for null eHg.
            elif selected.is_native_fighter is not True:
                if selected.is_native_fighter is False:
                    return -1
                raise ValueError("Missing native closest-area eGj type authority")
            owner_id = None
            if owner_selector is not None:
                key = owner_selector.lower()
                if key in aliases:
                    owner_id = selected_relationship_id(key)
                elif key not in null_aliases:
                    raise ValueError(
                        "Missing native closest-area owner selector authority"
                    )
            return closest_specific_area_distance(
                preview,
                selected_id=identity,
                reference=reference,
                use_path=use_path,
                owner_id=owner_id,
            )

        def active_spell_id_query():
            from .combat_active_spell import active_spell_id

            return active_spell_id(preview)

        def fight_model_query():
            from .combat_summon_initialization import detached_actor

            # Actual eZQ construction context and fresh eGj.dpt are null;
            # eKj returns 0 after its context/container/caster fallbacks.
            if source is not None and detached_actor(preview, source.id) is not None:
                return 0
            model = getattr(preview, "native_fight_model", None)
            if type(model) is not int or not -128 <= model <= 127:
                raise ValueError("Missing native serialized combat kind")
            return model

        def cosmetic_state():
            from .combat_cosmetic_conditions import NativeCosmeticState

            actor = native_actor(preview, invocation.caster_id)
            if actor is None:
                raise ValueError("Missing native cosmetic caster")
            metadata = self._actor(preview, actor)
            return NativeCosmeticState(
                metadata.targeting.get("is_eGj"),
                metadata.native_selected_cosmetics,
                metadata.native_active_cosmetics,
            )

        def active_cosmetic_id_query(category):
            from .combat_cosmetic_conditions import active_cosmetic_id

            return active_cosmetic_id(cosmetic_state(), category)

        def has_active_cosmetic_query(category, cosmetic_id):
            from .combat_cosmetic_conditions import has_active_cosmetic

            return has_active_cosmetic(cosmetic_state(), category, cosmetic_id)

        def pvp_query():
            from .combat_system_conditions import fight_is_pvp
            from .combat_summon_initialization import detached_actor

            if source is not None and detached_actor(preview, source.id) is not None:
                return False  # eOL: fresh eZQ/PO context and eGj.dpt are null-fight.
            return fight_is_pvp(fight_model_query())

        def is_protector_in_fight_query(selector):
            from .combat_protector_fight_condition import query_owned_fight
            from .combat_summon_initialization import detached_actor

            identity = (
                invocation.target_id if selector == "target" else invocation.caster_id
            )
            selected = native_actor(preview, identity)
            if selected is None or detached_actor(preview, selected.id) is not None:
                return False  # eII null or actual fresh constructor has no fcb.
            metadata = self._actor(preview, selected)
            if metadata.targeting.get("is_eGj") is False:
                return False
            return query_owned_fight(
                preview, selected, lambda actor: self._actor(preview, actor)
            )

        def battleground_query():
            from wakfu_server.native_world_context import is_battleground

            if caster_actor is None:
                return False  # eNo rejects a null/non-fighter eII.n recipient.
            authority = authority_for(caster_actor)
            fighter = authority.targeting.get("is_eGj")
            if type(fighter) is not bool:
                raise ValueError("Missing native IsBattleground fighter kind")
            if not fighter:
                return False
            return is_battleground(authority.native_instance_id)

        def boolean_system_configuration_query(key):
            from .combat_system_conditions import boolean_system_configuration

            return boolean_system_configuration(preview, key)

        def current_container_level_query():
            from .combat_container_level import running_container_level

            return running_container_level(
                preview, plan, None if effect is None else invocation
            )

        def area_type_range_query(selector, kind, minimum, maximum, owned):
            from .combat_effect_area_queries import area_type_count

            center = (
                (invocation.cell if target is None else target.position)
                if selector.lower() == "target"
                else (None if source is None else source.position)
            )
            return area_type_count(
                preview,
                source_id=invocation.caster_id,
                center=center,
                area_type=kind,
                minimum=minimum,
                maximum=maximum,
                owned=owned,
            )

        def actor_obstacle_query(selector):
            from .combat_obstacle_condition import is_obstacle

            key = selector.lower()
            if key == "caster":
                identity = invocation.caster_id
            elif key == "target":
                identity = invocation.target_id
            elif key == "castercontroller":
                identity = controller_id
            elif key in ("triggeringcaster", "triggeringtarget"):
                trigger = invocation.native_trigger_context
                identity = (
                    None
                    if trigger is None
                    else trigger.get(
                        "caster_id" if key == "triggeringcaster" else "target_id"
                    )
                )
            elif key == "eventtarget":
                raise ValueError("Missing native ePH event-target fallback authority")
            else:
                identity = None  # eII.a unknown selector is null, not caster.
            return is_obstacle(
                preview,
                selected_id=identity,
                viewer_id=self.viewer_id,
                actor_authority=self.actor_authority,
            )

        def actor_area_type_query(selector, kind, owned):
            from .combat_effect_area_queries import actor_on_area_type

            identity = (
                invocation.target_id
                if selector.lower() == "target"
                else invocation.caster_id
            )
            return actor_on_area_type(
                preview, actor_id=identity, area_type=kind, owned=owned
            )

        def team_area_range_query(selector, kind, minimum, maximum):
            from .combat_effect_area_queries import team_area_count

            from .combat_team_area_center import team_area_center

            center = team_area_center(preview, invocation, selector)
            return team_area_count(
                preview,
                source_id=invocation.caster_id,
                center=center,
                area_type=kind,
                minimum=minimum,
                maximum=maximum,
            )

        def cell_specific_area_query(reference, owned):
            from .combat_effect_area_queries import cell_contains_specific

            return cell_contains_specific(
                preview,
                cell=invocation.cell,
                reference=reference,
                source_id=invocation.caster_id,
                owned=owned,
            )

        def cell_area_type_query(kind, owned):
            from .combat_effect_area_queries import cell_contains_type

            return cell_contains_type(
                preview,
                cell=invocation.cell,
                area_type=kind,
                source_id=invocation.caster_id,
                owned=owned,
            )

        def coordinate_query(axis, selector):
            from .combat_condition_coordinates import native_coordinate

            identity = (
                invocation.target_id if selector == "target" else invocation.caster_id
            )
            actor = native_actor(preview, identity)
            area = getattr(preview, "native_effect_areas", {}).get(identity)
            position = (
                actor.position
                if actor is not None
                else (area["cell"] if area is not None else None)
            )
            if native_cell_argument and selector == "target":
                position = invocation.cell
            # faV is eHg even when its Qf is null; coordinates need no state manager.
            if actor is None and area is None and selector == "target":
                position = invocation.cell
            return native_coordinate(axis, position)

        def life_actor_query(name, selector):
            from .combat_condition_life import registered_life_predicate

            identity = (
                invocation.target_id if selector == "target" else invocation.caster_id
            )
            if selector == "target" and (native_cell_argument or identity is None):
                if invocation.cell is None:
                    return False
                # Actual eII.a/b resolve aBn through QI.U/O's first eGj.
                from .combat_qi_fight import current_registry

                registry = current_registry(preview)
                identity = None
                for slot in registry.ordered_U(*invocation.cell[:2]):
                    row = registry.slots[slot]
                    if row is not None and row["identity"][0] == "actor":
                        identity = row["identity"][1]
                        actor = native_actor(preview, identity)
                        if (
                            actor is None
                            or self._actor(preview, actor).targeting.get("is_eGj")
                            is not True
                        ):
                            raise ValueError("Missing native QI life fighter type")
                        break
            return registered_life_predicate(preview, self._actor, name, identity)

        def border_cell_query(selector):
            from .combat_condition_border import border_cell_result
            from .combat_state_managers import registered_area_pv

            identity = (
                invocation.target_id if selector == "target" else invocation.caster_id
            )
            actor = native_actor(preview, identity)
            if actor is not None:
                metadata = self._actor(preview, actor)
                if metadata.targeting.get("is_eGj") is not True:
                    raise ValueError(
                        "Missing native eHg actor type for border-cell coordinate"
                    )
                qi = getattr(preview, "native_qi_snapshot", None)
                if qi is None:
                    raise ValueError("Missing serialized native QI border snapshot")
                return border_cell_result(qi, *actor.position[:2])

            if identity is not None:
                area = registered_area_pv(preview, identity)
                if area is None:
                    raise ValueError(
                        "Unregistered non-null native border-cell recipient"
                    )
                if area.state_ledger is not None:
                    raise ValueError("Missing native ePy border-cell target authority")
                return -1  # A null-Qf Qq/faV PV is not eHg/ePy.

            if selector == "target" and invocation.cell is None:
                return -1  # eII.b resolves a proven null target.
            if invocation.target_id is None and invocation.cell is not None:
                if native_cell_argument:
                    return -1  # Completed QI lookup proved no eHg target.
                raise ValueError(
                    "Missing native QI.U first fighter for explicit target cell"
                )
            raise ValueError("Missing native border-cell actor identity")

        def facing_query(selector, query):
            selected_id, opposite_id = (
                (invocation.target_id, invocation.caster_id)
                if selector == "target"
                else (invocation.caster_id, invocation.target_id)
            )
            return query(preview, selected_id, opposite_id, aliases.get(selector))

        def backstabbed_query(selector):
            from .combat_condition_facing import native_backstabbed

            return facing_query(selector, native_backstabbed)

        def facestabbed_query(selector):
            from .combat_condition_facing import native_facestabbed

            return facing_query(selector, native_facestabbed)

        def sidestabbed_query(selector):
            from .combat_condition_facing import native_sidestabbed

            return facing_query(selector, native_sidestabbed)

        def selected_relationship_id(selector):
            key = selector.lower()
            if key == "caster":
                return invocation.caster_id
            if key == "target":
                return invocation.target_id
            if key == "castercontroller":
                return controller_id
            if key in ("triggeringcaster", "triggeringtarget"):
                if trigger_source is None:
                    return None
                role = "caster_id" if key == "triggeringcaster" else "target_id"
                if role not in trigger_source:
                    raise ValueError("Missing native selected source relationship")
                return trigger_source[role]
            return None  # Original eII unknown selector produces null.

        def areas_base_id_query(reference, selector):
            from .combat_effect_area_queries import areas_with_base_id

            return areas_with_base_id(
                preview,
                reference=reference,
                owner_id=None
                if selector is None
                else selected_relationship_id(selector),
                all_owners=selector is None,
            )

        def actor_specific_area_query(selector, reference, owned):
            from .combat_effect_area_queries import actor_on_specific_area
            from .combat_state_managers import verified_native_owner_root

            ownership = (
                ("own" if owned else "all")
                if type(owned) is bool
                else (
                    "own"
                    if owned.lower() == "ownareas"
                    else "team"
                    if owned.lower() == "teamareas"
                    else "all"
                )
            )
            selected_id = selected_relationship_id(selector)
            selected_actor = native_actor(preview, selected_id)
            controller_id = None
            if selected_actor is not None:
                controller_id = self._actor(
                    preview, selected_actor
                ).native_controller_id
                if type(controller_id) is not int:
                    raise ValueError("Missing verified native selected controller")
            return actor_on_specific_area(
                preview,
                actor_id=selected_id,
                reference=reference,
                ownership=ownership,
                selected_controller_id=controller_id,
                owner_root_query=lambda identity: verified_native_owner_root(
                    preview, identity, lambda actor: self._actor(preview, actor)
                ),
            )

        def own_summon_actor_query(selector):
            key = selector.lower()
            if key in aliases:
                return aliases[key]
            identity = selected_relationship_id(selector)
            if identity is None:
                return None
            selected = native_actor(preview, identity)
            if selected is None:
                raise ValueError("Unregistered native own-summon selected actor")
            metadata = self._actor(preview, selected)
            return selected.state_ledger.condition_actor(
                is_native_fighter=metadata.targeting.get("is_eGj"),
                breed_id=metadata.breed_id,
                is_summon=metadata.is_summon,
                summon_root_id=metadata.summon_root_id,
            )

        def spell_level_query(reference, selector):
            identity = selected_relationship_id(selector)
            actor = native_actor(preview, identity)
            if actor is None:
                raise ValueError(
                    "Native GetSpellLevel selected user is not a character"
                )
            authority = self._actor(preview, actor)
            from .combat_spell_level import NativeSpellBook

            if not isinstance(authority.native_spellbook, NativeSpellBook):
                raise ValueError("Missing native complete owned spellbook authority")
            return authority.native_spellbook.level(reference)

        def state_max_level_query(
            minimum, maximum, selector, reference, owner_selector
        ):
            from .combat_state_max_level_range import (
                maximum_state_level,
                state_level_population,
            )
            from .combat_summon_initialization import detached_actor
            from .combat_native_criterion_failure import NativeCriterionRuntimeFailure
            from .combat_state_managers import registered_area_pv

            if source is not None and detached_actor(preview, source.id) is not None:
                raise NativeCriterionRuntimeFailure(
                    "Native eLt criterion has no constructor combat context"
                )

            def selected_identity(value):
                key = value.lower()
                if key not in (
                    "caster",
                    "target",
                    "castercontroller",
                    "triggeringcaster",
                    "triggeringtarget",
                ):
                    return None  # Actual eII.a unknown selector is null.
                if key == "target" and native_cell_argument:
                    actor = condition_cell_fighter()
                    return None if actor is None else actor.id
                selected = state_actor_query(value)
                return None if selected is None else selected.actor_id

            if selector == "target" and native_cell_argument:
                center = invocation.cell
            else:
                identity = selected_identity(selector)
                selected = native_actor(preview, identity)
                if selected is None and identity is not None:
                    selected = registered_area_pv(preview, identity)
                center = None if selected is None else selected.position
            if center is None:
                return 0  # Native eLt returns before scanning fUQ/Qs.
            owner = selected_identity(owner_selector) if owner_selector else None
            caster_present = True
            if owner is not None:
                caster = aliases.get("caster")
                if caster is None:
                    if "caster" not in null_aliases:
                        raise ValueError("Missing native eLt source eHg nullability")
                    caster_present = False
                elif caster.is_native_ehg is True or caster.is_native_fighter is True:
                    caster_present = True
                elif (
                    caster.is_native_ehg is False and caster.is_native_fighter is False
                ):
                    caster_present = False
                else:
                    raise ValueError("Missing native eLt source eHg type")
            return maximum_state_level(
                state_level_population(preview, self.actor_authority),
                center=center,
                minimum=minimum,
                maximum=maximum,
                reference=reference,
                owner_id=owner,
                native_caster_present=caster_present,
            )

        def state_actor_query(selector):
            key = selector.lower()
            if key in ("caster", "target", "castercontroller"):
                selected = aliases.get(key)
                if selected is None:
                    if key in null_aliases:
                        return None
                    raise ValueError(f"Missing native eHg state-query actor: {key}")
                # eME/eMF select eHg, not the narrower eGj fighter type.
                # Actual faV areas implement eHg and may own a state ledger.
                if selected.is_native_ehg is True or selected.is_native_fighter is True:
                    return selected
                if selected.is_native_ehg is False:
                    return None
                raise ValueError(f"Missing native eHg state-query type: {key}")
            if key in ("triggeringcaster", "triggeringtarget"):
                if trigger_source is None:
                    return None  # Ready/turn external boundary has no source Qe.
                role = "caster_id" if key == "triggeringcaster" else "target_id"
                if role not in trigger_source:
                    raise ValueError("Missing native state-query source relationship")
                identity = trigger_source[role]
                if identity is None:
                    return None
                selected = triggering_actor_alias(
                    "caster" if key == "triggeringcaster" else "target"
                )
                if selected is None:
                    return None
                # eME/eMF require eHg. The original validated area alias keeps
                # its real ledger even while Qs retirement holds that PV alive.
                if selected.is_native_ehg is True or selected.is_native_fighter is True:
                    return selected
                if selected.is_native_ehg is False:
                    return None
                raise ValueError("Missing native eHg triggering state-query type")
            raise ValueError("Unsupported native state-query relationship")

        def team_id_query(selector):
            key = selector.lower()
            if key in ("caster", "target", "castercontroller"):
                selected = aliases.get(key)
                if selected is not None:
                    return selected.fight_affiliation
                if key == "target" and target is None:
                    return -1
                raise ValueError(f"Missing native team actor authority: {key}")
            if key in ("triggeringcaster", "triggeringtarget"):
                if trigger_source is None:
                    if key == "triggeringtarget":
                        from .combat_external_turn_recipient import (
                            qualified_boundary_actor,
                        )

                        boundary_actor = qualified_boundary_actor(
                            preview,
                            turn_context=turn_boundary,
                            movement_context=getattr(
                                invocation, "native_movement_boundary_context", None
                            ),
                        )
                        if boundary_actor is not None:
                            self._actor(preview, boundary_actor)
                            return getattr(
                                boundary_actor,
                                "native_fight_affiliation",
                                boundary_actor.team,
                            )
                    return -1
                role = "caster_id" if key == "triggeringcaster" else "target_id"
                if role not in trigger_source:
                    raise ValueError(f"Missing native team source relationship: {key}")
                identity = trigger_source[role]
                if identity is None:
                    return -1
                selected = triggering_actor_alias(
                    "caster" if key == "triggeringcaster" else "target"
                )
                if selected is None:
                    return -1
                # eLx reads eHg.bcM from the original Qe participant, including
                # a real faV's constructor capture; never its current owner.
                return selected.fight_affiliation
            if key == "eventtarget":
                raise ValueError("Missing native ePH event target authority")
            return -1  # Unrecognized eII.a selector is native null.

        def caster_facing_fighter_query():
            from .combat_caster_facing_condition import native_caster_facing_fighter

            # The running Qe criterion context is not an ePy wrapper.
            return native_caster_facing_fighter(
                preview, native_actor(preview, invocation.caster_id), self._actor
            )

        def behind_target_free_query():
            from .combat_behind_target_condition import native_behind_target_free

            if (native_cell_argument or invocation.target_id is None) and getattr(
                invocation, "state_uid", None
            ) is not None:
                # eII.b checks an actual ePy wrapper before its aBn/QI fallback.
                raise ValueError("Missing native eNA wrapped state target authority")
            selected = native_actor(preview, invocation.target_id)
            if selected is None and invocation.target_id in getattr(
                preview, "native_effect_areas", {}
            ):
                raise ValueError("Missing native eNA non-eHg wrapped target authority")
            return native_behind_target_free(
                preview,
                native_actor(preview, invocation.caster_id),
                selected,
                self._actor,
            )

        def free_cell_query(selector, forward, sideways):
            from .combat_free_cell_condition import native_free_cell
            from .combat_qi_fight import current_registry
            from .combat_effect_area_targets import area_targets

            target_selected = selector.lower() == "target"
            selected = "target" if target_selected else "caster"
            opposite = "caster" if target_selected else "target"
            origin = tuple(coordinate_query(axis, selected) for axis in "xyz")
            other = tuple(coordinate_query(axis, opposite) for axis in "xyz")
            if -(1 << 63) in origin or -(1 << 63) in other:
                return False
            registry = current_registry(preview)

            def first_obstacle(x, y):
                order = registry.ordered_U(x, y)
                return bool(order and registry.slots[order[0]] is not None)

            return native_free_cell(
                origin,
                other,
                forward,
                sideways,
                terrain_free=registry.snapshot().R,
                area_blockers=tuple(
                    (area.position, area.native_movement_blocking)
                    for area in area_targets(preview)
                ),
                first_obstacle=first_obstacle,
            )

        def free_surrounding_cell_query(strict_terrain, target_selected):
            from .combat_free_surrounding_condition import native_free_surrounding_cell
            from .combat_qi_fight import current_registry

            # eMp requires the original caster argument to be eGj.
            caster = native_actor(preview, invocation.caster_id)
            if caster is None:
                return False
            caster_kind = self._actor(preview, caster).targeting.get("is_eGj")
            if caster_kind is False:
                return False
            if caster_kind is not True:
                raise ValueError("Missing native free-surrounding caster fighter type")
            registry = current_registry(preview)
            identity = invocation.target_id if target_selected else invocation.caster_id
            if target_selected and (native_cell_argument or identity is None):
                # eII.b converts an aBn target through the first QI eGj.
                if invocation.cell is None:
                    return False
                identity = None
                for slot in registry.ordered_U(*invocation.cell[:2]):
                    row = registry.slots[slot]
                    if row is not None and row["identity"][0] == "actor":
                        identity = row["identity"][1]
                        break
            actor = native_actor(preview, identity)
            if actor is None:
                if identity in getattr(preview, "native_effect_areas", {}):
                    raise ValueError(
                        "Native free-surrounding selected actor has no eGj position"
                    )
                return False
            snapshot = registry.snapshot()
            return native_free_surrounding_cell(
                actor.position,
                terrain_free=snapshot.R if strict_terrain else snapshot.Q,
                first_obstacle=lambda x, y: bool(
                    (order := registry.ordered_U(x, y))
                    and registry.slots[order[0]] is not None
                ),
            )

        def controlled_by_ai_query(selector):
            # eNH's one string selects target only for case-insensitive target.
            target_selected = selector.lower() == "target"
            identity = invocation.target_id if target_selected else invocation.caster_id
            if target_selected and (native_cell_argument or identity is None):
                if invocation.cell is None:
                    return False
                raise ValueError(
                    "Missing native IsControlledByAI cell-to-eGj resolution"
                )
            actor = native_actor(preview, identity)
            if actor is None:
                if identity is None or identity in getattr(
                    preview, "native_effect_areas", {}
                ):
                    return False
                raise ValueError("Unregistered native AI-control recipient")
            value = self._actor(preview, actor).native_controlled_by_ai
            if type(value) is not bool:
                raise ValueError("Missing native eGj.fqL authority")
            return value

        def owned_area_count_query(selector, count_query):
            from .combat_effect_area_queries import _rows
            from .combat_global_pv_collections import global_area_order

            # A missing manager must not be mistaken for an empty Qs.
            global_area_order(preview)
            if selector is None:
                return count_query(_rows(preview))
            selector = selector.lower()
            if selector == "target" and native_cell_argument:
                raise ValueError("Missing native NbGlyphs cell-to-eGj resolution")
            selected = state_actor_query(selector)
            if selected is None:
                return count_query(_rows(preview), filter_owner=True)
            if selected.is_native_fighter is False:
                return count_query(_rows(preview), filter_owner=True)
            if (
                selected.is_native_fighter is not True
                or type(selected.actor_id) is not int
            ):
                raise ValueError("Missing native NbGlyphs eHg identity")
            return count_query(
                _rows(preview), actor_id=selected.actor_id, filter_owner=True
            )

        def condition_cell_fighter():
            # Shared eII.b(true,aBn,...) source: first actual eGj in QI.U,
            # identical to the existing life_actor_query cell resolver.
            if invocation.cell is None:
                return None
            from .combat_qi_fight import current_registry

            registry = current_registry(preview)
            for slot in registry.ordered_U(*invocation.cell[:2]):
                row = registry.slots[slot]
                if row is None or row["identity"][0] != "actor":
                    continue
                actor = native_actor(preview, row["identity"][1])
                if actor is None:
                    raise ValueError("Missing actual native QI condition actor")
                kind = self._actor(preview, actor).targeting.get("is_eGj")
                if type(kind) is not bool:
                    raise ValueError("Missing native QI condition fighter type")
                if kind:
                    return actor
            return None

        def enemy_line_of_sight_query(selector):
            from .combat_enemy_condition_los import enemy_condition_los
            from .combat_summon_initialization import detached_actor

            key = "target" if selector.lower() == "target" else "caster"
            if key == "target" and native_cell_argument:
                actor = condition_cell_fighter()
                if actor is None:
                    return False
                identity = actor.id
                affiliation = getattr(actor, "native_fight_affiliation", actor.team)
            else:
                selected = state_actor_query(key)
                if selected is None:
                    return False
                identity = selected.actor_id
                affiliation = selected.fight_affiliation
            if source is not None and detached_actor(preview, source.id) is not None:
                return False  # eMs eII.aS has no fbX in fresh eZQ.
            return enemy_condition_los(
                preview,
                self.actor_authority,
                affiliation=affiliation,
                target_id=identity,
                target_position=(
                    invocation.cell
                    if native_cell_argument or target is None
                    else target.position
                ),
            )

        def has_been_raised_query(selector):
            from .combat_restore_strategy import has_been_raised_by_effect

            # eMc compares the literal string with "target" ignoring case;
            # every other string selects the caster through eII.b(false,...).
            key = "target" if selector.lower() == "target" else "caster"
            if key == "target" and native_cell_argument:
                actor = condition_cell_fighter()
                return False if actor is None else has_been_raised_by_effect(actor)
            selected = state_actor_query(key)
            if selected is None or selected.is_native_fighter is False:
                return False
            if selected.is_native_fighter is not True:
                raise ValueError("Missing native raised-by-effect eGj type")
            actor = native_actor(preview, selected.actor_id)
            if actor is None:
                raise ValueError("Missing actual raised-by-effect fighter")
            return has_been_raised_by_effect(actor)

        def glyph_count_query(selector):
            from .combat_glyph_count import native_glyph_count

            return owned_area_count_query(selector, native_glyph_count)

        def wall_count_query(selector):
            from .combat_wall_count import native_wall_count

            return owned_area_count_query(selector, native_wall_count)

        def gate_count_query(selector, mode):
            from .combat_effect_area_queries import _rows
            from .combat_gate_conditions import native_gate_count

            if selector.lower() == "target" and native_cell_argument:
                raise ValueError("Missing native NbGates cell-to-eGj resolution")
            selected = aliases.get(selector.lower())
            if selected is None or selected.is_native_fighter is False:
                return 0
            if (
                selected.is_native_fighter is not True
                or type(selected.actor_id) is not int
            ):
                raise ValueError("Missing native NbGates eGj identity")
            return native_gate_count(
                _rows(preview),
                actor_id=selected.actor_id,
                affiliation=selected.fight_affiliation,
                mode=mode,
            )

        def use_gate_effect_query():
            from .combat_casting_context import use_gate_effect

            return use_gate_effect(self, preview, plan, effect, invocation)

        def use_gate_triggering_effect_query():
            from .combat_casting_context import use_gate_triggering_effect

            return use_gate_triggering_effect(self, preview, plan, effect, invocation)

        def original_controller_predicate_query(name):
            from .combat_original_controller import controller_predicate

            return controller_predicate(
                preview,
                self.actor_authority,
                invocation.caster_id,
                invocation.target_id,
                invocation.cell,
                target_is_cell=native_cell_argument,
                name=name,
            )

        def breed_in_symbiot_query(reference, selector):
            from .combat_captured_roster_condition import breed_in_symbiot

            key = selector.lower()
            if key == "caster":
                identity = invocation.caster_id
            elif key == "target":
                identity = invocation.target_id
                if native_cell_argument or identity is None:
                    from .combat_qi_fight import current_registry

                    identity = None
                    if invocation.cell is not None:
                        registry = current_registry(preview)
                        for slot in registry.ordered_U(*invocation.cell[:2]):
                            row = registry.slots[slot]
                            if row is not None and row["identity"][0] == "actor":
                                identity = row["identity"][1]
                                break
            elif key in (
                "triggeringcaster",
                "triggeringtarget",
                "castercontroller",
                "eventtarget",
            ):
                raise ValueError(
                    "Missing native symbiot selector relationship authority"
                )
            else:
                return False  # Actual eII.a unrecognized selector returns null.
            actor = native_actor(preview, identity)
            if actor is None:
                if identity is not None and identity not in getattr(
                    preview, "native_effect_areas", {}
                ):
                    raise ValueError("Unregistered native symbiot selector identity")
                return False  # Null/faV is not the actual eHP required by eMd.
            return breed_in_symbiot(self._actor(preview, actor), reference)

        def has_summon_query(selector):
            from .combat_captured_roster_condition import has_captured_summon

            selected = (
                condition_cell_fighter()
                if selector == "target" and native_cell_argument
                else (
                    native_actor(preview, invocation.target_id)
                    if selector == "target"
                    else native_actor(preview, invocation.caster_id)
                )
            )
            if selected is None:
                identity = (
                    invocation.target_id
                    if selector == "target"
                    else invocation.caster_id
                )
                if (
                    not (selector == "target" and native_cell_argument)
                    and identity is not None
                    and identity not in getattr(preview, "native_effect_areas", {})
                ):
                    raise ValueError("Unregistered native HasSummon selector identity")
                return False  # eII.a resolved no actual eGj; eIF returns-1.
            metadata = self._actor(preview, selected)
            if metadata.targeting.get("is_eGj") is not True:
                raise ValueError("Missing actual eIF selected fighter type")
            return has_captured_summon(metadata)

        def selected_creature_available_query():
            from .combat_captured_roster_condition import selected_creature_status

            source_actor = native_actor(preview, invocation.caster_id)
            if source_actor is None:
                raise ValueError("Native eON requires a non-null actual caster")
            return selected_creature_status(self._actor(preview, source_actor))

        def space_in_symbiot_query():
            from .combat_captured_roster_condition import space_in_symbiot

            source_actor = native_actor(preview, invocation.caster_id)
            if source_actor is None:
                raise ValueError("Missing actual eLm caster resolution authority")
            metadata = self._actor(preview, source_actor)
            if metadata.targeting.get("is_eGj") is not True:
                raise ValueError("Missing actual eLm caster eGj type")
            return space_in_symbiot(metadata)

        def enemy_cell_affiliations_query():
            from .combat_casting_context import enemy_cell_affiliations

            return enemy_cell_affiliations(
                self, preview, invocation.caster_id, invocation.cell
            )

        def is_hero_query():
            from .combat_native_ai_hero_predicates import registered_is_hero

            # Effect-context eII.n selects ePy.fyI (the current caster).
            if caster_actor is None:
                raise ValueError("Missing native IsHero current fighter")
            return registered_is_hero(
                preview, caster_actor, self._actor(preview, caster_actor)
            )

        def ai_has_cast_spell_query(spell_id):
            from .combat_ai_cast_history import has_cast_spell

            # Explicit Wakemu policy: the actual effect caster owns this
            # fight's authorized-cast ledger. Native ffb lifetime is unknown.
            return has_cast_spell(preview, invocation.caster_id, spell_id)

        def dungeon_difficulty_query():
            from .combat_dungeon_difficulty_condition import runtime_difficulty

            metadata = (
                None
                if caster_actor is None
                else self.actor_authority(preview, caster_actor).targeting
            )
            return runtime_difficulty(preview, invocation.caster_id, metadata)

        return ConditionContext(
            aliases,
            cell,
            distance,
            alignment,
            dungeon_difficulty_query=dungeon_difficulty_query,
            random_number_query=(
                None
                if not callable(self.cast.random_number)
                else lambda limit, exclusions: self.cast.random_number(
                    preview, plan, limit, exclusions
                )
            ),
            is_hero_query=is_hero_query,
            enemy_line_of_sight_query=enemy_line_of_sight_query,
            has_been_raised_query=has_been_raised_query,
            ai_has_cast_spell_query=ai_has_cast_spell_query,
            world_property_now_ms=wall_time_ns("runtime_adapter.world_property.wall_ns")
            // 1_000_000,
            current_fighter_id=preview.current.id if preview.current is not None else 0,
            equipment_type_query=(
                (
                    lambda references, target, inventory: self.actor_authority.has_equipment_type(
                        preview,
                        preview.actors.get(invocation.target_id, source)
                        if target
                        else source,
                        references,
                        inventory,
                    )
                )
                if callable(getattr(self.actor_authority, "has_equipment_type", None))
                else None
            ),
            weapon_type_query=(
                (
                    lambda references: self.actor_authority.has_weapon_type(
                        preview, source, references
                    )
                )
                if callable(getattr(self.actor_authority, "has_weapon_type", None))
                else None
            ),
            item_quantity_query=(
                (
                    lambda references: self.actor_authority.item_quantity(
                        preview, source, references
                    )
                )
                if callable(getattr(self.actor_authority, "item_quantity", None))
                else None
            ),
            is_in_diagonal=diagonal,
            line_of_sight_query=line_of_sight_query,
            valid_path_query=valid_path_query,
            fighters_breed_range_query=fighters_breed_range_query,
            fighters_world_property_range_query=fighters_world_property_range_query,
            fighters_max_level_query=fighters_max_level_query,
            fighters_min_level_query=fighters_min_level_query,
            player_max_level_query=player_max_level_query,
            human_allies_range_query=human_allies_range_query,
            human_enemies_range_query=human_enemies_range_query,
            allies_count_query=allies_count_query,
            monsters_count_query=monsters_count_query,
            has_summon_breed_query=has_summon_breed_query,
            enemy_range_query=enemy_range_query,
            allies_range_query=allies_range_query,
            state_max_level_query=state_max_level_query,
            state_range_query=state_range_query,
            own_team_state_range_query=own_team_state_range_query,
            specific_area_range_query=specific_area_range_query,
            nearest_ally_beacon_query=nearest_ally_beacon_query,
            closest_specific_area_query=closest_specific_area_query,
            valid_gate_for_tp_query=valid_gate_for_tp_query,
            use_gate_effect_query=use_gate_effect_query,
            use_gate_triggering_effect_query=use_gate_triggering_effect_query,
            activation_query=lambda name, argument: current_activation(
                preview, name, argument
            ),
            original_controller_predicate_query=original_controller_predicate_query,
            selected_creature_available_query=selected_creature_available_query,
            breed_in_symbiot_query=breed_in_symbiot_query,
            space_in_symbiot_query=space_in_symbiot_query,
            has_summon_query=has_summon_query,
            surrounding_own_summon_query=surrounding_own_summon_query,
            controlled_by_ai_query=controlled_by_ai_query,
            free_cell_query=free_cell_query,
            caster_facing_fighter_query=caster_facing_fighter_query,
            behind_target_free_query=behind_target_free_query,
            free_surrounding_cell_query=free_surrounding_cell_query,
            gate_count_query=gate_count_query,
            wall_count_query=wall_count_query,
            glyph_count_query=glyph_count_query,
            own_specific_area_query=own_specific_area_query,
            area_identity_query=lambda name, value: self._area_identity_query(
                preview, invocation, name, value
            ),
            cell_area_type_query=cell_area_type_query,
            cell_specific_area_query=cell_specific_area_query,
            team_area_range_query=team_area_range_query,
            area_type_range_query=area_type_range_query,
            actor_area_type_query=actor_area_type_query,
            actor_obstacle_query=actor_obstacle_query,
            state_actor_query=state_actor_query,
            areas_base_id_query=areas_base_id_query,
            actor_specific_area_query=actor_specific_area_query,
            own_summon_actor_query=own_summon_actor_query,
            viewer_id=self.viewer_id,
            coordinate_query=coordinate_query,
            border_cell_query=border_cell_query,
            team_id_query=team_id_query,
            backstabbed_query=backstabbed_query,
            facestabbed_query=facestabbed_query,
            sidestabbed_query=sidestabbed_query,
            active_spell_id_query=active_spell_id_query,
            fight_model_query=fight_model_query,
            pvp_query=pvp_query,
            is_protector_in_fight_query=is_protector_in_fight_query,
            battleground_query=battleground_query,
            daytime_query=lambda: world_clock.daytime(world_clock.current_time_ms()),
            boolean_system_configuration_query=boolean_system_configuration_query,
            active_cosmetic_id_query=active_cosmetic_id_query,
            has_active_cosmetic_query=has_active_cosmetic_query,
            spell_level_query=spell_level_query,
            current_container_level_query=current_container_level_query,
            effect_caster_original_controller_query=lambda: original_target_controller(
                preview,
                self.actor_authority,
                invocation.caster_id
                if native_original_caster_id is CURRENT_TARGET
                else native_original_caster_id,
            ),
            effect_target_original_controller_query=lambda: original_target_controller(
                preview,
                self.actor_authority,
                invocation.target_id
                if native_original_target_id is CURRENT_TARGET
                else native_original_target_id,
            ),
            fight_current_table_turn=getattr(preview, "native_table_turn", None),
            enemy_target_kind=(
                ("null" if invocation.cell is None else "cell")
                if native_cell_argument
                else "actor"
                if target is not None
                else "other"
                if invocation.target_id is not None
                else "null"
                if invocation.cell is None
                else "cell"
            ),
            enemy_cell_affiliations_query=enemy_cell_affiliations_query,
            effect_target_absent=invocation.target_id is None,
            target_cell_is_explicit=(
                native_cell_argument
                or invocation.target_id is None
                and invocation.cell is not None
            ),
            native_cell_target_fighter_resolved=True if native_cell_argument else None,
            null_actor_aliases=frozenset(null_aliases),
            state_null_fallback_absent=True,  # Actual effect context Qe is not ePy.
            life_actor_query=life_actor_query,
            **triggering,
        )

    def cast_condition(self, preview, request):
        """Conditional cost facts before resource spend, without a fake effect.

        The ordinary cast cell policy does not require an effect definition.
        Future policies that need one must provide a dedicated cast policy.
        """
        from types import SimpleNamespace

        caster = native_actor(preview, request["actor_id"])
        if caster is None:
            raise ValueError("Missing conditional-cost caster")
        from dataclasses import replace
        from .combat_casting_context import (
            NativeOwnedCastingContext,
            cast_cell_condition,
        )

        conditions, context = cast_cell_condition(
            self, preview, request, caster.id, request["target"], return_invocation=True
        )

        def native_usage_context_query(target_id, spell_id, level):
            from copy import copy

            selected = copy(context)
            selected.target_id = target_id
            selected.native_target_cell_argument = False
            selected.native_explicit_target = target_id is not None
            plan = dict(request, spell_id=spell_id, evaluation_level=level)
            return self.condition(preview, plan, None, selected)

        def native_casting_query(rule, spell_id, level):
            plan = dict(request, spell_id=spell_id, evaluation_level=level)
            casting = NativeOwnedCastingContext(
                self, preview, plan, context, conditions, rule
            )
            casting.normal_mode = True
            casting.resolve_target_fighter()
            aligned = casting.normal_alignment()
            trace = [dict(stage="normal_alignment", value=aligned)]
            try:
                result = casting.eligibility(trace=trace) if aligned else "twU"
            except ValueError as error:
                error.native_casting_context = dict(
                    criterion=rule.get("cast_criterion_raw"),
                    caster_id=caster.id,
                    target_cell=list(context.cell),
                    target_id=context.target_id,
                    spell_id=spell_id,
                    evaluation_level=level,
                )
                error.native_casting_trace = trace
                raise
            diagnostic = dict(
                selected_casting_flags={
                    key: rule.get(key)
                    for key in (
                        "line_of_sight",
                        "linear",
                        "diagonal",
                        "linear_path",
                        "path_option",
                        "free_cell",
                        "range_modifiable",
                        "allow_self",
                        "forbid_QI_P",
                        "minimum",
                        "maximum",
                    )
                },
                criterion=rule.get("cast_criterion_raw"),
                caster_id=caster.id,
                target_cell=list(context.cell),
                target_id=context.target_id,
                spell_id=spell_id,
                evaluation_level=level,
                trace=trace,
            )
            return dict(
                result=result,
                aligned=aligned,
                diagnostic=diagnostic,
                target_id=None if casting.target is None else casting.target.id,
            )

        return replace(
            conditions,
            native_casting_query=native_casting_query,
            native_usage_context_query=native_usage_context_query,
        )

    def targets(self, preview, plan, effect, invocation):
        contexts = {
            actor.id: dict(self._actor(preview, actor).targeting)
            for actor in native_actor_population(preview)
            if not getattr(actor, "pve_withdrawn", False)
        }
        # A retained effect may outlive its caster's global PV membership.
        # Resolve that source through current authority without making it a
        # candidate target or a recipient of global turn events.
        if invocation is not None and invocation.caster_id not in contexts:
            caster = native_actor(preview, invocation.caster_id)
            if caster is not None:
                contexts[caster.id] = dict(self._actor(preview, caster).targeting)
        return contexts

    def random(self, preview, plan):
        value = self.cast.random_fraction(preview, plan)
        if type(value) not in (int, float) or not 0 <= value < 1:
            raise ValueError("Invalid authoritative native random fraction")
        return value

    @staticmethod
    def uid(preview, plan):
        value = preview.native_effect_uid_next
        if type(value) is not int or not 0 < value < (1 << 63) - 1:
            raise ValueError(
                "Initialize authoritative native effect UID before casting"
            )
        return value

    def healing_events(self, preview, plan, replay, retention):
        from .combat_ordinary_events import OrdinaryHealingEvents
        from .combat_ordinary_authority import OrdinaryActorAuthority

        from .combat_summon import ordinary_roster_authority

        if not ordinary_roster_authority(self.actor_authority):
            return None  # Other actor families need their own lifecycle authority.
        return OrdinaryHealingEvents(
            adapter=self, preview=preview, plan=plan, replay=replay, retention=retention
        )

    def area_affiliation(self, preview, source_identity):
        """Capture faV.j(PV): only an actual eGj owner copies current bcM."""
        source = native_actor(preview, source_identity)
        if source is None:
            from .combat_state_managers import registered_area_pv

            if registered_area_pv(preview, source_identity) is None:
                raise ValueError("Unregistered non-null area affiliation source")
            # faV constructors initialize ebh=-1; Qq bav is not eGj kind20.
            return -1
        authority = self._actor(preview, source)
        native_fighter = authority.targeting.get("is_eGj")
        if type(native_fighter) is not bool:
            raise ValueError("Missing native area owner eGj type authority")
        if not native_fighter:
            return -1
        if hasattr(source, "native_fight_affiliation"):
            affiliation = source.native_fight_affiliation
        else:
            from .combat_summon import ordinary_roster_authority

            if not ordinary_roster_authority(self.actor_authority):
                raise ValueError("Missing actual native area owner bcM affiliation")
            # Ordinary fcb/eGj.bcM uses team, independently of obstacle bcN.
            affiliation = source.team
        if type(affiliation) is not int or not -128 <= affiliation < 128:
            raise ValueError("Invalid native signed-byte area owner bcM")
        return affiliation

    def contexts(self):
        from .combat_qi_fight import register_effect_area_obstacle

        def state_spell_level(preview, plan, effect, invocation, spell_reference):
            caster = native_actor(preview, invocation.caster_id)
            if caster is None:
                raise ValueError("Missing native eWu caster character")
            authority = self._actor(preview, caster)
            native_fighter = authority.targeting.get("is_eGj")
            if native_fighter is False:
                return None  # eWu.eq leaves its initial level for non-eGj casters.
            if native_fighter is not True:
                raise ValueError("Unknown native eWu caster type")
            from .combat_spell_level import NativeSpellBook

            book = authority.native_spellbook
            if not isinstance(book, NativeSpellBook):
                raise ValueError("Missing native complete owned spellbook authority")
            if book.levels is None:
                return None  # Native dok()==null: eq logs and keeps the initial level.
            if type(spell_reference) is not int:
                raise ValueError("Invalid native eWu owned spell reference")
            level = book.levels.get(spell_reference)
            if level is None:
                return None  # fyR.pb miss also preserves the initial level.
            if type(level) is not int or not -32768 <= level <= 32767:
                raise ValueError("Invalid native owned spell level")
            return level

        return NativeRuntimeContexts(
            actor_candidates=lambda p, plan, e, i: native_actor_population(p),
            resolution=self.cast.resolution,
            native_targets=self.targets,
            cell_eligible=self.cast.cell_eligible,
            condition=self.condition,
            probability=self.cast.probability_accepts,
            group_cells=self.cast.group_cells,
            damage=self.cast.damage,
            healing=self.cast.healing,
            stat=self.cast.stat,
            state=self.cast.state,
            rounding=self.random,
            uid_start=self.uid,
            healing_events=self.healing_events,
            damage_block=self.cast.damage_block,
            area_affiliation=self.area_affiliation,
            area_obstacle_register=register_effect_area_obstacle,
            state_spell_level=state_spell_level,
            state_random=(
                None
                if not callable(self.cast.random_number)
                else lambda preview, plan, limit: self.cast.random_number(
                    preview, plan, limit, ()
                )
            ),
        )
