"""eZl/307 descriptors and a separate registered-summon authority.

OrdinaryActorAuthority remains strict. Summons need an explicit full snapshot,
native properties and timeline insertion result; missing providers are errors.
This module does not invent summon statistics, AI or unsummoning rules.
"""
from dataclasses import dataclass, replace
from collections import Counter
from copy import copy, deepcopy
from .combat_state import Actor
from .combat_runtime_adapter import NativeActorAuthority
from .combat_effects import _integer, _varint


def fresh_summon_slot_owned(preview, actor):
    """QI.f owns slots by registered QK identity, not historical Actor bytes."""
    slots = getattr(preview, "native_qi_slots", None)
    if slots is None:
        # Legacy fixtures have only a complete actor-only registration table.
        return not any(
            a.native_obstacle_id == actor.native_obstacle_id
            for a in preview.actors.values()
        )
    from .combat_qi_registry import NativeQIRegistry

    registry = NativeQIRegistry(
        preview.native_qi_snapshot,
        slots,
        touched_cells=getattr(preview, "native_qi_touched_cells", None),
        byte_topology=getattr(preview, "native_qi_byte_topology", None),
    )
    row = registry.slots[actor.native_obstacle_id]
    return (
        row is not None
        and row["identity"] == ["actor", actor.id]
        and row["position"] == list(actor.position[:2])
        and row["radius"] == actor.physical_radius
    )


def _short(value):
    return (value + 32768) % 65536 - 32768


def _byte(value):
    return (value + 128) % 256 - 128


@dataclass(frozen=True)
class SummonSpecification:
    reference: int
    level: int
    self_controlled: bool
    direction: int
    team: int
    timeline_anchor: str
    timeline_offset: int


def summon_specification(
    effect,
    values,
    *,
    evaluation_level,
    container_present,
    caster_level,
    caster_team,
    caster_direction,
    native_minimum_level
):
    """Exact eZl.C parameters; eHD/SQ defaults are preserved explicitly."""
    if effect["effect_class"] != 307:
        raise ValueError("Expected native summon307")
    p = tuple(values["parameters"])
    if not p or any(type(v) is not int for v in p):
        raise ValueError("Unknown native integer summon parameters")
    reference = _short(p[0])
    level_mode = p[1] if len(p) > 1 else -1
    if level_mode == -1:
        if container_present is not True:
            raise ValueError("Summon level requires its actual container")
        level = evaluation_level
    elif level_mode == -2:
        level = caster_level
    elif level_mode == -3:
        level = native_minimum_level
    elif level_mode > 0:
        level = _short(level_mode)
    else:
        raise ValueError("Invalid native summon level mode")
    if type(level) is not int or not 0 <= level < 32768 or reference <= 0:
        raise ValueError("Missing native summon reference/level")
    direction = p[3] if len(p) > 3 else -1
    # aAS.wL searches the eight planar directions; anything else becomes NONE.
    direction = direction if 0 <= direction <= 7 else caster_direction
    team = _byte(p[4]) if len(p) > 4 else caster_team
    # big creation inherits caster.bcM when eHD.bcM is the native NONE byte.
    if team == -1:
        team = caster_team
    if type(direction) is not int or not 0 <= direction < 8 or team not in (0, 1):
        raise ValueError("Unsupported native summon direction/team")
    anchor = (
        ("current" if p[5] == 0 else "start" if p[5] == 1 else "caster")
        if len(p) > 5
        else "caster"
    )
    return SummonSpecification(
        reference,
        level,
        len(p) > 2 and p[2] >= 1,
        direction,
        team,
        anchor,
        p[6] if len(p) > 6 else 1,
    )


def summon_additional_payload(actor_id):
    """eZl.a(iP): ProtoRunningEffect field12/iR field4 summon UID."""
    if type(actor_id) is not int or not 0 < actor_id < 1 << 63:
        raise ValueError("Missing native PW-owned summon UID")
    child = _integer(4, actor_id)
    return _varint((12 << 3) | 2) + _varint(len(child)) + child


