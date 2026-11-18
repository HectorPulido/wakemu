"""Connection lifecycle and composition of Python domain coordinators."""

import struct
import os
import time
import uuid
from types import SimpleNamespace
from .dispatch_result import DispatchResult
from .network_delivery import PendingSessionWork
from .session_dispatch import SessionDispatchMixin
from .session_protocol import ProtocolSessionMixin
from .session_inventory import InventorySessionMixin
from .session_travel import TravelSessionMixin
from .session_objectives import ObjectivesSessionMixin
from .session_combat import CombatSessionMixin
from .session_combat_admission import CombatAdmissionMixin
from .session_combat_actions import CombatActionsMixin
from .session_world import WorldSessionMixin
from .session_ecology import EcologySessionMixin
from .session_social import SocialSessionMixin
from .session_admin import AdminSessionMixin
from .session_actor_approach import ActorApproachMixin
from .session_scheduler import SessionSchedulerMixin
from .session_characters import CharacterSessionMixin
from .session_private_scenes import PrivateScenesMixin


class Session(
    SessionDispatchMixin,
    ActorApproachMixin,
    ProtocolSessionMixin,
    InventorySessionMixin,
    TravelSessionMixin,
    ObjectivesSessionMixin,
    CombatSessionMixin,
    CombatAdmissionMixin,
    CombatActionsMixin,
    WorldSessionMixin,
    EcologySessionMixin,
    SocialSessionMixin,
    AdminSessionMixin,
    SessionSchedulerMixin,
    CharacterSessionMixin,
    PrivateScenesMixin,
):
    """Own session state and ordered connection lifecycle; domains own operations."""

    def __init__(self, runtime, raw, peer, service, context):
        self.runtime = runtime
        self.state = SimpleNamespace(
            raw=raw, peer=peer, service=service, context=context
        )
        self._bind_runtime_callbacks()
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.ecology_feedback import information

        self.state.information = information
        self.state.selected = self.state.loaded = False
        self.state.intro_cinematic_scene = None
        self.state.scene_sync = self.runtime.SceneSync()
        self.state.static_sync_pending = False
        self.state.static_sync_attempts = 0
        self.state.static_sync_due = time.monotonic() + 0.75
        self.state.world_snapshot_pending = False
        self.state.world_snapshot_due = time.monotonic() + 0.75
        self.state.world_snapshot_identity = None
        self.state.account_id = self.state.generation = self.state.character = None
        self.state.training_transit_active = False
        self.state.hero_switch_pending = None
        self.state.bag_session = None
        self.state.ranch_session = None
        self.state.chest_opening = None
        self.state.paid_container_ticket = None
        self.state.guild_chest_session = None
        self.state.fight = None
        self.state.pending_actor_approach = None
        self.state.pending_guardian_attack = None
        self.state.owned_story_ambush_admission = None
        self.state.pending_rii_lesson_guide = None
        self.state.combat_session = None
        self.state.pending_terminal_world_recovery = None
        self.state.pending_combat_return = None
        self.state.pending_travel_resume = None
        self.state.world_respawn_retry_at = 0.0
        from wakfu_server.combat_return_command import PendingEmergencyCommand

        self.state.pending_return_command = PendingEmergencyCommand()
        self.state.publication_recovery_shared = None
        self.state.publication_recovery_attempt_token = None
        self.state.publication_recovery_attempt_due = 0.0
        self.state.publication_recovery_notice_token = None
        self.state.publication_recovery_return_due = 0.0
        self.state.aborted_native_return = None
        self.state.spectator_session = None
        self.state.npc_dialogue_session = None
        self.state.spectator_fight_id = None
        self.state.spectator_terminal_pending = None
        self.state.pve_withdrawal_pending = None
        self.state.active_request = None
        self.state.connection_trace_id = uuid.uuid4().hex
        self.state.fight_messages = None
        self.state.fight_started_at = None
        self.state.group_lease = None
        self.state.TEST_MONSTERS = ()
        self.state.TEST_MONSTERS_BY_ID = {}
        self.state.TEST_GROUP_KEY = None
        self.state.checkpoint_local_shared = None
        self.state.checkpoint_revision = self.state.checkpoint_id = None
        self.state.checkpoint_terminal = False
        self.state.connected_at = time.monotonic()
        self.state.last_chat = 0
        self.state.last_health_tick = 0
        self.state.last_consumable_tick = 0
        self.state.last_ranch_cycle_tick = 0
        self.state.guild_daily_boundary = (None, None)
        self.state.recurring_hunter_boundary = (None, None)
        self.state.recurring_hunter_refresh_pending = False
        self.state.pet_hibernation_due = 0.0
        self.state.last_shop_refresh = 0
        self.state.last_session_renewal = 0
        self.state.last_dungeon_transition_poll = 0.0
        self.state.last_dungeon_transition_report = None
        self.state.last_dungeon_recovery_identity = None
        self.state.dungeon_recovery_notice_states = set()
        from wakfu_server.placement_deadline import Deadline
        from wakfu_server.achievements.rii_guardian_contract import (
            is_owned as is_owned_guardian_fight,
        )

        self.state.is_owned_guardian_fight = is_owned_guardian_fight
        from wakfu_server.custom_tasks.hooks import SelectedTaskCards
        from wakfu_server.custom_tasks.gift_source import current_local_gifts

        self.state.current_local_gifts = current_local_gifts
        self.state.custom_task_cards = SelectedTaskCards()
        from wakfu_server.objectives.environmental_world import (
            SelectedEnvironmentalEvents,
        )

        self.state.environmental_events = SelectedEnvironmentalEvents(
            hero_template=self.runtime.OWNED_HERO_TEMPLATE,
            roster_template=self.runtime.CHARACTERS,
            groups=vars(self.runtime).get("COMBAT_GROUPS"),
        )
        from wakfu_server.national_publication import SelectedNationalProgression

        self.state.national_publication = SelectedNationalProgression()
        self.state.national_poll_at = 0.0
        self.state.environmental_poll_at = 0.0
        self.state.environmental_publication_error = None
        self.state.objectives_poll_at = 0.0
        self.state.objectives_hunt_poll_at = 0.0
        self.state.objectives_projection = None
        self.state.placement_deadline = Deadline()
        self.state.position = {"x": -12, "y": -8, "z": -1}
        self.state.console_session = None
        self.state.flora_ticket = None
        self.state.flora_retry_body = None
        self.state.environment_ticket = None
        self.state.quest_source_ticket = None
        self.state.pending_artifact_action = None
        self.state.environment_seat = None
        self.state.environment_scene_identity = None
        self.state.environment_scene_states = {}
        self.state.last_environment_refresh = 0.0
        self.state.native_area_movement_provider = self.area_movement_provider
        self.state.reconnect_expiry_recovery = dict(running=False, notice=None, due=0.0)
        self.refresh_shared_combat = self.combat_reconnect_expiry_boundary(
            self.refresh_shared_combat
        )
        self.drain_shared_combat = self.combat_reconnect_expiry_boundary(
            self.drain_shared_combat
        )

    def _bind_runtime_callbacks(self):
        """Keep the identity guarantees formerly supplied by local functions."""
        for name in (
            "current_combat_stats",
            "area_boundary_provider",
            "area_movement_provider",
        ):
            setattr(self, name, getattr(self, name))

    def bind_input(self, name, value):
        setattr(self.state, name, value)
        return value

    def __deepcopy__(self, memo):
        """Runtime callbacks retain their live owner across private fight copies.

        The previous function closures also kept the one live session. Copying
        a bound method must not copy its sockets, services or ownership state.
        """
        memo[id(self)] = self
        return self

    def ai_world_context(self):
        """Supply live ownership and callbacks without inspecting caller frames."""
        bindings = dict(vars(self.state))
        for name in (
            "current_combat_stats",
            "refresh_shared_combat",
            "drain_shared_combat",
            "checkpoint_fight",
            "complete_test_fight",
            "publish_external_marker",
            "publish_spectator_state",
        ):
            bindings[name] = getattr(self, name)
        return {"globals": vars(self.runtime), "scopes": [bindings]}

    def run(self):
        try:
            # Preserve remote TLS handshake tolerance before normal polling.
            self.state.raw.settimeout(10)
            with self.state.context.wrap_socket(
                self.state.raw, server_side=True
            ) as self.state.connection:
                self.state.connection.settimeout(1)
                self.state.connection = self.runtime.Connection(self.state.connection)
                self.state.connection.trace_id = self.state.connection_trace_id
                if self.state.service == "world":
                    self.state.connection.account_item_spell_update = (
                        self.publish_account_item_spells
                    )
                from wakfu_server.custom_tasks import external as external_objectives

                if self.state.service == "world" and external_objectives.enabled():
                    from wakfu_server.custom_tasks.external_updates import subscribe

                    self.state.connection.objectives_updates = subscribe(
                        self.runtime.STORE, self.runtime.STOPPING
                    )
                if self.state.service == "world":
                    from wakfu_server.interactive_publication import (
                        InteractivePublication,
                    )
                    from wakfu_server.seasonal_native_gateway import attachment

                    trace_ids = os.environ.get("WAKFU_INTERACTIVE_TRACE_IDS", "")
                    trace_account = os.environ.get(
                        "WAKFU_INTERACTIVE_TRACE_ACCOUNT", ""
                    )
                    self.state.connection.interactive_publication = (
                        InteractivePublication(
                            self.runtime.world_static.objects,
                            trace=self.state.connection.interactive_trace.append,
                            trace_ids={
                                int(value) for value in trace_ids.split(",") if value
                            },
                            trace_account_id=(
                                int(trace_account) if trace_account else None
                            ),
                            trace_limit=512 if trace_ids else 0,
                            attachment_projector=attachment,
                        )
                    )
                    self.state.connection.interactive_scope = lambda: (
                        dict(
                            session_id=self.state.connection_trace_id,
                            generation=self.state.generation,
                            account_id=self.state.account_id,
                            character_id=self.state.character["id"],
                            map_id=self.state.character["map_id"],
                            instance_id=self.state.character.get("instance_id", 0),
                        )
                        if self.state.character is not None
                        and self.state.generation is not None
                        else None
                    )
                    self.state.connection.native_instance_scope = lambda: (
                        (
                            self.state.account_id,
                            self.state.generation,
                            self.state.character["id"],
                            self.state.character["map_id"],
                            self.state.character["instance_id"],
                        )
                        if self.state.account_id is not None
                        and self.state.generation
                        and self.state.character is not None
                        else None
                    )
                if not self.runtime.CONNECTIONS.register(
                    self.state.connection,
                    lambda opcode, body: self.runtime.send(
                        self.state.connection, self.state.service, opcode, body
                    ),
                ):
                    return
                self.runtime.record(
                    event="tls_connected",
                    connection_id=self.state.connection_trace_id,
                    service=self.state.service,
                    peer=self.state.peer,
                    tls=self.state.connection.version(),
                )
                while not self.runtime.STOPPING.is_set():
                    if self.state.active_request is not None:
                        self.state.active_request.finish()
                        self.state.active_request = None
                    self.release_completed_combat_action_results()
                    if not self.idle():
                        raise ValueError("Session expired or replaced")
                    if self.state.pending_guardian_attack is not None:
                        self.state.route, self.state.opcode, self.state.body = (
                            0,
                            13130,
                            self.state.pending_guardian_attack,
                        )
                        self.state.pending_guardian_attack = None
                    else:
                        try:
                            header = self.runtime.receive(
                                self.state.connection,
                                4,
                                self.idle,
                                pending_work=lambda: self.state.pending_guardian_attack
                                is not None,
                            )
                        except PendingSessionWork:
                            continue
                        length = struct.unpack(
                            ">I",
                            header,
                        )[0]
                        if not 7 <= length <= 327670:
                            raise ValueError("Invalid frame size")
                        frame = self.runtime.receive(
                            self.state.connection, length - 4, self.idle
                        )
                        self.state.route, self.state.opcode = struct.unpack(
                            ">BH", frame[:3]
                        )
                        self.state.body = frame[3:]
                    self.state.request_received_at = time.monotonic()
                    from wakfu_server.combat_diagnostics import combat_diagnostic_scope

                    self.state.active_request = self.runtime.RequestTrace(
                        sink=self.runtime.record,
                        opcode=self.state.opcode,
                        service=self.state.service,
                        connection_id=self.state.connection_trace_id,
                        snapshot=lambda: (
                            {"keepalive": True}
                            if self.state.opcode == 33
                            else self.runtime.state_summary(
                                self.state.character,
                                self.state.fight,
                                self.state.fight_messages,
                                detailed=self.runtime.REQUEST_STATE_DETAIL,
                            )
                        ),
                        failure_snapshot=lambda: self.runtime.state_summary(
                            self.state.character,
                            self.state.fight,
                            self.state.fight_messages,
                        ),
                        effect_scope=(
                            combat_diagnostic_scope(self.runtime.record)
                            if self.state.fight is not None
                            or self.state.opcode in (13130, 12523, 13260)
                            else None
                        ),
                        flush=self.runtime.write_records,
                        activity_scope=(
                            self.runtime.ECOLOGY_BRIDGE.interactive()
                            if self.runtime.ECOLOGY_BRIDGE is not None
                            and self.state.service == "world"
                            else None
                        ),
                    )
                    self.runtime.record(
                        service=self.state.service,
                        direction="in",
                        opcode=self.state.opcode,
                        route=self.state.route,
                        bytes=len(self.state.body),
                    )
                    if self.prepare_request() is DispatchResult.CONTINUE:
                        continue
                    if self.dispatch_request() is DispatchResult.CONTINUE:
                        continue
                    if self.state.opcode not in (
                        13917,
                        12366,
                        13074,
                        13224,
                        13188,
                        13831,
                        12116,
                        13702,
                        12387,
                    ):
                        # Chat does not mutate the fight. Its reader must not wait
                        # for a combat outbox drain or serialize a Rift checkpoint.
                        # Gameplay and terminal paths retain their durable barriers.
                        self.checkpoint_fight()
                    self.state.active_request.finish()
                    self.state.active_request = None
                    self.release_completed_combat_action_results()
        except (EOFError, OSError, ValueError) as error:
            if self.state.active_request is not None:
                self.state.active_request.rejection("request_disconnected", str(error))
            self.runtime.record(
                event="disconnected",
                connection_id=self.state.connection_trace_id,
                service=self.state.service,
                error=type(error).__name__,
                detail=str(error),
                traceback=self.runtime.exception_frames(error),
                state_at_disconnect=self.runtime.safe_snapshot(
                    lambda: self.runtime.state_summary(
                        self.state.character,
                        self.state.fight,
                        self.state.fight_messages,
                    )
                ),
                native_action_id=(
                    None
                    if self.state.fight_messages is None
                    else self.state.fight_messages.native_action_id
                ),
                logical_action_id=(
                    None
                    if self.state.fight_messages is None
                    else self.state.fight_messages.action_id
                ),
            )
            if self.state.active_request is not None:
                self.state.active_request.finish(
                    status=(
                        "invalid_request"
                        if isinstance(error, ValueError)
                        else "disconnected"
                    )
                )
                self.state.active_request = None
        except Exception as error:
            self.runtime.record(
                event="unexpected_request_exception",
                service=self.state.service,
                connection_id=self.state.connection_trace_id,
                exception_type=type(error).__name__,
                reason=self.runtime.redact(str(error)),
                traceback=self.runtime.exception_frames(error),
                state_at_failure=self.runtime.safe_snapshot(
                    lambda: self.runtime.state_summary(
                        self.state.character,
                        self.state.fight,
                        self.state.fight_messages,
                    )
                ),
            )
            if self.state.active_request is not None:
                self.state.active_request.finish(status="unexpected_error")
                self.state.active_request = None
        finally:
            self.close()

    def close(self):
        if (
            self.state.service == "world"
            and self.state.character is not None
            and self.state.generation is not None
        ):
            self.runtime.WORLD.deactivate_ecology(
                self.state.character["id"], self.state.generation
            )
        publication_connection = vars(self.state).get("connection")
        if isinstance(publication_connection, self.runtime.Connection):
            updates = getattr(publication_connection, "objectives_updates", None)
            if updates is not None:
                updates.close()
            publication_connection.instance_publications.invalidate()
        if self.state.guild_chest_session is not None:
            self.state.guild_chest_session.close()
            self.state.guild_chest_session = None
        if self.state.active_request is not None:
            self.state.active_request.finish(status="interrupted")
            self.state.active_request = None
        if self.state.character is not None:
            self.runtime.PLANTINGS.cancel(
                self.state.character["id"], self.state.generation
            )
        if self.state.character is not None:
            self.runtime.HARVESTS.cancel(
                self.state.character["id"], generation=self.state.generation
            )
        if self.state.console_session is not None:
            self.runtime.TEST_CONSOLE.unregister(*self.state.console_session)
        if self.state.character is not None and self.state.generation is not None:
            self.runtime.TEST_CONSOLE.unregister(
                self.state.character["id"], self.state.generation
            )
        if "connection" in vars(self.state):
            self.runtime.CONNECTIONS.unregister(self.state.connection)
        from psycopg import OperationalError, InterfaceError

        self.state.OperationalError = OperationalError
        self.state.InterfaceError = InterfaceError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout
        from wakfu_server.position_redis import PositionJournalUnavailable

        self.state.PositionJournalUnavailable = PositionJournalUnavailable
        from wakfu_server.session_cleanup import retry_step

        self.state.retry_step = retry_step

        def logout_barrier(stage, operation):
            return self.state.retry_step(
                operation,
                retry_errors=(
                    self.state.OperationalError,
                    self.state.InterfaceError,
                    self.state.PoolTimeout,
                    self.state.PositionJournalUnavailable,
                    OSError,
                ),
                failed=lambda error: self.runtime.record(
                    event="logout_barrier_failed",
                    stage=stage,
                    actor_id=(
                        None
                        if self.state.character is None
                        else self.state.character["id"]
                    ),
                    reason=self.runtime.redact(str(error)),
                ),
                renew=lambda: (
                    self.runtime.STORE.heartbeat(
                        self.state.account_id, self.state.generation
                    )
                    if self.state.account_id is not None
                    and self.state.generation is not None
                    else None
                ),
            )

        self.state.logout_barrier = logout_barrier

        if self.state.service == "world" and (
            self.state.environment_ticket is not None
            or self.state.environment_seat is not None
            or self.state.pending_artifact_action is not None
        ):
            self.state.logout_barrier(
                "environment_occupation", lambda: self.cancel_environment(publish=False)
            )
        if self.state.service == "world" and self.state.flora_ticket is not None:
            self.state.logout_barrier("flora_occupation", self.cancel_flora)
        if (
            self.state.service == "world"
            and self.state.character is not None
            and self.state.generation is not None
            and hasattr(self, "consume_rift_entry_combat_retirement")
        ):
            self.consume_rift_entry_combat_retirement()
            from wakfu_server.combat_entry_recovery import discard_entry_recovery

            discard_entry_recovery(
                self.runtime.COMBAT_SESSIONS.registry,
                self.state.account_id,
                self.state.generation,
            )
        if self.state.service == "world" and self.state.combat_session is not None:
            from wakfu_server.combat_command_recovery import take_cancelled

            cancelled = take_cancelled(
                self.runtime.COMBAT_SESSIONS.registry, self.state.combat_session
            )
            if cancelled is None:
                cancelled = self.state.publication_recovery_shared
            exits = getattr(cancelled, "publication_recovery_aborted", None) or {}
            if self.state.character is not None and self.state.character["id"] in exits:
                # The health/abort transaction already committed. Never let
                # this socket's older active FSM write another checkpoint.
                self.state.fight = (
                    self.state.fight_messages
                ) = self.state.combat_session = self.state.group_lease = None
                self.state.checkpoint_id = self.state.checkpoint_revision = None
                self.state.checkpoint_terminal = True
        if self.state.service == "world":
            from wakfu_server.checkpoint_worker import checkpoint_cleanup_barrier

            checkpoint_cleanup_barrier(
                lambda: self.state.logout_barrier(
                    "fight_checkpoint",
                    lambda: self.checkpoint_fight(
                        (
                            None
                            if self.state.combat_session is not None
                            else (
                                "ended"
                                if self.state.fight is not None
                                and self.state.fight.phase == "finished"
                                else "aborted"
                            )
                        ),
                        deliver=False,
                    ),
                ),
                failed=lambda error: self.runtime.record(
                    event="logout_checkpoint_failed",
                    stage="save",
                    actor_id=(
                        None
                        if self.state.character is None
                        else self.state.character["id"]
                    ),
                    reason=self.runtime.redact(str(error)),
                    traceback=self.runtime.exception_frames(error),
                ),
            )
        if self.state.service == "world" and self.state.fight is not None:

            def flush_logout_checkpoint():
                if not self.runtime.CHECKPOINT_WRITER.flush_fight(
                    self.state.fight.id, timeout=10
                ):
                    raise ValueError(
                        "Pending checkpoint exceeded logout flush deadline"
                    )

            self.state.flush_logout_checkpoint = flush_logout_checkpoint

            checkpoint_cleanup_barrier(
                lambda: self.state.logout_barrier(
                    "fight_checkpoint_flush", self.state.flush_logout_checkpoint
                ),
                failed=lambda error: self.runtime.record(
                    event="logout_checkpoint_failed",
                    stage="flush",
                    actor_id=(
                        None
                        if self.state.character is None
                        else self.state.character["id"]
                    ),
                    reason=self.runtime.redact(str(error)),
                    traceback=self.runtime.exception_frames(error),
                ),
            )
        shared_fight_retained = False
        self.state.last_owner_pve_abort = None
        if (
            self.state.service == "world"
            and self.state.combat_session is not None
            and self.state.fight is not None
        ):
            from wakfu_server.combat_pve_withdraw import has_other_live_owner

            self.state.has_other_live_owner = has_other_live_owner

            try:
                disconnected_fights = self.runtime.COMBAT_SESSIONS.disconnect(
                    self.state.combat_session
                )
                shared_fight_retained = bool(disconnected_fights)
                if not disconnected_fights:
                    current_shared = self.runtime.COMBAT_SESSIONS.lookup_character(
                        self.state.combat_session.character_id
                    )
                    shared_fight_retained = (
                        current_shared is not None
                        and current_shared.participants.get(
                            self.state.combat_session.account_id
                        )
                        != self.state.combat_session
                    )
                if disconnected_fights:
                    shared_entry = self.runtime.COMBAT_SESSIONS.registry.lookup(
                        self.state.fight.id
                    )
                    if getattr(shared_entry, "is_duel", False):
                        forfeited = self.runtime.COMBAT_SESSIONS.registry.forfeit_duel(
                            self.state.combat_session
                        )
                        if forfeited:
                            # A forfeit is already a resolved duel. Persist the
                            # no-reward/full-health outcome before ending this
                            # lease; otherwise two simultaneous disconnects
                            # could leave only an in-memory winner behind.
                            self.state.logout_barrier(
                                "duel_forfeit_settlement", self.complete_test_fight
                            )
                            self.runtime.record(
                                event="friendly_duel_disconnect_forfeit",
                                actor_id=self.state.combat_session.character_id,
                                fight_id=self.state.fight.id,
                            )
                    elif shared_entry.disconnect_abort_pending:
                        # Transport loss retains the live native FSM/checkpoint.
                        # A selected replacement lease can durably take over;
                        # explicit abandonment still follows its terminal path.
                        shared_fight_retained = True
                    elif (
                        not shared_entry.connected
                        and not self.state.has_other_live_owner(
                            shared_entry.fight, self.state.combat_session
                        )
                        and getattr(shared_entry.runtime, "abandon_owner", None)
                        == (
                            self.state.combat_session.account_id,
                            self.state.combat_session.character_id,
                        )
                        and shared_entry.fight.phase == "finished"
                        and not shared_entry.settlement_ready
                    ):
                        # The abandon transaction already saved HP and marked
                        # the fight aborted; a closed ACK socket must not pin
                        # its actor IDs or group lease indefinitely.
                        self.state.last_owner_pve_abort = (
                            self.state.fight.id,
                            self.state.combat_session,
                            shared_entry,
                        )
                        shared_fight_retained = False
            except ValueError:
                shared_fight_retained = False
        if (
            self.state.service == "world"
            and self.state.account_id is not None
            and self.state.character is not None
            and not shared_fight_retained
        ):
            from wakfu_server.combat_health import (
                persist_aborted_fight,
                persist_aborted_shared_fight,
            )

            self.state.persist_aborted_fight = persist_aborted_fight
            self.state.persist_aborted_shared_fight = persist_aborted_shared_fight

            # Confirm wounds before releasing the monster roster or position lease.
            def persist_exit_health():
                if self.state.last_owner_pve_abort is None:
                    return self.state.persist_aborted_fight(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.fight,
                    )
                fight_id, exited_session, shared_abort = self.state.last_owner_pve_abort
                try:
                    all_exits = self.state.persist_aborted_shared_fight(
                        self.runtime.STORE,
                        shared_abort,
                        groups=self.runtime.COMBAT_GROUPS,
                    )
                except ValueError as error:
                    self.runtime.record(
                        event="shared_pve_disconnect_cleanup_rejected",
                        actor_id=exited_session.character_id,
                        fight_id=fight_id,
                        reason=str(error),
                    )
                    return None
                return all_exits.get(exited_session.character_id)

            self.state.exited = self.state.logout_barrier(
                "fight_health",
                persist_exit_health,
            )
            if self.state.exited is not None and self.state.exited["applied"]:
                self.runtime.record(
                    event="combat_disconnected_health_saved",
                    actor_id=self.state.character["id"],
                    fight_id=self.state.fight.id,
                    hp=self.state.exited["character"]["hp"],
                )
            if self.state.last_owner_pve_abort is not None:
                (
                    self.state.fight_id,
                    exited_session,
                    shared_abort,
                ) = self.state.last_owner_pve_abort
                if (
                    self.state.exited is not None
                    and self.runtime.COMBAT_SESSIONS.registry.retire_disconnected_pve(
                        self.state.fight_id, exited_session
                    )
                ):
                    # Durable abort has committed and registry retirement fenced
                    # every owner. Publish removal, never another active marker.
                    with shared_abort.lock:
                        shared_abort.fight.phase = "finished"
                        shared_abort.fight.winner = None
                    from wakfu_server.combat_abandon import aborted_terminal_packets

                    losing_team = shared_abort.fight.actors[
                        exited_session.character_id
                    ].team
                    self.publish_external_marker(shared_abort)
                    self.publish_spectator_state(
                        shared_abort,
                        aborted_terminal_packets(
                            shared_abort.fight,
                            shared_abort.runtime,
                            losing_team=losing_team,
                        ),
                    )
                    if shared_abort.group_lease is not None:
                        self.state.context = shared_abort.join_context or {}
                        from wakfu_server.ecology_admin import current_available

                        self.state.key = shared_abort.group_lease[0]
                        self.state.members = current_available(
                            self.runtime.STORE, self.state.key
                        )
                        if self.state.members:
                            from wakfu_server.combat_monster_world import spawn_group

                            self.runtime.publish_available_group(
                                self.state.key, self.state.members
                            )
                            for (
                                self.state.packet
                            ) in self.runtime.HARVESTS.availability_for(
                                self.state.key[0],
                                self.state.key[1],
                                [member["id"] for member in self.state.members],
                            ):
                                self.runtime.WORLD.emit_location(
                                    self.state.key[0],
                                    self.state.key[1],
                                    *self.state.packet
                                )
                    self.runtime.record(
                        event="shared_pve_last_owner_disconnected",
                        actor_id=exited_session.character_id,
                        fight_id=self.state.fight_id,
                        durable_abort=True,
                        registry_retired=True,
                    )
                elif (
                    self.state.exited is not None
                    and self.runtime.COMBAT_SESSIONS.registry.retire_disconnected_abandon(
                        self.state.fight_id, exited_session
                    )
                ):
                    from wakfu_server.combat_abandon import aborted_terminal_packets

                    self.publish_external_marker(shared_abort)
                    self.publish_spectator_state(
                        shared_abort,
                        aborted_terminal_packets(
                            shared_abort.fight,
                            shared_abort.runtime,
                            losing_team=shared_abort.fight.actors[
                                exited_session.character_id
                            ].team,
                        ),
                    )
                    self.runtime.record(
                        event="shared_pve_abandon_disconnected",
                        actor_id=exited_session.character_id,
                        fight_id=self.state.fight_id,
                        registry_retired=True,
                    )
                else:
                    self.runtime.COMBAT_SESSIONS.registry.clear_disconnect_abort(
                        self.state.fight_id
                    )
                    shared_fight_retained = True
                    self.runtime.record(
                        event="shared_pve_disconnect_cleanup_pending",
                        actor_id=exited_session.character_id,
                        fight_id=self.state.fight_id,
                        durable_abort=self.state.exited is not None,
                        registry_retired=False,
                    )
        if (
            self.state.service == "world"
            and self.state.account_id is not None
            and self.state.character is not None
        ):
            from wakfu_server.consumable_world_lifecycle import synchronize

            self.state.synchronize = synchronize

            self.state.logout_barrier(
                "consumable_clocks",
                lambda: self.state.synchronize(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    mode="pause",
                    in_combat=self.state.fight is not None,
                ),
            )
            self.state.logout_barrier(
                "position_flush",
                lambda: self.runtime.flush_positions(
                    account_id=self.state.account_id,
                    generation=self.state.generation,
                    character_id=self.state.character["id"],
                ),
            )
            self.state.logout_barrier(
                "position_release",
                lambda: self.runtime.POSITIONS.release(
                    self.state.account_id,
                    self.state.generation,
                    self.state.character["id"],
                ),
            )
        if self.state.service == "world" and not shared_fight_retained:
            if (
                self.state.fight is not None
                and self.state.fight.phase == "finished"
                and self.state.character is not None
                and self.state.group_lease is not None
                and self.state.fight.winner
                == self.state.fight.actors[self.state.character["id"]].team
            ):
                self.state.logout_barrier(
                    "group_finish",
                    lambda: self.runtime.COMBAT_GROUPS.finish(
                        self.state.group_lease, defeated=True
                    ),
                )
            if not self.runtime.COMBAT_SESSIONS.registry.lease_generation_active(
                self.state.generation
            ):
                self.state.logout_barrier(
                    "group_release",
                    lambda: self.runtime.release_groups(self.state.generation),
                )
        if self.state.service == "world" and self.state.account_id is not None:
            if self.state.character is not None:
                self.state.exterior = self.runtime.HAVEN_BAG_EXTERIORS.discard(
                    self.state.generation,
                    (
                        self.state.bag_session.exterior_actor_id
                        if self.state.bag_session is not None
                        else self.state.character["id"]
                    ),
                )
                if self.state.exterior is not None:
                    self.state.outside, self.state.packet = self.state.exterior
                    self.state.logout_barrier(
                        "haven_bag_exterior_remove",
                        lambda: self.runtime.WORLD.emit_location(
                            self.state.outside["map_id"],
                            self.state.outside["instance_id"],
                            *self.state.packet
                        ),
                    )
                self.state.logout_barrier(
                    "world_leave",
                    lambda: self.runtime.WORLD.leave(
                        self.state.character["id"], self.state.generation
                    ),
                )
            with self.runtime.LOCK:
                if (
                    self.runtime.LIVE.get(self.state.account_id, (None,))[0]
                    == self.state.generation
                ):
                    self.runtime.LIVE.pop(self.state.account_id, None)
            self.state.logout_barrier(
                "session_end",
                lambda: self.runtime.STORE.end_session(
                    self.state.account_id, self.state.generation
                ),
            )
