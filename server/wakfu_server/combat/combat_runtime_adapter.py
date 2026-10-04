"""Server adapter for the common native runtime, using live preview snapshots.

Native properties are not inferred from player/NPC IDs. The authority must
supply ff e/Qq metadata, deck/breed/summon context and execution decisions.
Events, cell routing, facing/block, state clocks and healing-resistance guards
remain explicit policies. Unknown fcE/effect flags still fail in the resolver
or handlers. This adapter never sends packets or mutates the original fight.
"""
from dataclasses import dataclass
from .combat_effect_runtime import NativeRuntimeContexts
from .combat_conditions import ConditionContext, ConditionCell
from .combat_damage_handler import _snapshot


@dataclass(frozen=True)
class NativeActorAuthority:
    targeting: dict
    is_player: bool
    deck_spell_ids: frozenset
    excluded_deck_spell_ids: frozenset
    is_carried: bool
    breed_id: int
    summon_count: int
    summon_counts_by_breed: dict
    occupant_blocks: bool
    is_summon: bool | None = None
    summon_root_id: int | None = None


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


class NativeServerRuntimeAdapter:
    """Bind authoritative actor metadata and cast policies to a runtime factory.

    actor_authority(preview, actor) must read current properties (including
    state-driven changes), rather than cache a pre-cast ConditionActor.
    Snapshot statistics, ledger entries and coordinates always come from the
    preview. UID sequence must already have been initialized at placement.
    RNG is owned by the caller's transaction; callers that require RNG rollback
    must clone its state together with the fight before constructing authority.
    """

    def __init__(self, *, actor_authority, cast):
        if not callable(actor_authority) or not isinstance(cast, NativeCastAuthority):
            raise ValueError("Missing authoritative actor/cast provider")
        if any(
            not callable(value)
            for name, value in vars(cast).items()
            if name != "damage_block"
        ) or (cast.damage_block is not None and not callable(cast.damage_block)):
            raise ValueError("Every native cast policy must be explicit")
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
        if (
            type(value.breed_id) is not int
            or type(value.summon_count) is not int
            or value.summon_count < 0
        ):
            raise ValueError("Unknown native breed/summon context")
        if not isinstance(value.targeting, dict):
            raise ValueError("Missing fcE actor metadata")
        return value

    def condition(self, preview, plan, effect, invocation):
        aliases = {}
        for name, identity in (
            ("caster", invocation.caster_id),
            ("target", invocation.target_id),
        ):
            actor = preview.actors.get(identity)
            if actor is None:
                continue
            authority = self._actor(preview, actor)
            from .combat_characteristic_conditions import characteristic_ids

            ids = characteristic_ids()
            affiliation = getattr(actor, "native_fight_affiliation", actor.team)
            if type(affiliation) is not int or not -128 <= affiliation < 128:
                raise ValueError("Missing native signed-byte bcM affiliation")
            from .combat_retained_runtime import native_retained_condition_effects

            try:
                retained_ids = frozenset(
                    row[0]
                    for row in native_retained_condition_effects(preview, actor.id)
                )
            except ValueError:
                # Unverified populations are unknown, never authoritatively empty.
                # Only a condition needing this information rejects the cast.
                retained_ids = None
            aliases[name] = actor.state_ledger.condition_actor(
                is_player=authority.is_player,
                deck_spell_ids=authority.deck_spell_ids,
                excluded_deck_spell_ids=authority.excluded_deck_spell_ids,
                is_carried=authority.is_carried,
                breed_id=authority.breed_id,
                effective_level=actor.effective_level,
                fight_affiliation=affiliation,
                is_native_fighter=authority.targeting.get("is_eGj"),
                # eGj.a(eHh) explicitly identifies CHARACTER. Other native
                # actor implementations need their own kind attestation.
                is_character=True
                if authority.targeting.get("is_eGj") is True
                else None,
                is_summon=authority.is_summon,
                summon_root_id=authority.summon_root_id,
                retained_effect_ids=retained_ids,
                # This entry only attests ordinary actors registered in an
                # active Fight. Other lifecycle contexts need their own proof.
                in_fight=True if preview.phase == "active" else None,
                physical_radius=actor.physical_radius,
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
        distance = (
            None
            if target is None
            else sum(
                max(0, abs(a - b) - source.physical_radius - target.physical_radius)
                for a, b in zip(source.position[:2], target.position[:2])
            )
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
        return ConditionContext(
            aliases,
            cell,
            distance,
            alignment,
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

        if not isinstance(self.actor_authority, OrdinaryActorAuthority):
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
