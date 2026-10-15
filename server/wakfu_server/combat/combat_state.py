"""Authoritative fight state, independent of packets, spell effects and AI.

Terrain cells and transitions must be validated against client map geometry by
caller. Actor control is explicit; signed identifiers never imply ownership.
"""
from dataclasses import dataclass, field
from contextlib import contextmanager
from .combat_turns import initial_order
from .combat_state_ledger import StateLedger


@dataclass
class Actor:
    id: int
    team: int
    position: tuple
    hp: int
    ap: int
    mp: int
    initiative: int
    effective_level: int
    owner_id: int | None = None
    controlled: bool = False
    turn_count: int = field(default=0, init=False)
    max_hp: int | None = None
    max_ap: int = field(init=False)
    max_mp: int = field(init=False)
    state_ledger: StateLedger = field(init=False, repr=False)
    # Complete native snapshots, populated by runtime; None means unknown.
    effect_stats: dict | None = None
    effect_maxima: dict | None = None
    effect_minima: dict | None = None
    effect_frozen: frozenset | None = None
    # Native eGj.frM()->eHl.pOJ; None is unknown/restored without snapshot.
    # Initialized only for a verified fresh actor before passive execution.
    spell_ap_cost_modifiers: dict | None = None
    # Native eHl.pOK category range offsets; absent authority is not zero.
    spell_range_modifiers: dict | None = None
    physical_radius: int | None = None
    native_physical_position: tuple | None = None  # Actual eGj.efR/pGF snapshot.
    native_jump_height: int | None = None  # Actual eGj.bvz; unknown is not zero.
    native_obstacle_id: int | None = None  # QK.bcN byte, distinct from fcb team/bcM.
    native_los_height: int | None = (
        None  # Exact eGH.bcK creation profile; unknown is not zero.
    )
    # Exact facing included in the native actor bootstrap. Fresh actor
    # serializers emit direction 0 unless a creation path supplies another
    # native direction; keeping it in the FSM makes that transmitted state
    # authoritative for orientation-dependent effects and checkpoints.
    direction: int = 0
    native_controlled_by_ai: bool | None = (
        None  # eGz.pHH via exact po.SX actor bootstrap.
    )
    native_death_script_id: int | None = (
        None  # eGj.pGU; absent restored authority is unknown.
    )
    native_turn_suppression_bits: int | None = (
        None  # eGj.frN/pGO; fresh snapshot initializes it.
    )

    def __post_init__(self):
        if any(
            type(n) is not int
            for n in (
                self.id,
                self.team,
                self.hp,
                self.ap,
                self.mp,
                self.initiative,
                self.effective_level,
            )
        ):
            raise ValueError("Actor fields must be integers")
        if self.team not in (0, 1) or self.hp <= 0 or self.ap < 0 or self.mp < 0:
            raise ValueError("Invalid actor team or resources")
        if self.controlled and (type(self.owner_id) is not int or self.owner_id <= 0):
            raise ValueError("Controlled actor needs an owner")
        if len(self.position) != 3 or any(type(n) is not int for n in self.position):
            raise ValueError("Invalid actor position")
        if type(self.direction) is not int or not 0 <= self.direction < 8:
            raise ValueError("Invalid native actor direction")
        if self.max_hp is None:
            self.max_hp = self.hp
        if type(self.max_hp) is not int or self.max_hp < self.hp:
            raise ValueError("Maximum HP is below current HP")
        self.max_ap, self.max_mp = self.ap, self.mp
        self.state_ledger = StateLedger(self.id)


