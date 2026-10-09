"""Lease-bound adapter between PostgreSQL participants and shared combat FSMs.

This module deliberately does not create actor serializers or interpret combat
actions. The network dispatcher supplies those native factories and routes each
accepted action through these ordered registry operations.
"""

from wakfu_server.combat_shared import Registry, Session
from wakfu_server.fight_store import join_participant
from copy import copy


class CombatSessionAdapter:
    def __init__(self, store):
        self.store = store
        self.registry = Registry(self._lease_is_current)

    def _lease_is_current(self, session):
        return self.store.current_character_session(
            session.account_id, session.generation, session.character_id
        )

    def session(self, account_id, generation, character):
        """Create a registry identity only for the currently selected lease."""
        entry = Session(
            account_id,
            character["id"],
            generation,
            character["map_id"],
            character.get("instance_id", 0),
        )
        self.registry._live(entry)
        return entry

    def lookup_character(self, character_id):
        return self.registry.lookup_character(character_id)

    def register(
        self,
        session,
        fight,
        *,
        runtime=None,
        group_lease=None,
        join_context=None,
    ):
        """Register a placement FSM after its durable starter row exists."""
        if join_context is not None:
            if not isinstance(join_context, dict):
                raise ValueError("Native join context must be a mapping")
            join_context = dict(join_context)
            join_context.setdefault("actor_payload", self.actor_payload)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT p.team,p.session_generation,f.status "
                "FROM combat_fights f JOIN combat_fight_participants p "
                "ON p.fight_id=f.id WHERE f.id=%s AND p.character_id=%s "
                "AND p.account_id=%s",
                (fight.id, session.character_id, session.account_id),
            ).fetchone()
        if (
            row is None
            or row["status"] != "placement"
            or row["session_generation"] != session.generation
            or row["team"] != fight.actors[session.character_id].team
        ):
            raise ValueError("Fight starter has no matching durable lease")
        return self.registry.register(
            fight,
            session,
            runtime=runtime,
            group_lease=group_lease,
            join_context=join_context,
        )

    def register_duel(
        self,
        fight,
        sessions,
        *,
        runtime=None,
        auto_locked=False,
        initial_packets,
        db=None,
        join_context=None,
    ):
        """Register a database-authorized duel after both owners are prepared."""
        from contextlib import nullcontext
        from psycopg.pq import TransactionStatus

        sessions = tuple(sessions)
        if len(sessions) != 2:
            raise ValueError("A duel requires two live sessions")
        if db is not None and db.info.transaction_status != TransactionStatus.INTRANS:
            raise ValueError(
                "Duel registration requires the active acceptance transaction"
            )
        with nullcontext(
            db
        ) if db is not None else self.store.connection() as connection:
            rows = tuple(
                connection.execute(
                    "SELECT p.character_id,p.account_id,p.team,p.session_generation,"
                    "f.status,f.fight_kind,s.character_id AS selected_character_id,"
                    "s.expires_at FROM combat_fights f "
                    "JOIN combat_fight_participants p ON p.fight_id=f.id "
                    "JOIN sessions s ON s.account_id=p.account_id "
                    "AND s.generation=p.session_generation "
                    "WHERE f.id=%s ORDER BY p.character_id FOR UPDATE OF s",
                    (fight.id,),
                )
            )
        expected = {
            (session.account_id, session.character_id, session.generation)
            for session in sessions
        }
        actual = {
            (row["account_id"], row["character_id"], row["session_generation"])
            for row in rows
        }
        if (
            len(rows) != 2
            or actual != expected
            or any(
                row["selected_character_id"] != row["character_id"]
                or row["expires_at"] <= self.store.now()
                for row in rows
            )
            or any(
                row["status"] != "placement" or row["fight_kind"] != "duel"
                for row in rows
            )
            or any(
                fight.actors[row["character_id"]].team != row["team"] for row in rows
            )
        ):
            raise ValueError("Duel runtime has no matching durable owner roster")
        return self.registry.register_duel(
            fight,
            sessions,
            runtime=runtime,
            auto_locked=auto_locked,
            initial_packets=initial_packets,
            # The rows above were joined under the acceptance transaction.
            # Rechecking through Store.current_character_session would open a
            # second connection and wait on the session locks held by `db`.
            leases_validated=True,
            join_context=join_context,
        )

    def player_actor(self, session, *, team):
        """Build and natively initialize a joining owner actor from Store state."""
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.builds import effective_sheet_level

        character = self.store.character(session.account_id, session.character_id)
        from wakfu_server import territory_bonuses

        with self.store.connection() as db:
            character = territory_bonuses.attach_character(db, character)
        resources = combat_resources(character)
        actor = Actor(
            character["id"],
            team,
            (character["x"], character["y"], character["z"]),
            character["hp"],
            resources["ap"],
            resources["mp"],
            resources["initiative"],
            effective_sheet_level(character, character.get("active_build_index", 0)),
            character["account_id"],
            True,
            max_hp=character["max_hp"],
            direction=0,
        )
        snapshot = build_player_snapshot(
            character,
            actor,
            wp_current=resources["wp"],
            wp_maximum=resources["wp"],
            running_effects=(),
        )
        snapshot.install(actor)
        actor.native_resource_numeric_observers = {4: ()}
        return actor

    def player_sources(self, fight):
        """Return fresh owner character/deck snapshots for the entire roster."""
        from wakfu_server.spells import default_deck
        from .combat_terminal_metadata import registered_summon_actor_ids

        characters = {}
        decks = {}
        summon_ids = registered_summon_actor_ids(fight)
        for actor in fight.actors.values():
            if (
                not actor.controlled
                or actor.id in summon_ids
                or getattr(actor, "pve_withdrawn", False)
            ):
                continue
            character = self.store.character(actor.owner_id, actor.id)
            if character.get("deleted_at") is not None:
                raise ValueError("Combat participant character is unavailable")
            index = character.get("active_build_index", 0)
            builds = character.get("builds", {})
            build = builds.get(index, builds.get(str(index), {}))
            deck_hex = build.get("deck") if isinstance(build, dict) else None
            deck = bytes.fromhex(deck_hex) if deck_hex else default_deck(character)
            characters[actor.id] = character
            decks[actor.id] = deck
        if not characters:
            raise ValueError("Shared fight requires an owned player roster")
        return characters, decks

    def ready_transition(
        self,
        session,
        fight,
        runtime,
        ready,
        monsters,
        *,
        previous_native_action_id=0,
        fight_start=True,
        area_callbacks=False,
    ):
        """Prepare one shared placement-ready transition for every owner.

        The caller commits the returned Transition through Registry.execute.
        Each participant gets its own current Store snapshot and active-build
        deck; no starter-owned character or deck is reused for another actor.
        """
        from wakfu_server.combat_actor import (
            actor_effects,
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_ready import prepare_ready
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_end,
            prepare_server_turn_start,
        )
        from wakfu_server.spells import default_deck

        # Withdrawn placement members remain in the historical checkpoint
        # roster, but cannot participate in native Ready initialization or its
        # initial_order. Filter a detached input, then restore the zero-HP
        # historical actors after the engine's ordinary Ready transition.
        withdrawn = {
            identity: actor
            for identity, actor in fight.actors.items()
            if getattr(actor, "pve_withdrawn", False)
        }
        if withdrawn:
            from copy import deepcopy

            fight = deepcopy(fight)
            for identity in withdrawn:
                fight.actors.pop(identity)

        characters, decks = self.player_sources(fight)
        actor_order = [
            actor_id
            for actor_id in fight.order
            if actor_id in characters and fight.actors[actor_id].controlled
        ]
        # A valid placement roster always contains its starter. Keep a stable
        # fallback for older FSMs whose order has not been populated yet.
        actor_order.extend(sorted(set(characters) - set(actor_order)))
        if not actor_order:
            raise ValueError("Placement has no initialized player owners")
        first_character = characters[actor_order[0]]
        first_deck = decks[actor_order[0]]

        def initialize(preview, action_id):
            packets = []
            for index, actor_id in enumerate(actor_order):
                actor = preview.actors[actor_id]
                source = characters[actor_id]
                # Deliver the fight-start subscriber once, after every owner
                # has installed its own innate states and passive roots.
                preview, owned_packets = prepare_server_initialization(
                    source,
                    monsters,
                    preview,
                    actor.owner_id,
                    decks[actor_id],
                    action_id=action_id,
                    player_characters=characters,
                    deck_blobs=decks,
                    fight_start=bool(fight_start and index == len(actor_order) - 1),
                )
                packets.extend(owned_packets)
            return preview, tuple(packets)

        def stats_serializer(actor, state=None):
            current = fight if state is None else state
            if actor.id in getattr(current, "native_summon_registrations", {}):
                from .combat_summon_stats import registered_summon_stats

                return registered_summon_stats(
                    actor, current, characters[session.character_id]["map_id"]
                )
            if actor.controlled:
                source = characters.get(actor.id)
                if source is None:
                    raise ValueError("Controlled combat actor has no owner snapshot")
                wp = (
                    actor.effect_stats.get(4)
                    if isinstance(actor.effect_stats, dict)
                    else None
                )
                maximum = (
                    actor.effect_maxima.get(4)
                    if isinstance(actor.effect_maxima, dict)
                    else None
                )
                if wp is None or maximum is None:
                    raise ValueError("Missing authoritative combat WP snapshot")
                return actual_actor_stats(
                    source, actor, fight.id, wp_current=wp, wp_maximum=maximum
                )
            monster = monsters.get(actor.id)
            if monster is None:
                raise ValueError("Unowned combat actor has no monster snapshot")
            wp = (
                actor.effect_stats.get(4)
                if isinstance(actor.effect_stats, dict)
                else None
            )
            maximum = (
                actor.effect_maxima.get(4)
                if isinstance(actor.effect_maxima, dict)
                else None
            )
            if wp is None or maximum is None:
                raise ValueError("Missing authoritative combat WP snapshot")
            return actual_monster_actor_stats(
                monster, actor, fight.id, wp_current=wp, wp_maximum=maximum
            )

        def turn_end(preview, *, actor_id, action_id):
            actor = preview.actors[actor_id]
            source = characters.get(actor_id, first_character)
            deck = decks.get(actor_id, first_deck)
            return prepare_server_turn_end(
                source,
                monsters,
                preview,
                deck,
                actor_id=actor_id,
                action_id=action_id,
                player_characters=characters,
                deck_blobs=decks,
            )

        def turn_start(preview, **boundary):
            actor_id = boundary["actor_id"]
            source = characters.get(actor_id, first_character)
            deck = decks.get(actor_id, first_deck)
            return prepare_server_turn_start(
                source,
                monsters,
                preview,
                deck,
                native_events=fight_start,
                area_callbacks=area_callbacks,
                player_characters=characters,
                deck_blobs=decks,
                **boundary,
            )

        def expiration_factory(*, action_id):
            from .combat_server_spell import server_runtime

            return server_runtime(
                first_character,
                monsters,
                first_deck,
                action_id=action_id,
                critical=False,
                player_characters=characters,
                deck_blobs=decks,
            )[0]

        candidate, candidate_runtime, packets = prepare_ready(
            fight,
            session.account_id,
            ready,
            initialize=initialize,
            stats_serializer=stats_serializer,
            runtime_stats_serializer=stats_serializer,
            effects_serializer=actor_effects,
            expiration_runtime_factory=expiration_factory,
            turn_end_provider=turn_end if fight_start else None,
            turn_start_provider=turn_start if fight_start or area_callbacks else None,
            previous_native_action_id=previous_native_action_id,
        )
        if withdrawn:
            from copy import deepcopy

            candidate.actors.update(deepcopy(withdrawn))
        # prepare_ready previews the next Fight by deepcopying it. While the
        # other owner is still choosing placement it returns no new
        # RuntimeMessages, so keep the existing counters but bind them to the
        # preview that Registry.execute is about to commit. The runtime passed
        # here is already a transactional deepcopy owned by execute; rebinding
        # it cannot mutate the currently published shared state on rollback.
        if candidate_runtime is None and runtime is not None:
            candidate_runtime = copy(runtime)
            candidate_runtime.fight = candidate
        return self._transition(candidate, candidate_runtime or runtime, packets)

    @staticmethod
    def _transition(fight, runtime, packets):
        from wakfu_server.combat_shared import Transition

        return Transition(fight, runtime, tuple(packets))

    def actor_payload(self, fight, actor, session):
        """Serialize the actor from its live native snapshot, never a capture."""
        from wakfu_server.combat_actor import (
            actor_effects,
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.breed_resources import live_wp

        if actor.id in getattr(fight, "native_summon_registrations", {}):
            from wakfu_server.combat_summon_stats import registered_summon_stats

            shared = self.registry.lookup(fight.id)
            stats = registered_summon_stats(actor, fight, shared.map_id)
        elif actor.controlled:
            character = self.store.character(actor.owner_id, actor.id)
            stats = actual_actor_stats(
                character,
                actor,
                fight.id,
                wp_current=live_wp(fight, actor.id)[0],
                wp_maximum=live_wp(fight, actor.id)[1],
            )
        else:
            shared = self.registry.lookup(fight.id)
            context = shared.join_context
            monsters = (
                None if not isinstance(context, dict) else context.get("monsters")
            )
            monster = None if monsters is None else monsters.get(actor.id)
            if monster is None:
                raise ValueError("Native monster bootstrap metadata is missing")
            current = live_wp(fight, actor.id)
            stats = actual_monster_actor_stats(
                monster,
                actor,
                fight.id,
                wp_current=current[0],
                wp_maximum=current[1],
            )
        if fight.phase == "active":
            from wakfu_server.combat_remote_effects import active_actor_effects

            effects = active_actor_effects(fight, actor.id)
        else:
            effects = actor_effects()
        return stats, effects

    @staticmethod
    def placement_bootstrap(fight, shared, session):
        """Rebuild the exact owned placement bootstrap for a joining peer."""
        context = shared.join_context
        if not isinstance(context, dict):
            raise ValueError("Native placement bootstrap context is missing")
        required = {
            "arena",
            "terrain_effect_id",
            "terrain_instance_id",
            "leaders",
            "duration_ms",
        }
        if required - context.keys():
            raise ValueError("Native placement bootstrap context is incomplete")
        from wakfu_server.combat_bootstrap import placement_messages

        # The bound callback is supplied by the adapter at join time so every
        # actor is serialized from its fresh shared-FSM state.
        serializer = context.get("actor_payload")
        if not callable(serializer):
            raise ValueError("Native actor serializer is unavailable")
        payloads = {
            actor.id: serializer(fight, actor, session)
            for actor in fight.actors.values()
        }
        return placement_messages(
            fight,
            context["arena"],
            payloads,
            terrain_effect_id=context["terrain_effect_id"],
            terrain_instance_id=context["terrain_instance_id"],
            leaders=context["leaders"],
            duration_ms=context["duration_ms"],
        )

    def join(
        self,
        session,
        body,
        actor,
        *,
        actor_payload=None,
        bootstrap_packets=None,
        expected_fight_id=None,
    ):
        """Persist a same-team placement member before publishing its outbox.

        Registry validation and native packet construction run while the chosen
        cell is reserved under the shared fight lock. The persistence callback
        commits the durable membership before the in-memory roster is exposed.
        """
        from wakfu_server.combat_multiplayer_wire import decode_join

        request = decode_join(body)
        fight_id = self.registry.resolve_join_target(request["target_id"])
        if expected_fight_id is not None and fight_id != expected_fight_id:
            raise ValueError("Join target changed during admission")
        shared = self.registry.lookup(fight_id)
        if request["target_id"] not in shared.fight.actors:
            raise ValueError("Join target disappeared")

        def persist(candidate, joined, prior_shared, owner):
            with self.store.connection() as db:
                join_participant(
                    self.store,
                    db,
                    owner.account_id,
                    owner.generation,
                    owner.character_id,
                    candidate.id,
                    target_character_id=request["target_id"],
                    team=candidate.actors[request["target_id"]].team,
                )

        actor_payload = actor_payload or self.actor_payload
        if bootstrap_packets is None:
            bootstrap_packets = self.placement_bootstrap
        return self.registry.join(
            session,
            body,
            actor,
            actor_payload=actor_payload,
            bootstrap_packets=bootstrap_packets,
            persist_member=persist,
            expected_fight_id=fight_id,
        )

    def ready(self, session, fight_id, ready, packets):
        return self.registry.ready(fight_id, session, ready, packets)

    def execute(
        self,
        session,
        fight_id,
        actor_id,
        operation,
        *,
        expected_sequence=None,
        require_turn=True,
    ):
        return self.registry.execute(
            fight_id,
            session,
            actor_id,
            operation,
            expected_sequence=expected_sequence,
            require_turn=require_turn,
        )

    def acknowledge(self, session, fight_id, body, release_packets):
        return self.registry.acknowledge(fight_id, session, body, release_packets)

    def expire_current_turn(self, fight_id, session, *, now_ms):
        """Delegate the idle-loop deadline check to the shared fight registry."""
        return self.registry.expire_current_turn(fight_id, session, now_ms=now_ms)

    def publish(self, session, fight_id, packets):
        return self.registry.publish(fight_id, session, packets)

    def drain(self, session, fight_id):
        return self.registry.drain(fight_id, session)

    def dispatch_connected(self, fight_id, deliver):
        """Push ordered outbox batches to all currently connected owners."""
        return self.registry.dispatch_connected(fight_id, deliver)

    def disconnect(self, session):
        return self.registry.disconnect(session)

    def withdraw_pve(self, session, character, body):
        """Prepare the private13952 continuation and preserve other owners."""
        if body != b"":
            raise ValueError("Invalid native abandon request")
        from .combat_pve_withdraw_store import persist

        from .combat_captured_roster_lifecycle import restore_departing_roster

        teardown = {}

        def owned_teardown(candidate):
            restore_departing_roster(candidate, character)
            teardown["fight"] = candidate

        def persist_owned(original):
            return persist(
                self.store,
                session,
                character,
                original,
                captured_departure_fight=teardown["fight"],
            )

        def placement_ready(shared, fight, runtime):
            remaining = next(
                participant
                for owner, participant in shared.participants.items()
                if owner != session.account_id
                and any(
                    actor.controlled
                    and actor.owner_id == owner
                    and not getattr(actor, "pve_withdrawn", False)
                    for actor in fight.actors.values()
                )
            )
            context = shared.join_context or {}
            return self.ready_transition(
                remaining,
                fight,
                runtime,
                True,
                context.get("monsters", {}),
                previous_native_action_id=runtime.native_action_id,
            )

        return self.registry.withdraw_pve(
            session,
            persist=persist_owned,
            owned_teardown=owned_teardown,
            placement_ready=placement_ready,
        )

    def return_withdrawn_pve(
        self, session, fight_id, character, body, *, wp, pending=None
    ):
        """Validate native12925, acknowledge durably, then release own indexes."""
        from copy import deepcopy
        from . import combat_abandon
        from .combat_pve_withdraw_store import acknowledge

        try:
            shared = self.registry.lookup(fight_id)
        except ValueError:
            shared = None
        if shared is None:
            receipt = pending
        else:
            with shared.lock:
                receipt = shared.withdrawals.get(session.account_id)
        if receipt is None or receipt["session"] != session:
            raise ValueError("No owned PvE withdrawal continuation")
        candidate = deepcopy(receipt["withdrawal"].private_runtime)
        returned = combat_abandon.return_to_world(
            self.store,
            session.account_id,
            session.generation,
            character,
            candidate,
            body,
            wp=wp,
        )
        # Never hold the per-fight lock while acquiring the registry lock.
        if shared is None:
            saved = acknowledge(self.store, session, fight_id)
        else:
            try:
                saved = self.registry.return_withdrawn_pve(
                    fight_id,
                    session,
                    persist=lambda: acknowledge(self.store, session, fight_id),
                )
            except ValueError:
                # The last remaining owner's disconnect can retire the
                # encounter between this socket's validated private ACK and
                # index cleanup. It cannot cancel this durable private exit.
                with self.registry.lock:
                    if fight_id in self.registry.fights:
                        raise
                saved = acknowledge(self.store, session, fight_id)
        returned["character"] = saved
        return returned

    def recover_withdrawn_pve(self, session):
        """After selector/disconnection, finish the durable private exit only."""
        from .combat_pve_withdraw_store import recover, recover_pending

        saved = self.registry.recover_withdrawn_pve(
            session,
            persist=lambda fight_id, previous_generation: recover(
                self.store,
                session,
                fight_id,
                previous_generation,
            ),
        )
        return saved if saved is not None else recover_pending(self.store, session)

    def live_reconnect_available(self, session):
        """Distinguish durable live ownership from an aborted stale registry entry."""
        shared = self.lookup_character(session.character_id)
        if shared is None:
            return False
        with shared.lock:
            previous = shared.participants.get(session.account_id)
            if (
                previous is None
                or previous.character_id != session.character_id
                or session.account_id in shared.returned
                or session.account_id in shared.withdrawals
                or shared.fight.phase not in ("placement", "active")
                or shared.settlement_ready
            ):
                return False
            with self.store.connection() as db:
                row = db.execute(
                    "SELECT f.status,p.session_generation FROM combat_fights f "
                    "JOIN combat_fight_participants p ON p.fight_id=f.id "
                    "WHERE f.id=%s AND p.character_id=%s AND p.account_id=%s",
                    (shared.fight.id, session.character_id, session.account_id),
                ).fetchone()
            if row is None:
                raise ValueError("Live combat has no durable participant authority")
            if row["status"] == "aborted":
                return False
            if row["status"] != shared.fight.phase:
                raise ValueError("Live combat phase differs from durable checkpoint")
            if row["session_generation"] not in (
                previous.generation,
                session.generation,
            ):
                raise ValueError("Live combat durable lease differs from owner")
            return True

    def owned_reconnect_bootstrap(self, fight, shared, session):
        from .combat_reconnect_snapshot import owned_snapshot

        return owned_snapshot(fight, shared, session, actor_payload=self.actor_payload)

    def reconcile_disconnected_pve(self, session, *, groups=None):
        """Heal an orphaned old lease before initializing a reconnect's world HP."""
        from .combat_health import persist_aborted_shared_fight

        def persist(previous, shared):
            if shared.participants.get(session.account_id) != previous:
                raise ValueError("Disconnected PvE owner changed during recovery")
            return persist_aborted_shared_fight(
                self.store,
                shared,
                groups=groups,
                reconnecting_session=session,
            )

        return self.registry.reconcile_disconnected_pve(session, persist)

    def settle_finished(self, session, fight_id, prepare_packets):
        return self.registry.settle_finished(fight_id, session, prepare_packets)

    def mark_returned(self, session, fight_id):
        return self.registry.mark_returned(fight_id, session)

    def takeover_settled(self, session, fight_id):
        """Reattach a current selected owner and replay its private result batch."""
        from wakfu_server.fight_store import takeover_participant

        shared = self.registry.lookup(fight_id)
        previous = shared.participants.get(session.account_id)
        if (
            not shared.settlement_ready
            or previous is None
            or previous.character_id != session.character_id
            or session.account_id in shared.returned
        ):
            raise ValueError("Settled combat participant is unavailable")

        def persist(previous_owner):
            if previous_owner != previous:
                raise ValueError("Combat owner changed during takeover")
            takeover_participant(
                self.store,
                session.account_id,
                session.generation,
                session.character_id,
                fight_id,
                previous_generation=previous_owner.generation,
            )

        return self.registry.takeover(
            fight_id,
            session,
            lambda fight, shared, owner: (),
            persist_takeover=persist,
        )

    def recover_settled_world(self, session, character, *, wp, ap=6, mp=3):
        """Resolve a terminal PvE reconnect that has already loaded world state."""
        if (
            not isinstance(character, dict)
            or character.get("id") != session.character_id
            or character.get("account_id") != session.account_id
        ):
            raise ValueError("Settled world recovery character does not match lease")

        def persist(previous, shared):
            from .combat_lifecycle import recover_settled_world

            if shared.participants.get(session.account_id) != previous:
                raise ValueError("Settled fight changed during world recovery")
            return recover_settled_world(
                self.store,
                session.account_id,
                session.generation,
                character,
                shared.fight,
                previous_generation=previous.generation,
                wp=wp,
                ap=ap,
                mp=mp,
            )

        shared = self.registry.lookup_character(session.character_id)
        if shared is not None:
            return self.registry.recover_settled_world(session, persist)

        # After process restart the in-memory Registry is empty. A terminal
        # snapshot committed with settlement is sufficient to restore this
        # owner directly to the already-loaded world, without fight replay.
        from .fight_store import recoverable_finished_fight

        candidate = recoverable_finished_fight(
            self.store, session.account_id, session.character_id
        )
        if candidate is None:
            return None
        from .combat_lifecycle import recover_settled_world

        return recover_settled_world(
            self.store,
            session.account_id,
            session.generation,
            character,
            None,
            previous_generation=candidate["previous_generation"],
            fight_id=candidate["fight_id"],
            wp=wp,
            ap=ap,
            mp=mp,
        )
