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
from .combat_original_controller import CURRENT_TARGET, original_target_controller


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
    native_in_play: bool | None = (
        None  # fdy sax membership, attested by creation/death lifecycle.
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

    def _actor(self, preview, actor):
        _snapshot(actor)
        if not isinstance(actor.effect_minima, dict):
            raise ValueError("Missing native characteristic minima")
        value = self.actor_authority(preview, actor)
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
    ):
        aliases = {}
        caster_actor = preview.actors.get(invocation.caster_id)
        controller_id = (
            self._actor(preview, caster_actor).native_controller_id
            if caster_actor is not None
            else None
        )
        for name, identity in (
            ("caster", invocation.caster_id),
            ("target", invocation.target_id),
            ("castercontroller", controller_id),
        ):
            actor = preview.actors.get(identity)
            if actor is None:
                from .combat_state_managers import state_manager

                manager = state_manager(preview, identity)
                if manager is not None:
                    # Actual faV eHg/Qf, without fictitious fighter resources.
                    aliases[name] = manager.state_ledger.condition_actor(
                        is_native_fighter=False,
                    )
                continue
            authority = self._actor(preview, actor)
            from .combat_characteristic_conditions import characteristic_ids

            ids = characteristic_ids()
            affiliation = getattr(actor, "native_fight_affiliation", actor.team)
            if type(affiliation) is not int or not -128 <= affiliation < 128:
                raise ValueError("Missing native signed-byte bcM affiliation")
            from .combat_retained_runtime import native_retained_condition_effects

            try:
                retained_rows = native_retained_condition_effects(preview, actor.id)
                retained_ids = frozenset(row[0] for row in retained_rows)
                retained_actions = frozenset(row[1] for row in retained_rows)
            except ValueError:
                # Unverified populations are unknown, never authoritatively empty.
                # Only a condition needing this information rejects the cast.
                retained_ids = None
                retained_actions = None
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
                is_off_play=authority.targeting.get("baG"),
                is_summon=authority.is_summon,
                summon_root_id=authority.summon_root_id,
                retained_effect_ids=retained_ids,
                retained_action_ids=retained_actions,
                # This entry only attests ordinary actors registered in an
                # active Fight. Other lifecycle contexts need their own proof.
                in_fight=True if preview.phase == "active" else None,
                physical_radius=actor.physical_radius,
                native_instance_id=authority.native_instance_id,
                world_properties=(
                    frozenset(self.actor_authority.world_properties(preview, actor))
                    if callable(getattr(self.actor_authority, "world_properties", None))
                    else getattr(actor, "native_world_properties", None)
                ),
                world_property_since_ms=getattr(
                    actor, "native_world_property_since_ms", None
                ),
                fight_properties=(
                    frozenset(self.actor_authority.properties(preview, actor))
                    if callable(getattr(self.actor_authority, "properties", None))
                    else getattr(actor, "native_fight_properties", None)
                ),
                summon_count=authority.summon_count,
                summon_counts_by_breed=authority.summon_counts_by_breed,
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
        source = preview.actors[invocation.caster_id]
        target = preview.actors.get(invocation.target_id)
        from .combat_condition_distance import (
            DistanceActor,
            native_caster_target_distance,
        )

        distance = native_caster_target_distance(
            DistanceActor(*source.position[:2], source.physical_radius),
            DistanceActor(*target.position[:2], target.physical_radius)
            if target is not None
            else invocation.cell,
        )
        alignment = (
            None
            if target is None
            else (
                source.position[0] == target.position[0]
                or source.position[1] == target.position[1]
            )
        )
        obstacle = self.cast.cell_obstacle(preview, plan, effect, invocation)
        if obstacle is not None and type(obstacle) is not bool:
            raise ValueError("Invalid native cell obstacle")
        occupants = tuple(
            self._actor(preview, a).occupant_blocks
            for a in preview.actors.values()
            if a.position == invocation.cell
        )
        cell = (
            None
            if obstacle is None
            else ConditionCell(invocation.cell in preview.walkable, obstacle, occupants)
        )
        # Actor branches use native eHg.bcM. A cell criterion needs fbX.fk
        # footprint + QI.V affiliations; missing cell metadata stays unknown.
        from .combat_trigger_identifiers import condition_identifiers

        triggering = condition_identifiers(
            getattr(invocation, "native_trigger_context", None)
        )
        trigger_source = getattr(invocation, "native_trigger_context", None)
        # eLL compares Qe.bbb and eII.aW by PV object identity. Registered
        # actors resolve to their sole owned object; absent source is native null.
        if trigger_source is None:
            triggering["triggering_caster_is_same"] = False
        elif "caster_id" in trigger_source:
            identity = trigger_source["caster_id"]
            if identity is None:
                triggering["triggering_caster_is_same"] = False
            elif identity in preview.actors:
                triggering["triggering_caster_is_same"] = (
                    preview.actors[identity] is source
                )
        if trigger_source is not None:
            trigger_caster = preview.actors.get(trigger_source.get("caster_id"))
            trigger_target = preview.actors.get(trigger_source.get("target_id"))
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
                elif identity in preview.actors:
                    triggering["triggering_effect_" + role + "_id"] = identity
                # Unresolved PV is not automatically eHg/eGj: retain unknown.

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
            own_team_states=False,
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
            if relation == "state":
                area_state_rows = attest_state_area_population(preview)
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
                metadata = self._actor(preview, candidate)
                properties = self.actor_authority.properties(preview, candidate)
                states = (
                    registered_state_carriers(preview, candidate)
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

        def line_of_sight_query():
            from .combat_condition_los import native_condition_los

            return native_condition_los(
                preview,
                self._actor,
                invocation.caster_id,
                invocation.target_id,
                invocation.cell,
            )

        def has_summon_breed_query(reference):
            from .combat_summon_conditions import SummonBreedRow, has_summon_with_breed

            rows = []
            for actor in preview.actors.values():
                metadata = self._actor(preview, actor)
                if (
                    metadata.targeting.get("is_eGj") is not True
                    or "dpu_id" not in metadata.targeting
                ):
                    raise ValueError("Missing native fUQ/dpu actor population")
                # eGj.b(fcb,actor): absent relation -> the actor itself.
                owner = metadata.targeting["dpu_id"]
                owner = actor.id if owner is None else owner
                if type(owner) is not int or owner not in preview.actors:
                    raise ValueError("Missing registered native dpu owner")
                rows.append(SummonBreedRow(actor.id, metadata.breed_id, owner))
            return has_summon_with_breed(
                rows, caller_id=invocation.caster_id, breed=reference
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

        def enemy_range_query(minimum, maximum, selector, aligned, los):
            return native_range_query(minimum, maximum, selector, aligned, los)

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

        def active_spell_id_query():
            from .combat_active_spell import active_spell_id

            return active_spell_id(preview)

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

            center = (
                (invocation.cell if target is None else target.position)
                if selector.lower() == "target"
                else (None if source is None else source.position)
            )
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
            actor = preview.actors.get(identity)
            area = getattr(preview, "native_effect_areas", {}).get(identity)
            position = (
                actor.position
                if actor is not None
                else (area["cell"] if area is not None else None)
            )
            # faV is eHg even when its Qf is null; coordinates need no state manager.
            if actor is None and area is None and selector == "target":
                position = invocation.cell
            return native_coordinate(axis, position)

        def backstabbed_query(selector):
            from .combat_condition_facing import native_backstabbed

            selected_id, opposite_id = (
                (invocation.target_id, invocation.caster_id)
                if selector == "target"
                else (invocation.caster_id, invocation.target_id)
            )
            return native_backstabbed(
                preview, selected_id, opposite_id, aliases.get(selector)
            )

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
            return actor_on_specific_area(
                preview,
                actor_id=selected_relationship_id(selector),
                reference=reference,
                ownership=ownership,
            )

        def own_summon_actor_query(selector):
            key = selector.lower()
            if key in aliases:
                return aliases[key]
            identity = selected_relationship_id(selector)
            if identity is None:
                return None
            selected = preview.actors.get(identity)
            if selected is None:
                raise ValueError("Unregistered native own-summon selected actor")
            metadata = self._actor(preview, selected)
            return selected.state_ledger.condition_actor(
                is_native_fighter=metadata.targeting.get("is_eGj"),
                breed_id=metadata.breed_id,
                is_summon=metadata.is_summon,
                summon_root_id=metadata.summon_root_id,
            )

        def state_actor_query(selector):
            key = selector.lower()
            if key in ("caster", "target", "castercontroller"):
                return aliases.get(key)
            if key in ("triggeringcaster", "triggeringtarget"):
                if trigger_source is None:
                    return None  # Ready/turn external boundary has no source Qe.
                role = "caster_id" if key == "triggeringcaster" else "target_id"
                if role not in trigger_source:
                    raise ValueError("Missing native state-query source relationship")
                identity = trigger_source[role]
                if identity is None:
                    return None
                from .combat_state_managers import state_manager

                selected = state_manager(preview, identity)
                if selected is None:
                    raise ValueError("Unregistered native triggering state-query actor")
                return selected.state_ledger.condition_actor()
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
                    return -1
                role = "caster_id" if key == "triggeringcaster" else "target_id"
                if role not in trigger_source:
                    raise ValueError(f"Missing native team source relationship: {key}")
                identity = trigger_source[role]
                if identity is None:
                    return -1
                actor = preview.actors.get(identity)
                if actor is None:
                    raise ValueError(
                        f"Unregistered native triggering team actor: {identity}"
                    )
                self._actor(
                    preview, actor
                )  # eHg authority, independent of listener rebinding.
                return getattr(actor, "native_fight_affiliation", actor.team)
            if key == "eventtarget":
                raise ValueError("Missing native ePH event target authority")
            return -1  # Unrecognized eII.a selector is native null.

        return ConditionContext(
            aliases,
            cell,
            distance,
            alignment,
            random_number_query=(
                None
                if not callable(self.cast.random_number)
                else lambda limit, exclusions: self.cast.random_number(
                    preview, plan, limit, exclusions
                )
            ),
            world_property_now_ms=time.time_ns() // 1_000_000,
            current_fighter_id=preview.current.id if preview.current is not None else 0,
            item_quantity_query=(
                (
                    lambda references: self.actor_authority.item_quantity(
                        preview, source, references
                    )
                )
                if callable(getattr(self.actor_authority, "item_quantity", None))
                else None
            ),
            line_of_sight_query=line_of_sight_query,
            fighters_breed_range_query=fighters_breed_range_query,
            has_summon_breed_query=has_summon_breed_query,
            enemy_range_query=enemy_range_query,
            allies_range_query=allies_range_query,
            state_range_query=state_range_query,
            own_team_state_range_query=own_team_state_range_query,
            specific_area_range_query=specific_area_range_query,
            own_specific_area_query=own_specific_area_query,
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
            team_id_query=team_id_query,
            backstabbed_query=backstabbed_query,
            active_spell_id_query=active_spell_id_query,
            current_container_level_query=current_container_level_query,
            effect_target_original_controller_query=lambda: original_target_controller(
                preview,
                self.actor_authority,
                invocation.target_id
                if native_original_target_id is CURRENT_TARGET
                else native_original_target_id,
            ),
            fight_current_table_turn=getattr(preview, "native_table_turn", None),
            enemy_target_kind="actor" if target is not None else "cell",
            effect_target_absent=invocation.target_id is None,
            **triggering,
        )

    def cast_condition(self, preview, request):
        """Conditional cost facts before resource spend, without a fake effect.

        The ordinary cast cell policy does not require an effect definition.
        Future policies that need one must provide a dedicated cast policy.
        """
        from types import SimpleNamespace

        caster = preview.actors.get(request["actor_id"])
        if caster is None:
            raise ValueError("Missing conditional-cost caster")
        target = next(
            (
                actor
                for actor in preview.actors.values()
                if actor.hp > 0 and actor.position == request["target"]
            ),
            None,
        )
        context = SimpleNamespace(
            caster_id=caster.id,
            target_id=None if target is None else target.id,
            cell=request["target"],
        )
        return self.condition(preview, request, None, context)

    def targets(self, preview, plan, effect, invocation):
        return {
            actor.id: dict(self._actor(preview, actor).targeting)
            for actor in preview.actors.values()
        }

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

    def contexts(self):
        return NativeRuntimeContexts(
            actor_candidates=lambda p, plan, e, i: tuple(p.actors.values()),
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
        )