def fresh_summon_insertion(preview, specification, *, caster_id, actor_id):
    """Tc.a(long,short,SQ), fresh UID absent from the initial bsy order.

    Re-inserting an existing UID follows an additional bsy/Td branch and is
    rejected. The current participant keeps its turn after insertion.
    """
    if (
        not isinstance(specification, SummonSpecification)
        or preview.phase != "active"
        or not preview.order
        or (
            len(preview.order) != len(set(preview.order))
            and getattr(preview, "native_base_turn_order", None) is None
        )
        or actor_id in preview.actors
        or actor_id in preview.order
        or caster_id not in preview.actors
        or not 0 <= preview.turn_index < len(preview.order)
    ):
        raise ValueError(
            "Fresh native timeline insertion requires an active owned caster"
        )
    if specification.timeline_anchor == "current":
        base = preview.turn_index
    elif specification.timeline_anchor == "start":
        base = 0
    elif specification.timeline_anchor == "caster":
        base = preview.order.index(caster_id) if caster_id in preview.order else -1
    else:
        raise ValueError("Unknown SQ timeline anchor")
    offset = specification.timeline_offset
    if type(offset) is not int or not -(1 << 31) <= offset < 1 << 31:
        raise ValueError("Invalid native SQ int offset")
    total = (base + offset + (1 << 31)) % (1 << 32) - (1 << 31)
    insertion = total % (len(preview.order) + 1)  # Java Math.floorMod.
    order = list(preview.order)
    order.insert(insertion, actor_id)
    return order, preview.turn_index + (insertion <= preview.turn_index)


@dataclass(frozen=True)
class SummonRegistration:
    actor_id: int
    caster_id: int
    controller_id: int
    authority: NativeActorAuthority
    fight_properties: frozenset
    world_properties: frozenset