class Fight:
    def __init__(self, fight_id, actors, walkable, placement_cells, valid_edges=None):
        actors = list(actors)
        self.actors = {a.id: a for a in actors}
        if len(self.actors) != len(actors) or {a.team for a in actors} != {0, 1}:
            raise ValueError("Fight requires unique actors on both teams")
        from .combat_obstacle_ids import assign_obstacle_ids

        assign_obstacle_ids(actors)
        # Explicit new-fight boundary, consumed after ordinary creation
        # snapshots and serialized arena masks have both been installed.
        self.native_qi_slots = None
        self.native_qi_movement_override = False  # Fresh QI.biP constructor.
        self.native_qi_ignored_slots = []  # Fresh QI.biN constructor.
        self.native_qi_visibility_ignored_slots = []  # Fresh QI.biO constructor.
        self.native_qi_fresh_actor_order = tuple(a.id for a in actors)
        initial_order(
            fight_id,
            [
                dict(
                    id=a.id,
                    team=a.team,
                    initiative=a.initiative,
                    effective_level=a.effective_level,
                )
                for a in actors
            ],
        )
        self.id = fight_id
        # Wakemu's fresh ordinary fight policy is native fcz.PVE (eSS = 2).
        # Placement serialization replaces this with its exact selected model.
        self.native_fight_model = 2
        from .combat_system_conditions import fresh_system_configuration

        self.native_system_configuration = fresh_system_configuration()
        self.walkable = set(walkable)
        self.placement = {team: set(cells) for team, cells in placement_cells.items()}
        if set(self.placement) != {0, 1} or any(
            not cells or not cells <= self.walkable for cells in self.placement.values()
        ):
            raise ValueError("Invalid placement terrain")
        self.edges = None if valid_edges is None else set(valid_edges)
        self.phase = "placement"
        self.native_spell_usage = {}
        from .combat_ai_cast_history import fresh_history

        self.wakemu_ai_cast_history = fresh_history()
        self.native_start_event_delivered = False
        self.native_turn_event_deliveries = {}
        self.native_table_turn = (
            0  # SU initial timeline before native13477 starts round1.
        )
        self.native_timeline_round = (
            0  # SU.brM; advances on complete cycles, not activations.
        )
        self.winner = None
        self.native_los_ignored_affiliations = frozenset()  # QI.biO freshly empty.
        self.native_walk_ignored_affiliations = frozenset()  # QI.biN freshly empty.
        self.native_timeline_policy = "feq"  # initial_order is the native feq policy.
        self.native_base_turn_order = None
        self.order = []
        self.turn_index = 0
        self.turn_id = 0
        self.ready_owners = set()
        self.events = []
        self._resolution_depth = 0
        self.sequence = 0
        self.native_effect_uid_next = (
            None  # Authoritative runtime initializes the owned UID sequence.
        )
        self.native_owned_area_effects = {}
        self.native_owned_spatial_effects = {}
        self.native_effect_areas = {}  # Fresh native Qs has no registered areas.
        # Plain, source-tagged records for the Wakemu settled-summon OUT_OF_PLAY
        # policy. Native actor identity and fdt membership remain intact.
        self.native_summon_retirements = {}
        self.native_owned_group_effects = {}
        from .combat_native_delay_queue import fresh_queue

        self.native_delay_queue = fresh_queue()  # Actual fresh SU/TC constructor.
        self.native_retained_records = {}
        self.native_owned_state_containers = (
            {}
        )  # Actual PL facts held by retained children.
        self.native_retained_order = []
        self.native_retained_tracking = not any(a.state_ledger.entries for a in actors)
        self.owned_stat_effects = {}
        self.native_retired_area_managers = {}  # Actual removed Qq/Qf objects.
        self.native_active_spell_id = None  # Fresh fight: native PZ absent.
        self.native_spell_grants = {}  # Native temporary fyR spell UID pool.
        self.state_wire_payloads = {}  # UID -> original owned carrier payload hex
        self._check_positions()

    def allocate_effect_uid(self):
        """Allocate only from this fight's initialized, checkpointed sequence."""
        uid = self.native_effect_uid_next
        if type(uid) is not int or not 0 < uid < (1 << 63) - 1:
            raise ValueError("Native effect UID sequence is missing or exhausted")
        occupied = (
            set(self.state_wire_payloads)
            | set(self.owned_stat_effects)
            | set(self.native_owned_group_effects)
            | set(getattr(self, "native_owned_area_effects", {}))
            | set(getattr(self, "native_owned_spatial_effects", {}))
            | set(getattr(self, "native_effect_areas", {}))
            | set(getattr(self, "native_retired_area_managers", {}))
        )
        occupied.update(
            entry.uid
            for actor in self.actors.values()
            for entry in actor.state_ledger.entries
        )
        if uid in occupied:
            raise ValueError("Native effect UID sequence collides with an owned effect")
        self.native_effect_uid_next = uid + 1
        return uid

    def allocate_area_uid(self):
        """Allocate a Qq PV identity without aliasing a fighter's Sn().

        Running effects may share a numeric identity with a fighter. Areas
        are PVs too, so their separate native PW.baj allocation cannot.
        """
        uid = self.native_effect_uid_next
        if type(uid) is not int or not 0 < uid < (1 << 63) - 1:
            raise ValueError("Native effect UID sequence is missing or exhausted")
        pvs = (
            set(self.actors)
            | set(self.native_effect_areas)
            | set(self.native_retired_area_managers)
        )
        pvs.update(
            row["area_uid"]
            for row in self.native_owned_area_effects.values()
            if isinstance(row, dict) and type(row.get("area_uid")) is int
        )
        while uid in pvs:
            uid += 1
            if uid >= (1 << 63) - 1:
                raise ValueError("Native area PV UID sequence is exhausted")
        previous = self.native_effect_uid_next
        self.native_effect_uid_next = uid
        try:
            return self.allocate_effect_uid()
        except Exception:
            self.native_effect_uid_next = previous
            raise

    def _check_positions(self):
        positions = [a.position for a in self.actors.values() if a.hp > 0]
        if len(set(positions)) != len(positions) or any(
            a.position not in self.placement[a.team] for a in self.actors.values()
        ):
            raise ValueError("Actor placement is occupied or outside team area")

    def _event(self, kind, **fields):
        self.sequence += 1
        event = dict(sequence=self.sequence, kind=kind, **fields)
        self.events.append(event)
        return event

    def _in_play(self, actor):
        if hasattr(self, "native_global_pv_collections"):
            from .combat_global_pv_collections import global_fighter_participates

            return global_fighter_participates(self, actor.id)
        return actor.hp > 0

    def _owned(self, owner_id, actor_id):
        actor = self.actors.get(actor_id)
        if (
            actor is None
            or not actor.controlled
            or actor.owner_id != owner_id
            or not self._in_play(actor)
        ):
            raise ValueError("Actor is not controlled by this owner")
        return actor

    @property
    def current(self):
        return (
            self.actors[self.order[self.turn_index]] if self.phase == "active" else None
        )

    def place(self, owner_id, actor_id, position):
        if self.phase != "placement":
            raise ValueError("Placement has ended")
        actor = self._owned(owner_id, actor_id)
        position = tuple(position)
        if owner_id in self.ready_owners or position not in self.placement[actor.team]:
            raise ValueError("Placement is ready or outside team area")
        if any(
            a.id != actor_id and a.hp > 0 and a.position == position
            for a in self.actors.values()
        ):
            raise ValueError("Placement cell occupied")
        from .combat_qi_fight import move_registered_actor

        move_registered_actor(self, actor, position)
        return self._event("placement", actor_id=actor_id, position=position)

    def ready(self, owner_id, ready=True):
        if self.phase != "placement":
            raise ValueError("Placement has ended")
        owners = {a.owner_id for a in self.actors.values() if a.controlled}
        if owner_id not in owners:
            raise ValueError("Owner is not a participant")
        if ready:
            self.ready_owners.add(owner_id)
        else:
            self.ready_owners.discard(owner_id)
        event = self._event("ready", owner_id=owner_id, ready=bool(ready))
        if owners <= self.ready_owners:
            # Native property114 actors remain in QI/the roster, without turns.
            self.order = initial_order(
                self.id,
                [
                    dict(
                        id=a.id,
                        team=a.team,
                        initiative=a.initiative,
                        effective_level=a.effective_level,
                    )
                    for a in self.actors.values()
                    if 114 not in getattr(a, "native_fight_properties", ())
                ],
            )
            from .combat_timeline_snapshot import initialize

            initialize(self, self.order)
            self.phase = "active"
            self.turn_id = 1
            self._begin_turn()
        return event

    @staticmethod
    def _sync_resources(actor):
        if actor.effect_stats is not None:
            for stat, value in ((1, actor.hp), (2, actor.ap), (3, actor.mp)):
                if stat in actor.effect_stats:
                    actor.effect_stats[stat] = value

    def _refill_turn_resources(self, actor):
        """Server policy: refill AP/MP after a completed turn or resurrection.

        This is an explicit server scheduling policy, not a recovered native
        refill producer. Successful resurrection restores one action budget before later external
        losses; turn start never refreshes it again. HP/WP and maxima remain
        effect-driven.
        """
        if getattr(actor, "effect_resource_raw_currents", None) is not None:
            from .combat_resource_pa_notifications import set_resource_current

            set_resource_current(self, actor, 2, actor.max_ap)
            set_resource_current(self, actor, 3, actor.max_mp)
        else:
            before_ap = actor.ap
            actor.ap = actor.max_ap
            if actor.effect_stats is not None and 2 in actor.effect_stats:
                actor.effect_stats[2] = actor.ap
            from .combat_resource_pa_notifications import notify_resource_pa

            notify_resource_pa(self, actor, 2, before_current=before_ap)
            actor.mp = actor.max_mp
        self._sync_resources(actor)

    def _begin_turn(self):
        actor = self.current
        self._sync_resources(actor)
        actor.turn_count += 1
        if self.native_timeline_round == 0:
            self.native_timeline_round = 1  # First SU.bhP enters round1.
        from .combat_initial_finite_clock_policy import bind_initial_finite_clocks

        bind_initial_finite_clocks(self)
        self._event(
            "turn_started",
            actor_id=actor.id,
            turn_id=self.turn_id,
            actor_turn=actor.turn_count,
        )

    def _current_owned(self, owner_id, actor_id):
        from .combat_effective_control import require_effective_owner

        actor = self.actors.get(actor_id)
        if actor is None or not self._in_play(actor):
            raise ValueError("Actor is not controlled by this owner")
        require_effective_owner(self, actor, owner_id)
        if self.current is None or self.current.id != actor_id:
            raise ValueError("Actor does not have the turn")
        return actor

    def spend(self, owner_id, actor_id, ap=0, mp=0):
        actor = self._current_owned(owner_id, actor_id)
        if (
            type(ap) is not int
            or type(mp) is not int
            or min(ap, mp) < 0
            or actor.ap < ap
            or actor.mp < mp
        ):
            raise ValueError("Insufficient or invalid action resources")
        if getattr(actor, "effect_resource_raw_currents", None) is not None:
            from .combat_resource_pa_notifications import shift_resource_current

            shift_resource_current(self, actor, 2, ap, subtract=True)
            shift_resource_current(self, actor, 3, mp, subtract=True)
        else:
            before_ap = actor.ap
            actor.ap -= ap
            if actor.effect_stats is not None and 2 in actor.effect_stats:
                actor.effect_stats[2] = actor.ap
            from .combat_resource_pa_notifications import notify_resource_pa

            notify_resource_pa(self, actor, 2, before_current=before_ap)
            actor.mp -= mp
        self._sync_resources(actor)

    def move(self, owner_id, actor_id, path, *, step_callback=None):
        actor = self._current_owned(owner_id, actor_id)
        path = [tuple(cell) for cell in path]
        if any(
            len(cell) != 3 or any(type(n) is not int for n in cell) for cell in path
        ):
            raise ValueError("Invalid path coordinates")
        return self._move_actor(actor, path, step_callback=step_callback)

    def server_move(self, actor_id, path, *, step_callback=None):
        from .combat_effective_control import effective_server_controlled

        actor = self.current
        if (
            actor is None
            or actor.id != actor_id
            or not effective_server_controlled(self, actor)
            or not self._in_play(actor)
        ):
            raise ValueError("Invalid server controlled movement")
        path = [tuple(cell) for cell in path]
        if any(
            len(cell) != 3 or any(type(n) is not int for n in cell) for cell in path
        ):
            raise ValueError("Invalid path coordinates")
        return self._move_actor(actor, path, step_callback=step_callback)

    def _move_actor(self, actor, path, *, step_callback=None):
        actor_id = actor.id
        origin = actor.position
        cost = 0
        from .combat_qi_movement import movement_blocked_cells

        qi_blocked = movement_blocked_cells(self, actor, path)
        occupied = (
            None
            if qi_blocked is not None
            else {
                a.position
                for a in self.actors.values()
                if a.id != actor_id and a.hp > 0
            }
        )
        for target in path:
            step = abs(target[0] - origin[0]) + abs(target[1] - origin[1])
            if (
                len(target) != 3
                or target not in self.walkable
                or (occupied is not None and target in occupied)
                or (qi_blocked is not None and target in qi_blocked)
                or step != 1
            ):
                raise ValueError("Invalid combat movement path")
            if self.edges is not None and (origin, target) not in self.edges:
                raise ValueError("Terrain transition is not walkable")
            if self.edges is None and target[2] != origin[2]:
                raise ValueError("Altitude transition requires validated terrain edge")
            cost += step
            origin = target
        from .combat_rail_movement import movement_cost
        from .combat_tackle_movement import movement_tackle_cost

        cost, on_rails = movement_cost(self, actor, path)
        tackle_ap, tackle_mp = (
            movement_tackle_cost(self, actor, path) if path else (0, 0)
        )
        cost += tackle_mp
        if not path or cost > actor.mp or tackle_ap > actor.ap:
            raise ValueError("Empty path or insufficient AP/MP for combat movement")
        if step_callback is not None:
            from .combat_sequential_movement import execute_steps

            return execute_steps(
                self, actor, path, on_rails=on_rails, callback=step_callback
            )
        if getattr(actor, "effect_resource_raw_currents", None) is not None:
            from .combat_resource_pa_notifications import (
                shift_resource_current,
                resource_shift_result,
            )

            # Validate both PA mutations before the first notification or write.
            if tackle_ap:
                resource_shift_result(actor, 2, tackle_ap, subtract=True)
            resource_shift_result(actor, 3, cost, subtract=True)
            if tackle_ap:
                shift_resource_current(self, actor, 2, tackle_ap, subtract=True)
            shift_resource_current(self, actor, 3, cost, subtract=True)
        else:
            actor.ap -= tackle_ap
            actor.mp -= cost
        self._sync_resources(actor)
        from .combat_qi_fight import move_registered_actor

        move_registered_actor(self, actor, origin)
        return self._event(
            "movement",
            actor_id=actor_id,
            path=path,
            cost=cost,
            **(
                {"tackle_ap": tackle_ap, "tackle_mp": tackle_mp}
                if tackle_ap or tackle_mp
                else {}
            ),
            **({"on_rails": True} if on_rails else {}),
        )

    def end_turn(self, owner_id, actor_id, turn_id):
        actor = self._current_owned(owner_id, actor_id)
        if turn_id != actor.turn_count:
            raise ValueError("Stale turn identifier")
        self._advance()

    def end_server_turn(self, actor_id, turn_id):
        from .combat_effective_control import effective_server_controlled

        if (
            self.current is None
            or self.current.id != actor_id
            or not effective_server_controlled(self, self.current)
            or turn_id != self.turn_id
        ):
            raise ValueError("Invalid server controlled turn")
        self._advance()

    def _advance(self):
        from .combat_timeline_snapshot import end_current

        # Runtime end reactions and native expiry finish before _advance.
        # Refill the completed actor before another actor can mutate its budget.
        self._refill_turn_resources(self.current)
        end_current(self)
        self._event("turn_ended", actor_id=self.current.id, turn_id=self.turn_id)
        next_index = (self.turn_index + 1) % len(self.order)
        if next_index == 0:
            self.native_timeline_round += 1  # SU.bhO/bhP, including extra-turn cycles.
        if (
            next_index == 0
            and getattr(self, "native_base_turn_order", None) is not None
        ):
            # Tc.bhP -> SX.bid -> feq.b restores the base list each round.
            self.order = [
                uid
                for uid in self.native_base_turn_order
                if self._in_play(self.actors[uid])
            ]
            self.native_base_turn_order = None
        self.turn_index = next_index
        self.turn_id += 1
        if getattr(self, "rift_wave_state", None) is not None:
            from .rift_combat_adapter import finish_survival

            if finish_survival(self):
                return
        if next_index == 0 and getattr(self, "boss_score_profile", None) is not None:
            from wakfu_server.maps.boss_score_runtime import finish_survival

            if finish_survival(self):
                return
        self._begin_turn()

    def apply_damage(self, source_id, target_id, amount):
        """Trusted effect executor only: caller validates spell, AP and targeting."""
        if (
            self.current is None
            or self.current.id != source_id
            or type(amount) is not int
            or amount < 0
        ):
            raise ValueError("Invalid damage source or amount")
        return self.apply_effect_damage(source_id, target_id, amount)

    def apply_effect_damage(
        self,
        source_id,
        target_id,
        amount,
        *,
        native_runner_effect=None,
        native_death_delivery=None,
    ):
        """Trusted dispatched effect, including reactions outside source's turn.

        The dispatcher validates the trigger, ownership and native eligibility.
        Player requests continue through apply_damage's current-turn guard.
        """
        if (
            self.phase != "active"
            or self.current is None
            or source_id not in self.actors
            or type(amount) is not int
            or amount < 0
        ):
            raise ValueError("Invalid dispatched damage context")
        target = self.actors.get(target_id)
        if target is None:
            raise ValueError("Target is not alive")
        if target.hp <= 0:
            if native_runner_effect is None:
                raise ValueError("Target is not alive")
            from .combat_runner_target_life import verify_runner_target_life

            verify_runner_target_life(self, target, native_runner_effect)
        before_hp = target.hp
        from .combat_hp_raw import hp_raw_present, shift_hp_raw_current

        if hp_raw_present(target):
            dealt = shift_hp_raw_current(target, amount, subtract=True)
        else:
            dealt = min(target.hp, amount)
            target.hp -= dealt
        self._sync_resources(target)
        self._event(
            "damage",
            source_id=source_id,
            target_id=target_id,
            amount=dealt,
            hp=target.hp,
        )
        if before_hp > 0 and target.hp == 0:
            self._event("death", actor_id=target_id)
            if hasattr(self, "native_global_pv_collections"):
                from .combat_global_pv_collections import set_global_fighter_status

                set_global_fighter_status(self, target_id, "OFF_PLAY")
            if native_death_delivery is not None:
                native_death_delivery(target_id)
            if not self._resolution_depth:
                self._settle_deaths()
        return dealt

    @contextmanager
    def effect_resolution(self):
        """Defer turn/result reconciliation until the outer effect chain ends.

        Use on a transaction preview: an exception discards that preview.
        This boundary does not grant eligibility to effects from dead actors.
        """
        self._resolution_depth += 1
        try:
            yield
        finally:
            self._resolution_depth -= 1
            if self._resolution_depth == 0 and self.phase == "active":
                self._settle_deaths()

            if self._resolution_depth == 0:
                from .combat_hud_resource import sync_hud_resources

                sync_hud_resources(self)

    def _settle_deaths(self):
        from .combat_summon_retirement import settle_summon_retirements

        from .combat_timeline_snapshot import remove

        for identity in tuple(dict.fromkeys(self.order)):
            if not self._in_play(self.actors[identity]):
                remove(self, identity)
        settle_summon_retirements(self)
        old_order = tuple(self.order)
        current_id = old_order[self.turn_index]
        # Validate the entire native population before publishing reconciliation.
        participating = {a.id for a in self.actors.values() if self._in_play(a)}
        self.order = [uid for uid in old_order if uid in participating]
        alive = {a.team for a in self.actors.values() if a.id in participating}
        defer_victory = False
        if getattr(self, "rift_wave_state", None) is not None:
            from .rift_combat_adapter import defer_wave_victory

            defer_victory = defer_wave_victory(self, alive)
        if len(alive) < 2 and not defer_victory:
            self.phase = "finished"
            self.winner = next(iter(alive), None)
            self._event("finished", winner=self.winner)
        elif current_id in self.order:
            self.turn_index = self.order.index(current_id)
        else:
            start = old_order.index(current_id)
            next_id = next(
                old_order[(start + offset) % len(old_order)]
                for offset in range(1, len(old_order) + 1)
                if old_order[(start + offset) % len(old_order)] in self.order
            )
            self.turn_index = self.order.index(next_id)
            self.turn_id += 1
            self._begin_turn()

    def apply_effect_healing(self, source_id, target_id, amount):
        """Trusted healing effect; resurrection has a separate native path."""
        if (
            self.phase != "active"
            or self.current is None
            or source_id not in self.actors
            or type(amount) is not int
            or amount < 0
        ):
            raise ValueError("Invalid dispatched healing context")
        target = self.actors.get(target_id)
        if target is None or target.hp <= 0:
            raise ValueError("Healing target is not alive")
        from .combat_hp_raw import hp_raw_present, shift_hp_raw_current

        if hp_raw_present(target):
            restored = shift_hp_raw_current(target, amount)
        else:
            restored = min(amount, target.max_hp - target.hp)
            target.hp += restored
        self._sync_resources(target)
        self._event(
            "healing",
            source_id=source_id,
            target_id=target_id,
            amount=restored,
            hp=target.hp,
        )
        return restored

    def apply_state(
        self,
        source_id,
        target_id,
        reference,
        level,
        *,
        uid,
        catalog,
        applying_effect_has_delay=None,
        timeline=None,
        protected=None,
        native_corpse_target=False,
        before_replace=None,
    ):
        """Trusted effect dispatcher only; selection/conditions are its job.

        The ledger returns child effects, including instant states. This method
        records the application but does not claim those effects were executed.
        """
        from .combat_state_managers import state_manager

        source = state_manager(self, source_id)
        target = state_manager(self, target_id)
        from .combat_summon_initialization import detached_actor

        constructor = (
            source_id == target_id
            and detached_actor(self, source_id) is source
            and source is not None
        )
        if (
            (self.phase != "active" and not constructor)
            or source is None
            or target is None
            or (
                not getattr(target, "native_is_area", False)
                and target.hp <= 0
                and native_corpse_target is not True
            )
        ):
            raise ValueError("Invalid state source, target or fight phase")
        change = target.state_ledger.apply(
            catalog,
            reference,
            level,
            caster_id=source_id,
            uid=uid,
            applying_effect_has_delay=applying_effect_has_delay,
            timeline=timeline,
            protected=protected,
            before_replace=before_replace,
        )
        for entry in change.removed:
            self._event(
                "state_removed",
                actor_id=target_id,
                uid=entry.uid,
                state_id=entry.reference,
                reason="replacement",
            )
        if change.applied is not None:
            entry = change.applied
            self._event(
                "state_applied",
                actor_id=target_id,
                source_id=source_id,
                uid=entry.uid,
                state_id=entry.reference,
                level=entry.level,
                duration=entry.duration,
                instant=not entry.retained,
            )
        return change

    def expire_states(self, *, actor_id, round_number, phase, round_cleanup=False):
        """Trusted timeline dispatcher; returned entries still need wire removal."""
        removed = []
        for actor in self.actors.values():
            entries = actor.state_ledger.expire(
                actor_id=actor_id,
                round_number=round_number,
                phase=phase,
                round_cleanup=round_cleanup,
            )
            for entry in entries:
                self._event(
                    "state_removed",
                    actor_id=actor.id,
                    uid=entry.uid,
                    state_id=entry.reference,
                    reason="expiration",
                )
            removed.extend(entries)
        return tuple(removed)