class RegisteredSummonAuthority:
    """Compose strict ordinary actors with explicitly registered summon actors.

    Records live in the preview, so cloning/checkpointing preserves ownership.
    Serializing NativeActorAuthority is left to the caller's checkpoint schema;
    only ordinary plain dictionaries are stored here.
    """

    def __init__(self, ordinary):
        self.ordinary = ordinary

    @staticmethod
    def _fresh_relationships(actor, registration, metadata):
        """Attest fdy saH/saJ and fresh pGW/pGV independently; no stale defaults."""
        source = getattr(actor, "native_summon_source", None)
        if (
            not isinstance(source, dict)
            or source.get("native_relation_source")
            != "big.new_bje.fdt_initial_registration"
            or source.get("caster_id") != registration["caster_id"]
            or source.get("controller_id") != registration["controller_id"]
            or source.get("ref") != metadata.breed_id
            or source.get("level") != metadata.native_real_level
            or type(registration["controller_id"]) is not int
            or type(getattr(actor, "native_controller_id", None)) is not int
            or actor.native_controller_id != registration["controller_id"]
            or metadata.native_controller_id != registration["controller_id"]
            or metadata.targeting.get("dpr_id") != registration["controller_id"]
        ):
            raise ValueError("Missing fresh native summon controller provenance")
        if (
            type(getattr(actor, "native_master_id", None)) is not int
            or actor.native_master_id != registration["controller_id"]
            or metadata.targeting.get("dpu_id") != actor.native_master_id
        ):
            raise ValueError(
                "Changed native summon master requires its registration producer"
            )
        if (
            "native_carrier_id" not in vars(actor)
            or "native_carried_actor_id" not in vars(actor)
            or actor.native_carrier_id is not None
            or actor.native_carried_actor_id is not None
            or metadata.is_carried is not False
            or metadata.is_carrying is not False
            or metadata.targeting.get("buX") is not False
        ):
            raise ValueError(
                "Changed native summon physical carry requires its registration producer"
            )
        for snapshot in (actor.spell_ap_cost_modifiers, actor.spell_range_modifiers):
            if not isinstance(snapshot, dict) or any(
                type(key) is not int or type(value) is not int
                for key, value in snapshot.items()
            ):
                raise ValueError(
                    "Missing complete native summon category modifier snapshot"
                )

    def register(self, preview, actor, registration, *, new_order, new_turn_index):
        if (
            preview.phase != "active"
            or not isinstance(actor, Actor)
            or not isinstance(registration, SummonRegistration)
            or actor.id != registration.actor_id
            or actor.id in preview.actors
            or actor.id <= 0
            or registration.caster_id not in preview.actors
            or registration.controller_id not in (*preview.actors, actor.id)
            or actor.position not in preview.walkable
        ):
            raise ValueError("Invalid owned summon registration")
        # Native big.a/fdt registers QK identities even at a shared cell.
        # Spell criteria own placement legality; creation can precede a carry
        # transition in the same ordered group. Validate its exact QI slot
        # below instead of imposing an additional living-cell restriction.
        metadata = registration.authority
        self._fresh_relationships(actor, vars(registration), metadata)
        if (
            metadata.is_summon is not True
            or metadata.summon_root_id is None
            or metadata.is_player is not False
            or metadata.is_carried is not False
            or metadata.targeting.get("bcN") != actor.native_obstacle_id
            or type(actor.native_obstacle_id) is not int
            or not 0 <= actor.native_obstacle_id <= 126
            or not fresh_summon_slot_owned(preview, actor)
            or actor.effect_stats is None
            or actor.effect_maxima is None
            or actor.effect_minima is None
            or actor.effect_frozen is None
            or actor.physical_radius is None
            or actor.spell_ap_cost_modifiers is None
            or actor.spell_range_modifiers is None
        ):
            raise ValueError("Summon requires complete native actor authority/snapshot")
        # fbX.C consults ffe114 NOT_PRESENT_IN_TIMELINE before fem.a.
        expected = Counter(preview.order)
        if 114 not in registration.fight_properties:
            expected[actor.id] += 1
        if (
            Counter(new_order) != expected
            or type(new_turn_index) is not int
            or not 0 <= new_turn_index < len(new_order)
            or new_order[new_turn_index] != preview.current.id
        ):
            raise ValueError(
                "Missing native timeline insertion preserving current actor"
            )
        controller = (
            actor
            if registration.controller_id == actor.id
            else preview.actors[registration.controller_id]
        )
        if (
            actor.controlled != controller.controlled
            or actor.owner_id != controller.owner_id
        ):
            raise ValueError("Summon controller/account mismatch")
        base_order = getattr(preview, "native_base_turn_order", None)
        next_base = None
        if base_order is not None:
            # Tc.pw counts duplicate IDs before the current-round insertion.
            # SX.n/feq.b insert into the base list at slot minus that count.
            if (
                getattr(preview, "native_timeline_policy", None) != "feq"
                or len(base_order) != len(set(base_order))
                or set(base_order) != set(preview.order)
            ):
                raise ValueError("Missing native extra-turn base timeline authority")
            next_base = list(base_order)
            if 114 not in registration.fight_properties:
                slot = list(new_order).index(actor.id)
                prefix = preview.order[:slot]
                base_slot = slot - (len(prefix) - len(set(prefix)))
                next_base.insert(base_slot, actor.id)
        row = dict(vars(registration))
        row["authority"] = dict(vars(metadata))
        records = getattr(preview, "native_summon_registrations", {})
        if actor.id in records:
            raise ValueError("Duplicate summon registration")
        if 114 not in registration.fight_properties:
            from .combat_timeline_snapshot import insert

            insert(preview, actor.id, list(new_order).index(actor.id))
        preview.actors[actor.id] = actor
        if hasattr(preview, "native_global_pv_collections"):
            from .combat_global_pv_collections import register_global_fighter

            register_global_fighter(
                preview, actor.id, controller_id=registration.controller_id
            )
        preview.native_summon_registrations = {**records, actor.id: row}
        preview.order, preview.turn_index = list(new_order), new_turn_index
        if next_base is not None:
            preview.native_base_turn_order = next_base

    def retire(self, preview, actor_id, *, new_order, new_turn_index):
        """Retire an already-dead owned summon after native timeline cleanup.

        eZl.bbF clears its descriptors, NOT the creature. Live unsummoning
        requires a different proven effect/lifecycle and is deliberately absent.
        """
        records = getattr(preview, "native_summon_registrations", {})
        actor = preview.actors.get(actor_id)
        if actor_id not in records or actor is None or actor.hp > 0:
            raise ValueError("Live or unregistered summon cannot be retired")
        if (
            set(new_order) != set(preview.order) - {actor_id}
            or len(new_order) != len(set(new_order))
            or not new_order
            or type(new_turn_index) is not int
            or not 0 <= new_turn_index < len(new_order)
        ):
            raise ValueError("Missing native post-death timeline")
        # Keep the actor and ownership record: late native effect removals and
        # corpse-target predicates still need the original identity.
        row = dict(records[actor_id])
        row["retired"] = True
        preview.native_summon_registrations = {**records, actor_id: row}
        preview.order, preview.turn_index = list(new_order), new_turn_index

    def _ordinary_view(self, preview):
        records = getattr(preview, "native_summon_registrations", {})
        if any(
            i not in preview.actors or row["actor_id"] != i
            for i, row in records.items()
        ):
            raise ValueError("Stale summon roster registration")
        view = copy(preview)
        view.actors = {i: a for i, a in preview.actors.items() if i not in records}
        return view

    def _call_ordinary(self, preview, callback, *args):
        from .combat_carrying import carry_population_scope

        # Keep the ordinary ownership roster strict, while reciprocal physical
        # relations still resolve both actors from the real transaction.
        with carry_population_scope(preview):
            return callback(self._ordinary_view(preview), *args)

    def __call__(self, preview, actor):
        from .combat_native_actor_lookup import detached_authority

        construction = detached_authority(preview, actor)
        if construction is not None:
            return construction
        if preview.actors.get(actor.id) is not actor:
            raise ValueError("Actor does not belong to this preview")
        if getattr(actor, "pve_withdrawn", False):
            raise ValueError("Withdrawn PvE actor has no active summon authority")
        records = getattr(preview, "native_summon_registrations", {})
        if actor.id in records:
            registration = records[actor.id]
            if registration.get("actor_id") != actor.id:
                raise ValueError("Stale native summon actor registration")
            metadata = NativeActorAuthority(**registration["authority"])
            # Verify original controller/master creation facts independently of
            # source-proven physical carrying changes installed afterwards.
            from .combat_carrying import carrying_relations

            carrying = carrying_relations(preview, actor)
            if any(carrying.values()):
                original = copy(actor)
                original.native_carrier_id = None
                original.native_carried_actor_id = None
                self._fresh_relationships(original, registration, metadata)
            else:
                self._fresh_relationships(actor, registration, metadata)
            targeting = dict(metadata.targeting)
            targeting["buX"] = carrying["is_carried"]
            metadata = replace(
                metadata,
                targeting=targeting,
                is_carried=carrying["is_carried"],
                is_carrying=carrying["is_carrying"],
            )
            from .combat_summon_spellbook import actor_spellbook

            from .combat_spell_grant_book import merged_grant_book
            from .combat_morph_spellbook import active_morph_book

            ai_control = getattr(actor, "native_controlled_by_ai", None)
            if ai_control is not None and type(ai_control) is not bool:
                raise ValueError("Invalid native summon AI control flag")
            metadata = replace(
                metadata,
                native_spellbook=merged_grant_book(
                    preview,
                    actor.id,
                    active_morph_book(preview, actor.id, actor_spellbook(actor)),
                ),
                native_controlled_by_ai=ai_control,
            )
            if registration["controller_id"] not in preview.actors:
                raise ValueError("Native summon controller no longer registered")
        else:
            from .combat_carrying import carry_population_scope

            with carry_population_scope(preview):
                metadata = self.ordinary(self._ordinary_view(preview), actor)
        # dTB/GF eligibility is an explicit native provider, not merely the
        # number of registrations: statuses/properties may exclude summons.
        if records:
            metadata = replace(
                metadata,
                summon_count=None,
                summon_counts_by_breed=None,
                native_summon_counts_complete=False,
            )
            from .combat_summon_count import registered_summon_counts

            from .combat_carrying import carry_population_scope

            with carry_population_scope(preview):
                counts = registered_summon_counts(
                    preview,
                    actor.id,
                    records,
                    self.ordinary,
                    self._ordinary_view(preview),
                )
            if counts is not None:
                metadata = replace(
                    metadata,
                    summon_count=counts[0],
                    summon_counts_by_breed=counts[1],
                    native_summon_counts_complete=True,
                )
        from .combat_ordinary_death import owned_fighter_guards

        life = owned_fighter_guards(preview, actor)
        from .combat_controller_registry import current_controller_authority

        metadata = current_controller_authority(preview, actor, metadata)
        return replace(
            metadata,
            targeting={**metadata.targeting, **life},
            native_in_play=life["baF"],
        )

    def item_quantity(self, preview, actor, references):
        self(preview, actor)
        records = getattr(preview, "native_summon_registrations", {})
        if actor.id in records:
            raise ValueError("Missing native summoned inventory authority")
        return self._call_ordinary(
            preview, self.ordinary.item_quantity, actor, references
        )

    def property_counts(self, preview, actor):
        self(preview, actor)
        from .combat_native_actor_lookup import detached_authority

        if detached_authority(preview, actor) is not None:
            from .combat_property_stack import property_present

            counts = getattr(actor, "native_fight_property_counts", None)
            property_present(counts, 0)
            return counts
        records = getattr(preview, "native_summon_registrations", {})
        if actor.id in records:
            counts = getattr(actor, "native_fight_property_counts", None)
            if counts is None:
                raise ValueError("Missing native summoned property counter snapshot")
            return counts
        return self._call_ordinary(preview, self.ordinary.property_counts, actor)

    def property_side_effect(self, preview, actor, identity, *, applying):
        records = getattr(preview, "native_summon_registrations", {})
        if actor.id in records:
            raise ValueError("Native summoned property callbacks remain unaudited")
        # Use the actual preview, not the roster-filtered view: timeline writes
        # belong to the same transaction. Ordinary __call__ rejects extra actors.
        if records:
            raise ValueError("Combined property/summon callbacks remain unaudited")
        return self.ordinary.property_side_effect(
            preview, actor, identity, applying=applying
        )

    def world_property_counts(self, preview, actor):
        from .combat_native_actor_lookup import detached_authority
        from .combat_property_stack import property_present

        if detached_authority(preview, actor) is not None or actor.id in getattr(
            preview, "native_summon_registrations", {}
        ):
            counts = getattr(actor, "native_world_property_counts", None)
            property_present(counts, 0)
            return counts
        self(preview, actor)
        return self._call_ordinary(preview, self.ordinary.world_property_counts, actor)

    def properties(self, preview, actor):
        from .combat_native_actor_lookup import detached_authority

        if detached_authority(preview, actor) is not None:
            live = getattr(actor, "native_fight_properties", None)
            if live is None:
                raise ValueError("Missing detached native fight-property source")
            return frozenset(live)
        self(preview, actor)
        records = getattr(preview, "native_summon_registrations", {})
        if actor.id in records:
            live = getattr(actor, "native_fight_properties", None)
            counts = getattr(actor, "native_fight_property_counts", None)
            if live is not None or counts is not None:
                from .combat_property_stack import property_present

                property_present(counts, 0)
                current = frozenset(k for k, value in counts.items() if value != 0)
                if live != current:
                    raise ValueError("Inconsistent native summoned property snapshot")
                # PB changes after construction, including retained eWt removal.
                # The registration stores the original descriptor, not live PB.
                return current
        return (
            records[actor.id]["fight_properties"]
            if actor.id in records
            else self._call_ordinary(preview, self.ordinary.properties, actor)
        )

    def world_properties(self, preview, actor):
        from .combat_native_actor_lookup import detached_authority

        if detached_authority(preview, actor) is not None:
            live = getattr(actor, "native_world_properties", None)
            if live is None:
                raise ValueError("Missing detached native world-property source")
            return frozenset(live)
        self(preview, actor)
        records = getattr(preview, "native_summon_registrations", {})
        return (
            records[actor.id]["world_properties"]
            if actor.id in records
            else self._call_ordinary(preview, self.ordinary.world_properties, actor)
        )


def prepare_summon(
    fight,
    specification,
    *,
    caster_id,
    cell,
    authority,
    allocate_actor_uid,
    build_native_actor,
    encode_application
):
    """Prepare a registered summon on a private preview; no partial commit.

    Providers receive this SAME preview. Actor builder must include eHD's
    post-creation transforms; encoder must produce the actual307 application.
    Until those native providers exist, their absence rejects the transaction.
    """
    if (
        not isinstance(authority, RegisteredSummonAuthority)
        or not isinstance(specification, SummonSpecification)
        or any(
            not callable(p)
            for p in (allocate_actor_uid, build_native_actor, encode_application)
        )
    ):
        raise ValueError("Missing native summon creation/application authority")
    preview = deepcopy(fight)
    if (
        preview.phase != "active"
        or caster_id not in preview.actors
        or preview.actors[caster_id].hp <= 0
        or cell not in preview.walkable
    ):
        raise ValueError("Invalid native summon caster/cell")
    identity = allocate_actor_uid(preview)
    summon_additional_payload(identity)  # Native signed long validation.
    actor, registration = build_native_actor(
        preview, specification, caster_id, identity, cell
    )
    if (
        not isinstance(actor, Actor)
        or actor.id != identity
        or actor.position != cell
        or actor.team != specification.team
        or actor.effective_level != specification.level
        or not isinstance(registration, SummonRegistration)
        or registration.caster_id != caster_id
        or registration.controller_id
        != (identity if specification.self_controlled else caster_id)
    ):
        raise ValueError("Native summon builder disagrees with eZl descriptor")
    order, turn_index = (
        (list(preview.order), preview.turn_index)
        if 114 in registration.fight_properties
        else fresh_summon_insertion(
            preview, specification, caster_id=caster_id, actor_id=identity
        )
    )
    authority.register(
        preview, actor, registration, new_order=order, new_turn_index=turn_index
    )
    packets = tuple(encode_application(preview, specification, registration, cell))
    if not packets or any(
        not isinstance(p, tuple)
        or len(p) != 2
        or type(p[0]) is not int
        or not isinstance(p[1], bytes)
        for p in packets
    ):
        raise ValueError("Missing native summon application packets")
    return preview, packets


def ordinary_roster_authority(authority):
    """Recognize exact ordinary creation behind our explicit registration wrapper."""
    from .combat_ordinary_authority import OrdinaryActorAuthority

    return isinstance(authority, OrdinaryActorAuthority) or (
        isinstance(authority, RegisteredSummonAuthority)
        and isinstance(authority.ordinary, OrdinaryActorAuthority)
    )
