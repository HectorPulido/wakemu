"""Combat actions operations for one lease-bound World session."""

from contextlib import contextmanager, nullcontext
import secrets
import struct
import os
import time
from .dispatch_result import DispatchResult


class CombatActionsMixin:
    def handle_spell_cast(self):
        from wakfu_server.combat_cast import decode_cast
        from wakfu_server.combat_execute import execute_adjacent_cast
        from wakfu_server.combat_wire import actor_state
        from wakfu_server.combat_death import death_messages

        self.state.death_messages = death_messages
        from wakfu_server.combat_results import finish_messages
        from wakfu_server.spells import default_deck

        self.state.default_deck = default_deck

        self.state.cast_request = {}
        if self.state.combat_session is not None:
            from wakfu_server.combat_shared import Transition

            self.state.Transition = Transition
            from wakfu_server.combat_cast import decode_cast
            from wakfu_server.combat_server_spell import (
                prepare_server_spell,
            )

            self.state.prepare_server_spell = prepare_server_spell
            from wakfu_server.combat_spell_commit import (
                commit_spell_transaction,
            )

            self.state.commit_spell_transaction = commit_spell_transaction
            from wakfu_server.combat_los import authoritative_visible

            self.state.authoritative_visible = authoritative_visible
            from wakfu_server.combat_death import death_messages

            self.state.death_messages = death_messages

            try:
                self.state.cast_request = decode_cast(self.state.body)
                self.state.shared = self.refresh_shared_combat()
                if self.state.shared.runtime is None:
                    raise ValueError("Fight is not ready for actions")
                if self.state.shared.runtime.awaiting_ack is not None:
                    raise ValueError("Previous turn is not synchronized")
                self.state.action_results = {}

                def shared_cast(candidate, runtime):
                    from wakfu_server.combat_owned_native_spell_entry import (
                        owned_native_spell_entry,
                    )

                    owned_stats_serializer = (
                        lambda actor, state: self.current_combat_stats(actor, state)
                    )
                    with owned_native_spell_entry(
                        runtime,
                        self.state.prepare_server_spell,
                        stats_serializer=owned_stats_serializer,
                    ):
                        characters, decks = self.runtime.COMBAT_SESSIONS.player_sources(
                            candidate
                        )
                        from wakfu_server.combat_cast_delivery_source import (
                            connected_action_source,
                        )

                        source, owner_deck = connected_action_source(
                            candidate,
                            characters,
                            decks,
                            self.state.combat_session.character_id,
                            self.state.combat_session.account_id,
                            self.state.cast_request["actor_id"],
                        )
                        with self.shared_action_incident(
                            runtime,
                            "player_spell",
                            self.state.body,
                            source,
                            owner_deck,
                            characters,
                            decks,
                        ) as incident:
                            transaction = self.state.prepare_server_spell(
                                self.state.body,
                                source,
                                self.state.TEST_MONSTERS_BY_ID,
                                candidate,
                                self.state.combat_session.account_id,
                                owner_deck,
                                action_id=runtime.action_id + 1,
                                critical=(
                                    None
                                    if self.runtime.COMBAT_TEST_CRITICAL_BRANCH
                                    == "auto"
                                    else self.runtime.COMBAT_TEST_CRITICAL_BRANCH
                                    == "critical"
                                ),
                                line_of_sight=lambda origin, target, state: self.state.authoritative_visible(
                                    source["map_id"],
                                    origin,
                                    target,
                                    state,
                                    blocking_footprints={
                                        actor.id: {actor.position[:2]}
                                        for actor in state.actors.values()
                                        if actor.hp > 0
                                    },
                                ),
                                player_characters=characters,
                                deck_blobs=decks,
                            )
                            from wakfu_server.combat_owned_spell_delivery import (
                                owned_spell_delivery,
                            )

                            with owned_spell_delivery(runtime, transaction):
                                delivery = self.state.commit_spell_transaction(
                                    runtime,
                                    transaction,
                                    stats_serializer=owned_stats_serializer,
                                    diagnostic=lambda **details: self.runtime.record(
                                        event="combat_commit_stage",
                                        **details,
                                    ),
                                )
                            packets = list(delivery)
                            for event in transaction.events:
                                if event["kind"] == "death":
                                    packets.extend(
                                        runtime.prepare_delivery(
                                            self.state.death_messages(
                                                runtime, event["actor_id"]
                                            )
                                        )
                                    )
                            if incident is not None:
                                incident.packets(packets)
                            self.state.action_results["transaction"] = transaction
                            self.state.action_results["delivery"] = delivery
                            return self.state.Transition(
                                transaction.fight, runtime, tuple(packets)
                            )

                self.state.shared_cast = shared_cast

                prepare_started = time.monotonic()
                self.runtime.COMBAT_SESSIONS.execute(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.cast_request["actor_id"],
                    self.state.shared_cast,
                    incident_request=(
                        dict(opcode=13260, body=self.state.body)
                        if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
                        else None
                    ),
                )
                prepare_finished = time.monotonic()
                self.refresh_shared_combat()
                self.drain_shared_combat()
                self.state.transaction = self.state.action_results["transaction"]
                self.state.delivery = self.state.action_results["delivery"]
                self.publish_incarnam_combat_guides(
                    self.state.cast_request["actor_id"], "cast"
                )
                self.checkpoint_fight(accepted_publication=True)
                self.runtime.record(
                    event="combat_cast",
                    requested_actor_id=self.state.cast_request["actor_id"],
                    requested_spell_uid=self.state.cast_request["spell_uid"],
                    requested_target=self.state.cast_request["target"],
                    native_actions=getattr(self.state.delivery, "native_actions", ()),
                    dispatch_ms=round(
                        (prepare_started - self.state.request_received_at) * 1000, 3
                    ),
                    prepare_ms=round((prepare_finished - prepare_started) * 1000, 3),
                    actor_id=self.state.transaction.plan["actor_id"],
                    spell_id=self.state.transaction.plan["spell_id"],
                    cast_diagnostics=self.state.transaction.plan.get(
                        "cast_diagnostics"
                    ),
                    native_casting_selection=self.state.transaction.plan.get(
                        "native_casting_selection"
                    ),
                    native_casting_flags=self.state.transaction.plan.get(
                        "native_casting_flags"
                    ),
                    native_casting_diagnostic=self.state.transaction.plan.get(
                        "native_casting_diagnostic"
                    ),
                    critical_decision=self.state.transaction.plan.get(
                        "critical_decision"
                    ),
                    costs=self.state.transaction.plan["costs"],
                    outcomes=self.state.transaction.outcomes,
                )
                if self.state.fight.phase == "finished":
                    self.complete_test_fight()
            except ValueError as error:
                self.runtime.record(
                    event="combat_cast_rejected",
                    actor_id=self.state.cast_request.get("actor_id"),
                    spell_uid=self.state.cast_request.get("spell_uid"),
                    target=self.state.cast_request.get("target"),
                    cast_diagnostics=getattr(error, "cast_diagnostics", None),
                    native_casting_result=getattr(error, "native_casting_result", None),
                    native_casting_diagnostic=getattr(
                        error, "native_casting_diagnostic", None
                    ),
                    cast_validation_code=getattr(error, "cast_validation_code", None),
                    reason=str(error),
                )
                from wakfu_server.combat_initialization_policy import (
                    safe_rejection_text,
                )

                self.state.safe_rejection_text = safe_rejection_text

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"),
                        self.state.safe_rejection_text(error),
                    ),
                )
            return DispatchResult.CONTINUE
        try:
            self.state.cast_request = decode_cast(self.state.body)
            if self.state.fight_messages.awaiting_ack is not None:
                raise ValueError("Previous turn is not synchronized")
            self.state.deck_hex = (
                self.state.character["builds"]
                .get(self.state.character.get("active_build_index", 0), {})
                .get("deck")
            )
            from wakfu_server.combat_server_spell import (
                prepare_server_spell,
            )

            self.state.prepare_server_spell = prepare_server_spell
            from wakfu_server.combat_spell_commit import (
                commit_spell_transaction,
            )

            self.state.commit_spell_transaction = commit_spell_transaction
            from wakfu_server.combat_los import authoritative_visible

            self.state.authoritative_visible = authoritative_visible

            cast_prepare_started = time.monotonic()
            self.state.transaction = self.state.prepare_server_spell(
                self.state.body,
                self.state.character,
                self.state.TEST_MONSTERS_BY_ID,
                self.state.fight,
                self.state.account_id,
                (
                    bytes.fromhex(self.state.deck_hex)
                    if self.state.deck_hex
                    else self.state.default_deck(self.state.character)
                ),
                action_id=self.state.fight_messages.action_id + 1,
                critical=(
                    None
                    if self.runtime.COMBAT_TEST_CRITICAL_BRANCH == "auto"
                    else self.runtime.COMBAT_TEST_CRITICAL_BRANCH == "critical"
                ),
                line_of_sight=lambda source, target, state: self.state.authoritative_visible(
                    self.state.character["map_id"],
                    source,
                    target,
                    state,
                    blocking_footprints={
                        a.id: {a.position[:2]}
                        for a in state.actors.values()
                        if a.hp > 0
                    },
                ),
            )
            cast_prepare_finished = time.monotonic()
            self.state.packets = self.state.commit_spell_transaction(
                self.state.fight_messages,
                self.state.transaction,
                stats_serializer=lambda actor, state: self.current_combat_stats(
                    actor, state
                ),
                diagnostic=lambda **details: self.runtime.record(
                    event="combat_commit_stage", **details
                ),
            )
            cast_commit_finished = time.monotonic()
            self.state.fight = self.state.transaction.fight
            for self.state.message_id, self.state.payload in self.state.packets:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.payload,
                )
            self.publish_incarnam_combat_guides(
                self.state.cast_request["actor_id"], "cast"
            )
            self.runtime.record(
                event="combat_cast",
                requested_actor_id=self.state.cast_request["actor_id"],
                requested_spell_uid=self.state.cast_request["spell_uid"],
                requested_target=self.state.cast_request["target"],
                native_actions=self.state.packets.native_actions,
                dispatch_ms=round(
                    (cast_prepare_started - self.state.request_received_at) * 1000, 3
                ),
                prepare_ms=round(
                    (cast_prepare_finished - cast_prepare_started) * 1000, 3
                ),
                commit_ms=round(
                    (cast_commit_finished - cast_prepare_finished) * 1000, 3
                ),
                send_ms=round((time.monotonic() - cast_commit_finished) * 1000, 3),
                actor_id=self.state.character["id"],
                spell_id=self.state.transaction.plan["spell_id"],
                cast_diagnostics=self.state.transaction.plan.get("cast_diagnostics"),
                native_casting_selection=self.state.transaction.plan.get(
                    "native_casting_selection"
                ),
                native_casting_flags=self.state.transaction.plan.get(
                    "native_casting_flags"
                ),
                native_casting_diagnostic=self.state.transaction.plan.get(
                    "native_casting_diagnostic"
                ),
                critical_decision=self.state.transaction.plan.get("critical_decision"),
                costs=self.state.transaction.plan["costs"],
                resources_before={
                    "ap": self.state.transaction.source_state["actors"][
                        str(self.state.transaction.plan["actor_id"])
                    ]["ap"],
                    "mp": self.state.transaction.source_state["actors"][
                        str(self.state.transaction.plan["actor_id"])
                    ]["mp"],
                    "wp": self.state.transaction.source_state["actors"][
                        str(self.state.transaction.plan["actor_id"])
                    ]["effect_stats"].get("4"),
                },
                resources_after={
                    "ap": self.state.fight.actors[
                        self.state.transaction.plan["actor_id"]
                    ].ap,
                    "mp": self.state.fight.actors[
                        self.state.transaction.plan["actor_id"]
                    ].mp,
                    "wp": self.state.fight.actors[
                        self.state.transaction.plan["actor_id"]
                    ].effect_stats.get(4),
                },
                outcomes=self.state.transaction.outcomes,
            )
            self.state.result = {"events": self.state.transaction.events}
            for self.state.event in self.state.result["events"]:
                if self.state.event["kind"] == "death":
                    for (
                        self.state.message_id,
                        self.state.payload,
                    ) in self.state.fight_messages.prepare_delivery(
                        self.state.death_messages(
                            self.state.fight_messages, self.state.event["actor_id"]
                        )
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            self.state.message_id,
                            self.state.payload,
                        )
            if self.state.fight.phase == "finished":
                self.complete_test_fight()
        except ValueError as error:
            self.runtime.record(
                event="combat_cast_rejected",
                actor_id=self.state.character["id"],
                spell_uid=self.state.cast_request.get("spell_uid"),
                target=self.state.cast_request.get("target"),
                cast_diagnostics=getattr(error, "cast_diagnostics", None),
                native_casting_result=getattr(error, "native_casting_result", None),
                native_casting_diagnostic=getattr(
                    error, "native_casting_diagnostic", None
                ),
                cast_validation_code=getattr(error, "cast_validation_code", None),
                reason=str(error),
            )
            from wakfu_server.combat_initialization_policy import (
                safe_rejection_text,
            )

            self.state.safe_rejection_text = safe_rejection_text

            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"),
                    self.state.safe_rejection_text(error),
                ),
            )
        return DispatchResult.FALLTHROUGH

    def handle_weapon_cast(self):
        from wakfu_server.combat_melee import prepare_server_unarmed
        from wakfu_server.combat_wire import actor_state
        from wakfu_server.combat_death import death_messages

        self.state.death_messages = death_messages
        from wakfu_server.combat_weapon import (
            decode_request,
            prepare_server_weapon,
        )

        self.state.decode_request = decode_request
        self.state.prepare_server_weapon = prepare_server_weapon

        if self.state.combat_session is not None:
            from wakfu_server.combat_shared import Transition

            self.state.Transition = Transition
            from wakfu_server.combat_spell_commit import (
                commit_spell_transaction,
            )

            self.state.commit_spell_transaction = commit_spell_transaction
            from wakfu_server.combat_los import authoritative_visible

            self.state.authoritative_visible = authoritative_visible
            from wakfu_server.combat_death import death_messages

            self.state.death_messages = death_messages
            from wakfu_server.spells import default_deck

            self.state.default_deck = default_deck

            try:
                self.state.request = self.state.decode_request(self.state.body)
                self.state.action_results = {}

                def shared_weapon(candidate, runtime):
                    from wakfu_server.combat_owned_native_spell_entry import (
                        owned_native_spell_entry,
                    )

                    owned_stats_serializer = (
                        lambda actor, state: self.current_combat_stats(actor, state)
                    )
                    with owned_native_spell_entry(
                        runtime,
                        self.state.prepare_server_weapon,
                        stats_serializer=owned_stats_serializer,
                        enabled=self.state.request["item_uid"] != -1,
                    ):
                        if runtime.awaiting_ack is not None:
                            raise ValueError("Previous turn is not synchronized")
                        characters, decks = self.runtime.COMBAT_SESSIONS.player_sources(
                            candidate
                        )
                        actor_id = self.state.request["actor_id"]
                        source = characters.get(actor_id)
                        if source is None:
                            raise ValueError("Weapon actor has no owner snapshot")
                        with self.shared_action_incident(
                            runtime,
                            (
                                "player_unarmed"
                                if self.state.request["item_uid"] == -1
                                else "player_weapon"
                            ),
                            self.state.body,
                            source,
                            decks.get(actor_id),
                            characters,
                            decks,
                        ) as incident:
                            if self.state.request["item_uid"] == -1:
                                from wakfu_server.equipment import (
                                    validate_sheet,
                                )
                                from wakfu_server.combat_melee import (
                                    prepare_server_unarmed,
                                )
                                from wakfu_server.combat_input_observation import (
                                    observe_fact,
                                )

                                selected = source["builds"].get(
                                    source.get("active_build_index", 0), {}
                                )
                                if any(
                                    row["slot"] == 15
                                    for row in validate_sheet(
                                        source,
                                        bytes.fromhex(selected.get("equipment", "")),
                                    )
                                ):
                                    raise ValueError(
                                        "Unarmed action requires the owned weapon slot to be empty"
                                    )
                                wp_current, wp_maximum = self.runtime.live_wp(
                                    candidate, actor_id
                                )
                                transaction = prepare_server_unarmed(
                                    self.state.body,
                                    source,
                                    self.state.TEST_MONSTERS_BY_ID,
                                    candidate,
                                    self.state.combat_session.account_id,
                                    unarmed=True,
                                    wp_current=wp_current,
                                    wp_maximum=wp_maximum,
                                    action_id=runtime.action_id + 1,
                                    effect_uid=observe_fact(
                                        "shared_weapon.unarmed_effect_uid",
                                        secrets.randbelow(2**60) + 1,
                                    ),
                                    critical_chance=0,
                                    caster_running_effects=(),
                                    target_running_effects=(),
                                    caster_bonuses={},
                                    target_bonuses={},
                                    mitigate=lambda damage, element, source, target, state: damage,
                                    player_characters=characters,
                                    deck_blobs=decks,
                                )
                            else:
                                transaction = self.state.prepare_server_weapon(
                                    self.state.body,
                                    source,
                                    self.state.TEST_MONSTERS_BY_ID,
                                    candidate,
                                    self.state.combat_session.account_id,
                                    decks[actor_id],
                                    action_id=runtime.action_id + 1,
                                    critical=(
                                        None
                                        if self.runtime.COMBAT_TEST_CRITICAL_BRANCH
                                        == "auto"
                                        else self.runtime.COMBAT_TEST_CRITICAL_BRANCH
                                        == "critical"
                                    ),
                                    line_of_sight=lambda origin, target, state: self.state.authoritative_visible(
                                        source["map_id"],
                                        origin,
                                        target,
                                        state,
                                        blocking_footprints={
                                            actor.id: {actor.position[:2]}
                                            for actor in state.actors.values()
                                            if actor.hp > 0
                                        },
                                    ),
                                    player_characters=characters,
                                    deck_blobs=decks,
                                )
                            from wakfu_server.combat_owned_spell_delivery import (
                                owned_spell_delivery,
                            )

                            with owned_spell_delivery(runtime, transaction):
                                delivery = self.state.commit_spell_transaction(
                                    runtime,
                                    transaction,
                                    stats_serializer=owned_stats_serializer,
                                    diagnostic=lambda **details: self.runtime.record(
                                        event="combat_commit_stage",
                                        **details,
                                    ),
                                )
                            packets = list(delivery)
                            for event in transaction.events:
                                if event["kind"] == "death":
                                    packets.extend(
                                        runtime.prepare_delivery(
                                            self.state.death_messages(
                                                runtime, event["actor_id"]
                                            )
                                        )
                                    )
                            if incident is not None:
                                incident.packets(packets)
                            self.state.action_results["transaction"] = transaction
                            self.state.action_results["delivery"] = delivery
                            return self.state.Transition(
                                transaction.fight, runtime, tuple(packets)
                            )

                self.state.shared_weapon = shared_weapon

                self.runtime.COMBAT_SESSIONS.execute(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.request["actor_id"],
                    self.state.shared_weapon,
                    incident_request=(
                        dict(opcode=12889, body=self.state.body)
                        if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
                        else None
                    ),
                )
                self.refresh_shared_combat()
                self.drain_shared_combat()
                self.checkpoint_fight(accepted_publication=True)
                self.state.transaction = self.state.action_results["transaction"]
                self.runtime.record(
                    event="combat_melee",
                    native_actions=getattr(
                        self.state.action_results["delivery"], "native_actions", ()
                    ),
                    actor_id=self.state.request["actor_id"],
                    outcomes=self.state.transaction.outcomes,
                )
                if self.state.fight.phase == "finished":
                    self.complete_test_fight()
            except ValueError as error:
                self.runtime.record(
                    event="combat_melee_rejected",
                    actor_id=self.state.character["id"],
                    item_uid=(
                        self.state.request.get("item_uid")
                        if "request" in vars(self.state)
                        else None
                    ),
                    reason=str(error),
                )
                from wakfu_server.combat_initialization_policy import (
                    safe_rejection_text,
                )

                self.state.safe_rejection_text = safe_rejection_text

                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    674,
                    self.runtime.wire.chat(
                        dict(self.state.character, name="Consola local"),
                        self.state.safe_rejection_text(error),
                    ),
                )
            return DispatchResult.CONTINUE

        try:
            if self.state.fight_messages.awaiting_ack is not None:
                raise ValueError("Previous turn is not synchronized")
            from wakfu_server.combat_spell_commit import (
                commit_spell_transaction,
            )

            self.state.commit_spell_transaction = commit_spell_transaction
            from wakfu_server.combat_los import authoritative_visible

            self.state.authoritative_visible = authoritative_visible
            from wakfu_server.spells import default_deck

            self.state.default_deck = default_deck

            self.state.request = self.state.decode_request(self.state.body)
            self.runtime.record(event="combat_weapon_request", **self.state.request)
            if self.state.request["item_uid"] == -1:
                from wakfu_server.equipment import validate_sheet

                self.state.selected = self.state.character["builds"].get(
                    self.state.character.get("active_build_index", 0), {}
                )
                if any(
                    row["slot"] == 15
                    for row in validate_sheet(
                        self.state.character,
                        bytes.fromhex(self.state.selected.get("equipment", "")),
                    )
                ):
                    raise ValueError(
                        "Unarmed action requires the owned weapon slot to be empty"
                    )
                unarmed_prepare_started = time.monotonic()
                self.state.transaction = prepare_server_unarmed(
                    self.state.body,
                    self.state.character,
                    self.state.TEST_MONSTERS_BY_ID,
                    self.state.fight,
                    self.state.account_id,
                    unarmed=True,
                    wp_current=self.runtime.live_wp(
                        self.state.fight, self.state.character["id"]
                    )[0],
                    wp_maximum=self.runtime.live_wp(
                        self.state.fight, self.state.character["id"]
                    )[1],
                    action_id=self.state.fight_messages.action_id + 1,
                    effect_uid=secrets.randbelow(2**60) + 1,
                    critical_chance=0,
                    caster_running_effects=(),
                    target_running_effects=(),
                    caster_bonuses={},
                    target_bonuses={},
                    mitigate=lambda damage, element, source, target, state: damage,
                )
                unarmed_prepare_finished = time.monotonic()
                self.state.packets = self.state.commit_spell_transaction(
                    self.state.fight_messages,
                    self.state.transaction,
                    stats_serializer=lambda actor, state: self.current_combat_stats(
                        actor, state
                    ),
                    diagnostic=lambda **details: self.runtime.record(
                        event="combat_commit_stage", **details
                    ),
                )
                unarmed_commit_finished = time.monotonic()
                self.state.fight = self.state.transaction.fight
                for self.state.message_id, self.state.payload in self.state.packets:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        self.state.message_id,
                        self.state.payload,
                    )
                    if self.state.message_id in (13509, 12613):
                        (
                            delivered_fight,
                            delivered_action,
                        ) = struct.unpack_from(">ii", self.state.payload)
                        self.runtime.record(
                            event="combat_melee_delivery",
                            fight_id=delivered_fight,
                            action_id=delivered_action,
                            opcode=self.state.message_id,
                            actor_id=self.state.character["id"],
                            item_uid=self.state.request["item_uid"],
                            target=self.state.request["target"],
                        )
                self.state.result = {
                    "events": self.state.transaction.events,
                    "damage": None,
                }
                self.runtime.record(
                    event="combat_unarmed",
                    actor_id=self.state.character["id"],
                    costs=self.state.transaction.plan["costs"],
                    prepare_ms=round(
                        (unarmed_prepare_finished - unarmed_prepare_started) * 1000,
                        3,
                    ),
                    commit_ms=round(
                        (unarmed_commit_finished - unarmed_prepare_finished) * 1000,
                        3,
                    ),
                    send_ms=round(
                        (time.monotonic() - unarmed_commit_finished) * 1000,
                        3,
                    ),
                )
            else:
                self.state.deck_hex = (
                    self.state.character["builds"]
                    .get(self.state.character.get("active_build_index", 0), {})
                    .get("deck")
                )
                weapon_prepare_started = time.monotonic()
                self.state.transaction = self.state.prepare_server_weapon(
                    self.state.body,
                    self.state.character,
                    self.state.TEST_MONSTERS_BY_ID,
                    self.state.fight,
                    self.state.account_id,
                    (
                        bytes.fromhex(self.state.deck_hex)
                        if self.state.deck_hex
                        else self.state.default_deck(self.state.character)
                    ),
                    action_id=self.state.fight_messages.action_id + 1,
                    critical=(
                        None
                        if self.runtime.COMBAT_TEST_CRITICAL_BRANCH == "auto"
                        else self.runtime.COMBAT_TEST_CRITICAL_BRANCH == "critical"
                    ),
                    line_of_sight=lambda source, target, state: self.state.authoritative_visible(
                        self.state.character["map_id"],
                        source,
                        target,
                        state,
                        blocking_footprints={
                            a.id: {a.position[:2]}
                            for a in state.actors.values()
                            if a.hp > 0
                        },
                    ),
                )
                weapon_prepare_finished = time.monotonic()
                self.state.packets = self.state.commit_spell_transaction(
                    self.state.fight_messages,
                    self.state.transaction,
                    stats_serializer=lambda actor, state: self.current_combat_stats(
                        actor, state
                    ),
                    diagnostic=lambda **details: self.runtime.record(
                        event="combat_commit_stage", **details
                    ),
                )
                weapon_commit_finished = time.monotonic()
                self.state.fight = self.state.transaction.fight
                for self.state.message_id, self.state.payload in self.state.packets:
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        self.state.message_id,
                        self.state.payload,
                    )
                self.state.result = {
                    "events": self.state.transaction.events,
                    "damage": None,
                }
                self.runtime.record(
                    event="combat_weapon",
                    actor_id=self.state.character["id"],
                    item_uid=self.state.request["item_uid"],
                    slot=self.state.request["slot"],
                    target=self.state.request["target"],
                    item_reference=self.state.transaction.plan["item_reference"],
                    item_level=self.state.transaction.plan["evaluation_level"],
                    critical_decision=self.state.transaction.plan.get(
                        "critical_decision"
                    ),
                    costs=self.state.transaction.plan["costs"],
                    prepare_ms=round(
                        (weapon_prepare_finished - weapon_prepare_started) * 1000,
                        3,
                    ),
                    commit_ms=round(
                        (weapon_commit_finished - weapon_prepare_finished) * 1000,
                        3,
                    ),
                    send_ms=round(
                        (time.monotonic() - weapon_commit_finished) * 1000,
                        3,
                    ),
                    outcomes=self.state.transaction.outcomes,
                )
            self.runtime.record(
                event="combat_melee",
                native_actions=self.state.packets.native_actions,
                actor_id=self.state.character["id"],
                damage=self.state.result["damage"],
            )
            for self.state.event in self.state.result["events"]:
                if self.state.event["kind"] == "death":
                    for (
                        self.state.message_id,
                        self.state.payload,
                    ) in self.state.fight_messages.prepare_delivery(
                        self.state.death_messages(
                            self.state.fight_messages, self.state.event["actor_id"]
                        )
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            self.state.message_id,
                            self.state.payload,
                        )
            if self.state.fight.phase == "finished":
                self.complete_test_fight()
        except ValueError as error:
            try:
                rejected_weapon = self.state.decode_request(self.state.body)
            except ValueError:
                rejected_weapon = {}
            self.runtime.record(
                event="combat_melee_rejected",
                item_uid=rejected_weapon.get("item_uid"),
                slot=rejected_weapon.get("slot"),
                target=rejected_weapon.get("target"),
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.combat_initialization_policy import (
                safe_rejection_text,
            )

            self.state.safe_rejection_text = safe_rejection_text

            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"),
                    self.state.safe_rejection_text(error),
                ),
            )
        return DispatchResult.FALLTHROUGH

    def handle_fight_abandon(self):
        from wakfu_server.combat_abandon import (
            prepare as prepare_abandon,
            placement_runtime,
        )

        self.state.placement_runtime = placement_runtime

        try:
            if self.deferred_native_combat_attachment() is not None:
                if self.state.body != b"":
                    raise ValueError("Invalid native abandon request")
                from wakfu_server.position_buffer import PositionOwnerBusy

                self.state.PositionOwnerBusy = PositionOwnerBusy

                try:
                    self.abort_waiting_publication_cohort()
                except (
                    ValueError,
                    self.state.DatabaseError,
                    self.state.PoolTimeout,
                    self.state.PositionOwnerBusy,
                ) as error:
                    self.runtime.record(
                        event="combat_publication_recovery_abort_rejected",
                        actor_id=self.state.character["id"],
                        reason=type(error).__name__,
                    )
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.information(
                            "No se pudo completar el abandono del combate pausado. "
                            "Espera un momento y vuelve a intentarlo."
                        ),
                    )
                return DispatchResult.CONTINUE
            if self.state.combat_session is not None:
                if self.state.body != b"":
                    raise ValueError("Invalid native abandon request")
                self.state.shared = self.refresh_shared_combat()
                if self.state.shared.fight.phase == "finished":
                    if (
                        getattr(self.state.shared, "full_abandon_owner", None)
                        == self.state.combat_session
                    ):
                        return (
                            DispatchResult.CONTINUE
                        )  # Its already-queued native abort is authoritative.
                    # Retry the original terminal settlement;
                    # a finished victory must not become defeat.
                    self.complete_test_fight()
                elif getattr(self.state.shared, "is_duel", False):
                    if not self.runtime.COMBAT_SESSIONS.registry.forfeit_duel(
                        self.state.combat_session, reason="defeat"
                    ):
                        raise ValueError("Friendly duel can no longer be forfeited")
                    self.refresh_shared_combat()
                    self.complete_test_fight()
                    self.runtime.record(
                        event="friendly_duel_forfeited",
                        actor_id=self.state.character["id"],
                        fight_id=self.state.fight.id,
                    )
                else:
                    from wakfu_server.combat_pve_withdraw import (
                        has_other_live_owner,
                    )

                    self.state.has_other_live_owner = has_other_live_owner

                    if self.state.has_other_live_owner(
                        self.state.shared.fight, self.state.combat_session
                    ):
                        self.state.pve_withdrawal_pending = (
                            self.runtime.COMBAT_SESSIONS.withdraw_pve(
                                self.state.combat_session,
                                self.state.character,
                                self.state.body,
                            )
                        )
                        self.publish_external_marker(self.state.shared)
                        self.state.character.update(
                            self.state.pve_withdrawal_pending["character"]
                        )
                        for self.state.packet in self.state.pve_withdrawal_pending[
                            "withdrawal"
                        ].private_packets:
                            self.runtime.send(
                                self.state.connection,
                                self.state.service,
                                *self.state.packet,
                            )
                        self.runtime.record(
                            event="shared_pve_member_withdrawn",
                            actor_id=self.state.character["id"],
                            fight_id=self.state.fight.id,
                        )
                        # Private native continuation is independent of the live
                        # encounter. This socket must not tick, abort or release it.
                        self.state.fight = self.state.fight_messages = None
                        self.state.combat_session = self.state.group_lease = None
                        self.state.loaded = False
                        return DispatchResult.CONTINUE
                    self.state.abandon_messages = self.state.placement_runtime(
                        self.state.fight, self.state.shared.runtime
                    )
                    with self.state.shared.lock:
                        # Snapshot/readiness/turn transitions share
                        # this lock; publish abandon only after its
                        # HP and terminal state are committed.
                        from wakfu_server.combat_shared_abandon import (
                            requires_shared_abort,
                        )

                        self.state.requires_shared_abort = requires_shared_abort

                        if self.state.requires_shared_abort(
                            self.state.shared.fight, self.state.combat_session
                        ):
                            self.state.abandoned = (
                                self.runtime.COMBAT_SESSIONS.abandon_shared_pve(
                                    self.state.combat_session,
                                    self.state.character,
                                    self.state.body,
                                    groups=self.runtime.COMBAT_GROUPS,
                                    shared=self.state.shared,
                                )
                            )
                            self.state.fight = self.state.shared.fight
                            self.state.fight_messages = self.state.shared.runtime
                        else:
                            self.state.abandoned = prepare_abandon(
                                self.runtime.STORE,
                                self.state.account_id,
                                self.state.generation,
                                self.state.character,
                                self.state.abandon_messages,
                                self.state.body,
                            )
                            self.state.fight_messages = (
                                self.state.shared.runtime
                            ) = self.state.abandon_messages
                        self.state.character.update(
                            self.refresh_owned_character(
                                self.state.abandoned["character"]
                            )
                        )
                    # Checkpoint lookup and outbox draining acquire
                    # the registry. Keep them outside the per-fight
                    # mutation lock, after durable abandonment.
                    if self.state.abandoned["applied"]:
                        self.checkpoint_fight("aborted")
                    for (
                        self.state.message_id,
                        self.state.payload,
                    ) in self.state.fight_messages.prepare_delivery(
                        self.state.abandoned["packets"]
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            self.state.message_id,
                            self.state.payload,
                        )
                    self.publish_external_marker(self.state.shared)
                    self.publish_spectator_state(
                        self.state.shared, self.state.abandoned["packets"]
                    )
                    if self.state.abandoned.get("shared_full_abort"):
                        self.publish_full_abandon_group(
                            self.state.shared, self.state.abandoned
                        )
                        self.drain_shared_combat()
                    self.runtime.record(
                        event="shared_pve_abandoned_waiting_return",
                        actor_id=self.state.character["id"],
                        fight_id=self.state.fight.id,
                        applied=self.state.abandoned["applied"],
                    )
                return DispatchResult.CONTINUE
            self.state.abandon_messages = self.state.placement_runtime(
                self.state.fight, self.state.fight_messages
            )
            self.state.abandoned = prepare_abandon(
                self.runtime.STORE,
                self.state.account_id,
                self.state.generation,
                self.state.character,
                self.state.abandon_messages,
                self.state.body,
            )
            self.state.fight_messages = self.state.abandon_messages
            self.state.character.update(
                self.refresh_owned_character(self.state.abandoned["character"])
            )
            if self.state.abandoned["applied"]:
                self.checkpoint_fight("aborted")
            for (
                self.state.message_id,
                self.state.payload,
            ) in self.state.fight_messages.prepare_delivery(
                self.state.abandoned["packets"]
            ):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.payload,
                )
            self.runtime.record(
                event="combat_abandoned_waiting_return",
                actor_id=self.state.character["id"],
                fight_id=self.state.fight.id,
                applied=self.state.abandoned["applied"],
            )
        except ValueError as error:
            self.runtime.record(
                event="combat_abandon_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.combat_initialization_policy import (
                safe_rejection_text,
            )

            self.state.safe_rejection_text = safe_rejection_text

            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"),
                    self.state.safe_rejection_text(error),
                ),
            )
        return DispatchResult.FALLTHROUGH

    def handle_aborted_return_ack(self):
        try:
            self.finish_aborted_native_return(self.state.body)
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.record(
                event="combat_aborted_native_return_rejected",
                actor_id=(
                    None if self.state.character is None else self.state.character["id"]
                ),
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_withdrawal_ack(self):
        try:
            self.state.pending = self.state.pve_withdrawal_pending
            self.state.owner = self.runtime.COMBAT_SESSIONS.session(
                self.state.account_id, self.state.generation, self.state.character
            )
            self.state.returned = self.runtime.COMBAT_SESSIONS.return_withdrawn_pve(
                self.state.owner,
                self.state.pending["withdrawal"].fight.id,
                self.state.character,
                self.state.body,
                wp=self.runtime.COMBAT_TEST_WP,
                pending=self.state.pending,
            )
            self.state.connection.native_fight_id = None
            self.state.character.update(
                self.refresh_owned_character(self.state.returned["character"])
            )
            for self.state.packet in self.state.returned["packets"]:
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.attach_combat_return_position()
            self.state.position = {
                key: self.state.character[key] for key in ("x", "y", "z")
            }
            self.state.movement_state = self.runtime.Movement(self.state.position)
            self.runtime.WORLD.leave(self.state.character["id"], self.state.generation)
            for self.state.packet in self.combat_return_bootstrap():
                self.runtime.send(
                    self.state.connection, self.state.service, *self.state.packet
                )
            self.runtime.join_world(
                self.state.generation, self.state.connection, self.state.character
            )
            self.state.loaded = True
            self.mark_static_sync_pending()
            self.state.pve_withdrawal_pending = None
            self.runtime.record(
                event="shared_pve_withdrawal_returned",
                actor_id=self.state.character["id"],
                fight_id=self.state.pending["withdrawal"].fight.id,
            )
            self.release_completed_combat_return_aliases()
        except ValueError as error:
            self.runtime.record(
                event="shared_pve_withdrawal_return_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_spectator_return_ack(self):
        try:
            pending_ack = self.state.spectator_terminal_pending
            current_observer = self.spectator_session_for_current_character()
            if not self.runtime.STORE.current_session(
                self.state.account_id, self.state.generation
            ) or (
                current_observer != pending_ack.session
                or self.state.fight is not None
                or self.state.combat_session is not None
            ):
                raise ValueError("Spectator terminal ACK has a stale session")
            pending_ack.validate(current_observer, self.state.body)
            self.state.connection.native_fight_id = None
            self.refresh_owned_world_after_spectating()
            self.state.spectator_terminal_pending = None
            self.runtime.record(
                event="combat_spectator_terminal_returned",
                actor_id=self.state.character["id"],
                fight_id=pending_ack.fight_id,
                native_return_ack=True,
                world_refreshed=True,
            )
        except ValueError as error:
            self.runtime.record(
                event="combat_spectator_terminal_return_rejected",
                actor_id=(
                    None if self.state.character is None else self.state.character["id"]
                ),
                fight_id=(
                    self.state.spectator_terminal_pending.fight_id
                    if self.state.spectator_terminal_pending is not None
                    else None
                ),
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_combat_return_ack(self):
        from wakfu_server.combat_lifecycle import return_to_world
        from wakfu_server.combat_death import despawn_monster

        try:
            self.state.shared_state = None
            self.state.shared_return = self.state.combat_session is not None
            duel_return = False
            self.state.abandoned = (
                getattr(self.state.fight_messages, "abandon_owner", None) is not None
            )
            if self.state.shared_return:
                from wakfu_server.combat_pve_withdraw import (
                    has_other_live_owner,
                )

                self.state.has_other_live_owner = has_other_live_owner

                self.refresh_shared_combat()
                self.state.shared_state = self.runtime.COMBAT_SESSIONS.registry.lookup(
                    self.state.fight.id
                )
                if self.state.abandoned:
                    if (
                        getattr(self.state.shared_state, "is_duel", False)
                        or self.state.has_other_live_owner(
                            self.state.shared_state.fight, self.state.combat_session
                        )
                        or self.state.shared_state.participants.get(
                            self.state.account_id
                        )
                        != self.state.combat_session
                        or self.state.shared_state.settlement_ready
                    ):
                        raise ValueError(
                            "Only a single-owner PvE fight can use abandon return"
                        )
                elif not self.state.shared_state.settlement_ready:
                    raise ValueError("Shared fight settlement is not ready for return")
            if self.state.abandoned:
                from wakfu_server.combat_abandon import (
                    return_to_world as return_abandon,
                )

                if (
                    self.state.shared_return
                    and getattr(self.state.shared_state, "full_abandon_owner", None)
                    is not None
                ):
                    self.state.returned = (
                        self.runtime.COMBAT_SESSIONS.return_withdrawn_pve(
                            self.state.combat_session,
                            self.state.fight.id,
                            self.state.character,
                            self.state.body,
                            wp=self.runtime.COMBAT_TEST_WP,
                            pending=self.state.shared_state.withdrawals[
                                self.state.account_id
                            ],
                        )
                    )
                elif self.state.shared_return:
                    with self.state.shared_state.lock:
                        self.state.returned = return_abandon(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            self.state.character,
                            self.state.fight_messages,
                            self.state.body,
                            wp=self.runtime.COMBAT_TEST_WP,
                        )
                else:
                    self.state.returned = return_abandon(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.fight_messages,
                        self.state.body,
                        wp=self.runtime.COMBAT_TEST_WP,
                    )
            else:
                if (
                    self.state.fight.phase != "finished"
                    or self.state.fight.winner not in (0, 1)
                ):
                    raise ValueError("Normal return requires a resolved fight outcome")
                duel_return = bool(
                    self.state.shared_return
                    and getattr(self.state.shared_state, "is_duel", False)
                )
                if duel_return:
                    from wakfu_server.friendly_duels import (
                        return_packets as duel_return_packets,
                    )

                    self.state.returned = duel_return_packets(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                        self.state.fight,
                        self.state.body,
                        wp=self.runtime.COMBAT_TEST_WP,
                    )
                else:
                    self.state.returned = return_to_world(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.fight_messages,
                        self.state.body,
                        wp=self.runtime.COMBAT_TEST_WP,
                    )
            self.state.character.update(
                self.refresh_owned_character(self.state.returned["character"])
            )
            for self.state.message_id, self.state.payload in self.state.returned[
                "packets"
            ]:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.payload,
                )
            self.state.owned_ids = []
            if (
                self.state.character["map_id"] in (1387, 1388)
                and self.state.TEST_MONSTERS
            ):
                from wakfu_server.achievements.rii_lesson_visibility import (
                    owned_actor_ids,
                )
                from wakfu_server.combat_monster_world import remove_message

                self.state.remove_message = remove_message

                with self.runtime.STORE.connection() as self.state.lesson_db:
                    self.state.owned_ids = owned_actor_ids(
                        self.state.lesson_db,
                        self.state.TEST_MONSTERS,
                        self.state.character["id"],
                    )
                if self.state.owned_ids:
                    # A lesson may end successfully with the sack
                    # still alive; the ordinary dead-actor cleanup
                    # therefore cannot remove its world sprite.
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        *self.state.remove_message(self.state.owned_ids),
                    )
            if not self.state.abandoned and not duel_return:
                from wakfu_server.combat_death import dead_world_removals

                ordinary_ids = [
                    m["id"]
                    for m in self.state.TEST_MONSTERS
                    if m["id"] not in self.state.owned_ids
                ]
                for self.state.packet in (
                    dead_world_removals(self.state.fight, ordinary_ids)
                    if ordinary_ids
                    else []
                ):
                    self.runtime.send(
                        self.state.connection, self.state.service, *self.state.packet
                    )
                self.runtime.record(
                    event="dead_monsters_removed_from_world",
                    fight_id=self.state.fight.id,
                    actor_ids=[
                        m["id"]
                        for m in self.state.TEST_MONSTERS
                        if self.state.fight.actors[m["id"]].hp == 0
                    ],
                )
            # This callback follows native aUH cleanup. Restore the
            # actual owned map, not an inherited fight/report state.
            from wakfu_server.position_lifecycle import (
                PendingPositionReturn,
            )

            self.state.position_scope = dict(
                account_id=self.state.account_id,
                generation=self.state.generation,
                character_id=self.state.character["id"],
            )
            pending_retry = PendingPositionReturn(now=time.monotonic())
            self.state.pending_started = time.monotonic()

            def position_busy(error, attempt):
                if attempt == 1 or attempt % 30 == 0:
                    self.runtime.record(
                        event="combat_return_position_pending",
                        actor_id=self.state.character["id"],
                        fight_id=self.state.fight.id,
                        attempt=attempt,
                        pending_seconds=round(
                            time.monotonic() - self.state.pending_started, 3
                        ),
                        reason=self.runtime.redact(str(error)),
                    )

            def finish_return():
                self.finish_combat_return_after_position_flush(
                    abandoned=self.state.abandoned,
                    shared_return=self.state.shared_return,
                    shared_state=self.state.shared_state,
                )
                self.release_completed_combat_return_aliases()

            self.state.finish_return = finish_return

            if not pending_retry.attempt(
                now=time.monotonic(),
                flush=lambda: self.runtime.flush_positions(**self.state.position_scope),
                complete=self.state.finish_return,
                busy=position_busy,
            ):
                self.state.pending_combat_return = dict(
                    retry=pending_retry,
                    scope=self.state.position_scope,
                    complete=self.state.finish_return,
                    fight_id=self.state.fight.id,
                    started_at=self.state.pending_started,
                    held_requests=0,
                )
        except ValueError as error:
            self.runtime.record(
                event="combat_return_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_fight_direction(self):
        from wakfu_server.combat_orientation import apply as orient_actor
        from wakfu_server.combat_abandon import placement_runtime

        self.state.placement_runtime = placement_runtime

        try:
            self.state.orientation_runtime = self.state.placement_runtime(
                self.state.fight, self.state.fight_messages
            )
            oriented = orient_actor(
                self.state.orientation_runtime, self.state.account_id, self.state.body
            )
            self.state.fight_messages = self.state.orientation_runtime
            for (
                self.state.message_id,
                self.state.payload,
            ) in self.state.fight_messages.prepare_delivery(oriented["packets"]):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.payload,
                )
            self.checkpoint_fight()
            # Combat keeps its sequenced action. World observers need
            # the distinct ctz event and persisted world snapshot.
            self.state.actor_id, self.state._ = struct.unpack(">qB", self.state.body)
            if self.state.actor_id == self.state.character["id"]:
                from wakfu_server.world_orientation import (
                    save as save_orientation,
                )

                self.state.save_orientation = save_orientation

                try:
                    self.runtime.POSITIONS.flush(
                        account_id=self.state.account_id,
                        generation=self.state.generation,
                        character_id=self.state.actor_id,
                    )
                    self.state.changed = self.state.save_orientation(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.actor_id,
                        oriented["direction"],
                    )
                    self.state.character = dict(
                        self.state.character, direction=self.state.changed["direction"]
                    )
                    self.runtime.POSITIONS.attach(
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                    )
                    self.runtime.WORLD.update(
                        self.state.generation,
                        self.state.character,
                        *self.state.changed["packet"],
                        include_sender=False,
                    )
                except ValueError as error:
                    self.runtime.record(
                        event="world_orientation_rejected",
                        actor_id=self.state.actor_id,
                        reason=str(error),
                    )
            self.runtime.record(
                event="combat_orientation",
                actor_id=self.state.character["id"],
                direction=oriented["direction"],
            )
        except ValueError as error:
            self.runtime.record(
                event="combat_orientation_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_fight_movement(self):
        from wakfu_server.combat_movement_runtime import (
            apply_client,
            decode_request,
        )

        self.state.apply_client = apply_client
        self.state.decode_request = decode_request
        from wakfu_server.combat_actor import actual_actor_stats

        if self.state.combat_session is not None:
            from wakfu_server.combat_shared import Transition

            self.state.Transition = Transition

            self.state.movement_result = {}
            try:
                (
                    self.state.movement_actor_id,
                    self.state.movement_path,
                ) = self.state.decode_request(self.state.body)
                self.state.movement_result[
                    "diagnostic"
                ] = self.runtime.movement_summary(
                    self.state.movement_actor_id, self.state.movement_path
                )

                def shared_move(candidate, runtime):
                    characters, decks = self.runtime.COMBAT_SESSIONS.player_sources(
                        candidate
                    )
                    from wakfu_server.combat_cast_delivery_source import (
                        connected_action_source,
                    )

                    source, owner_deck = connected_action_source(
                        candidate,
                        characters,
                        decks,
                        self.state.combat_session.character_id,
                        self.state.combat_session.account_id,
                        self.state.movement_actor_id,
                    )
                    with self.shared_action_incident(
                        runtime,
                        "move",
                        self.state.body,
                        source,
                        owner_deck,
                        characters,
                        decks,
                    ) as incident:
                        self.state.movement_result[
                            "diagnostic"
                        ] = self.runtime.movement_summary(
                            self.state.movement_actor_id,
                            self.state.movement_path,
                            candidate.actors.get(self.state.movement_actor_id),
                        )
                        from wakfu_server.combat_owned_movement_step import (
                            owned_native_movement,
                        )

                        with owned_native_movement(
                            runtime,
                            self.area_movement_provider,
                            enabled=self.area_movement_provider
                            is self.state.native_area_movement_provider,
                        ):
                            packets, event = self.state.apply_client(
                                runtime,
                                self.state.combat_session.account_id,
                                self.state.body,
                                self.current_combat_stats,
                                runtime_stats_serializer=self.current_combat_stats,
                                area_provider=(
                                    self.area_movement_provider
                                    if os.environ.get(
                                        "WAKFU_NATIVE_AREA_CALLBACKS", "1"
                                    )
                                    == "1"
                                    else None
                                ),
                            )
                        packets = runtime.prepare_delivery(packets)
                        if incident is not None:
                            incident.packets(packets)
                        self.state.movement_result["event"] = event
                        return self.state.Transition(candidate, runtime, tuple(packets))

                self.runtime.COMBAT_SESSIONS.execute(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.movement_actor_id,
                    shared_move,
                    incident_request=(
                        dict(opcode=12161, body=self.state.body)
                        if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
                        else None
                    ),
                )
                self.refresh_shared_combat()
                self.drain_shared_combat()
                self.checkpoint_fight(accepted_publication=True)
                self.publish_incarnam_combat_guides(
                    self.state.movement_actor_id, "move"
                )
                self.runtime.record(
                    event="combat_movement",
                    actor_id=self.state.movement_actor_id,
                    movement=self.state.movement_result.get("event"),
                )
            except ValueError as error:
                self.runtime.record(
                    event="combat_movement_rejected",
                    actor_id=self.state.combat_session.character_id,
                    reason=str(error),
                    **self.state.movement_result.get("diagnostic", {}),
                )
                from wakfu_server.combat_movement_rejection import (
                    queue_shared_movement_rejection,
                )

                try:
                    if queue_shared_movement_rejection(
                        self.runtime.COMBAT_SESSIONS.registry,
                        self.state.combat_session,
                        self.state.fight.id,
                        self.state.body,
                    ):
                        self.drain_shared_combat()
                except (
                    ValueError,
                    self.state.DatabaseError,
                    self.state.PoolTimeout,
                ) as correction_error:
                    self.runtime.record(
                        event="combat_movement_correction_deferred",
                        actor_id=self.state.combat_session.character_id,
                        error_type=type(correction_error).__name__,
                    )
            return DispatchResult.CONTINUE

        try:
            self.state.packets, self.state.event = self.state.apply_client(
                self.state.fight_messages,
                self.state.account_id,
                self.state.body,
                self.current_combat_stats,
                runtime_stats_serializer=self.current_combat_stats,
                area_provider=(
                    self.area_movement_provider
                    if os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1"
                    else None
                ),
            )
            self.state.packets = self.state.fight_messages.prepare_delivery(
                self.state.packets
            )
            for self.state.message_id, self.state.payload in self.state.packets:
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.payload,
                )
            if self.state.fight.phase == "finished":
                self.complete_test_fight()
            self.publish_incarnam_combat_guides(self.state.character["id"], "move")
            self.runtime.record(
                event="combat_movement",
                actor_id=self.state.character["id"],
                movement=self.state.event,
            )
        except ValueError as error:
            self.runtime.record(
                event="combat_movement_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.combat_movement_rejection import (
                movement_rejection_packet,
            )

            try:
                correction = movement_rejection_packet(
                    self.state.fight_messages,
                    self.state.account_id,
                    self.state.body,
                    session_is_current=self.runtime.STORE.current_character_session(
                        self.state.account_id,
                        self.state.generation,
                        self.state.character["id"],
                    ),
                )
                if correction is not None:
                    self.runtime.send(
                        self.state.connection, self.state.service, *correction
                    )
            except (
                ValueError,
                self.state.DatabaseError,
                self.state.PoolTimeout,
            ) as correction_error:
                self.runtime.record(
                    event="combat_movement_correction_deferred",
                    actor_id=self.state.character["id"],
                    error_type=type(correction_error).__name__,
                )
        return DispatchResult.FALLTHROUGH

    def handle_fight_turn_end(self):
        if self.state.combat_session is not None:
            from wakfu_server.combat_shared import Transition

            self.state.Transition = Transition

            try:
                self.state.actor_id, self.state.actor_turn = struct.unpack(
                    ">qh", self.state.body
                )

                def shared_end_turn(candidate, runtime):
                    with self.shared_action_incident(
                        runtime,
                        "end_turn",
                        self.state.body,
                        None,
                        None,
                        None,
                        None,
                        actor_id=self.state.actor_id,
                        turn_id=self.state.actor_turn,
                    ) as incident:
                        from contextlib import nullcontext
                        from types import MethodType
                        from wakfu_server.combat_runtime_messages import (
                            RuntimeMessages,
                        )
                        from wakfu_server.combat_retained_gc_authority import (
                            capture_native_callbacks,
                        )
                        from wakfu_server.combat_native_action_ids import (
                            owned_native_delivery,
                        )

                        boundary = runtime.end_turn
                        owned = (
                            type(runtime) is RuntimeMessages
                            and runtime.fight is candidate
                            and type(boundary) is MethodType
                            and boundary.__self__ is runtime
                            and boundary.__func__ is RuntimeMessages.end_turn
                            and capture_native_callbacks(runtime) is not None
                        )
                        # Registry.execute owns this disposable pair;
                        # failures escape this callback before publication.
                        with (
                            owned_native_delivery(runtime, boundary.__func__)
                            if owned
                            else nullcontext()
                        ):
                            if owned and os.environ.get(
                                "WAKFU_RIFT_ACTION_CAPTURE_DIR"
                            ):
                                from wakfu_server.combat_rift_action_capture import (
                                    capture_end_turn,
                                )

                                packets = capture_end_turn(
                                    runtime,
                                    self.state.combat_session.account_id,
                                    self.state.actor_id,
                                    self.state.actor_turn,
                                    boundary=boundary,
                                )
                            else:
                                packets = boundary(
                                    self.state.combat_session.account_id,
                                    self.state.actor_id,
                                    self.state.actor_turn,
                                )
                        if incident is not None:
                            incident.packets(packets)
                        return self.state.Transition(candidate, runtime, tuple(packets))

                self.runtime.COMBAT_SESSIONS.execute(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.actor_id,
                    shared_end_turn,
                    incident_request=(
                        dict(opcode=12403, body=self.state.body)
                        if os.environ.get("WAKFU_COMBAT_INCIDENT_DIR")
                        else (
                            dict(opcode=12403)
                            if (
                                os.environ.get("WAKFU_REGISTRY_EXECUTE_CPROFILE") == "1"
                                or os.environ.get(
                                    "WAKFU_REGISTRY_EXECUTE_ALLOCATION_TRACE"
                                )
                                == "1"
                            )
                            else None
                        )
                    ),
                )
                self.refresh_shared_combat()
                if self.state.fight_messages.awaiting_ack is not None:
                    self.runtime.COMBAT_SESSIONS.registry.arm_ack(
                        self.state.fight.id, self.state.fight_messages.awaiting_ack
                    )
                self.drain_shared_combat()
                self.checkpoint_fight(accepted_publication=True)
                self.publish_incarnam_combat_guides(self.state.actor_id, "end_turn")
                if self.state.fight.phase == "finished":
                    self.complete_test_fight()
            except ValueError as error:
                self.runtime.record(
                    event="combat_test_end_turn_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
            return DispatchResult.CONTINUE
        try:
            self.state.actor_id, self.state.actor_turn = struct.unpack(
                ">qh", self.state.body
            )
            for (
                self.state.message_id,
                self.state.payload,
            ) in self.state.fight_messages.end_turn(
                self.state.account_id, self.state.actor_id, self.state.actor_turn
            ):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.payload,
                )
            self.publish_incarnam_combat_guides(self.state.actor_id, "end_turn")
            if self.state.fight.phase == "finished":
                self.complete_test_fight()
        except ValueError as error:
            self.runtime.record(
                event="combat_test_end_turn_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
            from wakfu_server.combat_initialization_policy import (
                safe_rejection_text,
            )

            self.state.safe_rejection_text = safe_rejection_text

            self.runtime.send(
                self.state.connection,
                self.state.service,
                674,
                self.runtime.wire.chat(
                    dict(self.state.character, name="Consola local"),
                    self.state.safe_rejection_text(error),
                ),
            )
            # Only an owned, still-active turn may be reannounced.
            # Stale or foreign requests must not clear another
            # actor's native synchronization barrier.
            from wakfu_server.combat_effective_control import (
                effective_input_owner,
            )

            current = self.state.fight.current
            if (
                self.state.fight.phase == "active"
                and current is not None
                and effective_input_owner(self.state.fight, current)
                == self.state.account_id
                and self.state.fight_messages.awaiting_ack is None
            ):
                recovery_body = struct.pack(">i", self.state.fight.id)
                if self.state.combat_session is not None:
                    self.state.published = (
                        self.runtime.COMBAT_SESSIONS.recover_timeline(
                            self.state.combat_session,
                            self.state.fight.id,
                            recovery_body,
                            now_ms=int(time.time() * 1000),
                        )
                    )
                    self.refresh_shared_combat()
                    self.drain_shared_combat()
                    if self.state.published:
                        self.checkpoint_fight()
                else:
                    for (
                        self.state.message_id,
                        self.state.payload,
                    ) in self.state.fight_messages.recover(
                        self.state.account_id,
                        recovery_body,
                        now_ms=int(time.time() * 1000),
                    ):
                        self.runtime.send(
                            self.state.connection,
                            self.state.service,
                            self.state.message_id,
                            self.state.payload,
                        )
                self.runtime.record(
                    event="combat_turn_rejection_recovered",
                    fight_id=self.state.fight.id,
                    actor_id=current.id,
                )
        return DispatchResult.FALLTHROUGH

    def handle_fight_ack(self):
        try:
            if self.state.combat_session is not None:
                self.state.published = self.runtime.COMBAT_SESSIONS.recover_timeline(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.body,
                    now_ms=int(time.time() * 1000),
                )
                self.refresh_shared_combat()
                self.drain_shared_combat()
                if self.state.published:
                    self.checkpoint_fight()
            else:
                for (
                    self.state.message_id,
                    self.state.payload,
                ) in self.state.fight_messages.recover(
                    self.state.account_id,
                    self.state.body,
                    now_ms=int(time.time() * 1000),
                ):
                    self.runtime.send(
                        self.state.connection,
                        self.state.service,
                        self.state.message_id,
                        self.state.payload,
                    )
            self.runtime.record(
                event="combat_timeline_recovered",
                actor_id=self.state.character["id"],
                fight_id=self.state.fight.id,
            )
            if self.runtime.CHECKPOINT_WRITER.recover_pending(
                self.state.fight.id,
                self.state.account_id,
                self.state.generation,
                request_token=(
                    13332,
                    bytes(self.state.body),
                    self.state.last_session_renewal,
                ),
            ):
                self.runtime.record(
                    event="combat_checkpoint_owned_recovery",
                    actor_id=self.state.character["id"],
                    fight_id=self.state.fight.id,
                )
            # Recovery supersedes the outstanding turn ACK. A
            # server-controlled actor otherwise has no remaining
            # packet that can trigger its bounded turn policy.
            if self.state.fight.phase == "finished":
                self.complete_test_fight()
            else:
                self.pass_test_monster_turn()
        except ValueError as error:
            self.runtime.record(
                event="combat_recovery_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_fight_ack_followup(self):
        if self.state.combat_session is not None:
            try:
                released = self.runtime.COMBAT_SESSIONS.acknowledge(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.body,
                    lambda candidate, runtime, ack_body: runtime.acknowledge_turn(
                        ack_body
                    ),
                )
                self.refresh_shared_combat()
                self.drain_shared_combat()
                if released:
                    self.checkpoint_fight(accepted_publication=True)
                    if self.state.fight.phase == "finished":
                        self.complete_test_fight()
                    else:
                        self.pass_test_monster_turn()
            except ValueError as error:
                self.runtime.record(
                    event="combat_test_turn_ack_rejected",
                    actor_id=self.state.character["id"],
                    reason=str(error),
                )
            return DispatchResult.CONTINUE
        try:
            for (
                self.state.message_id,
                self.state.payload,
            ) in self.state.fight_messages.acknowledge_turn(self.state.body):
                self.runtime.send(
                    self.state.connection,
                    self.state.service,
                    self.state.message_id,
                    self.state.payload,
                )
            if self.state.fight.phase == "finished":
                self.complete_test_fight()
            else:
                self.pass_test_monster_turn()
        except ValueError as error:
            self.runtime.record(
                event="combat_test_turn_ack_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_captured_roster(self):
        from wakfu_server.captured_roster_management import (
            manage,
            decode_request,
        )

        self.state.manage = manage
        self.state.decode_request = decode_request
        from wakfu_server.captured_roster_selection import (
            owned_request_character,
        )

        self.state.owned_request_character = owned_request_character
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout

        try:
            (
                self.state.requested_owner_id,
                self.state._,
                self.state._,
            ) = self.state.decode_request(self.state.opcode, self.state.body)
            self.state.managed_record = {}
            if self.state.combat_session is not None:
                from wakfu_server.combat_shared import Transition

                self.state.Transition = Transition

                def shared_manage(candidate, runtime):
                    owner = self.state.owned_request_character(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.requested_owner_id,
                        fight=candidate,
                    )
                    self.state.managed_record.update(
                        self.state.manage(
                            self.runtime.STORE,
                            self.state.account_id,
                            self.state.generation,
                            owner,
                            self.state.opcode,
                            self.state.body,
                            fight=candidate,
                        )
                    )
                    return self.state.Transition(candidate, runtime, ())

                self.runtime.COMBAT_SESSIONS.execute(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.requested_owner_id,
                    shared_manage,
                    require_turn=self.state.requested_owner_id
                    != self.state.character["id"],
                )
                self.refresh_shared_combat()
                self.checkpoint_fight()
            else:
                self.state.managed_record = self.state.manage(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.generation,
                    self.state.character,
                    self.state.opcode,
                    self.state.body,
                    fight=self.state.fight,
                )
                if self.state.fight is not None:
                    self.checkpoint_fight()
            if self.state.requested_owner_id == self.state.character["id"]:
                self.state.character["captured_roster"] = self.state.managed_record
            self.runtime.record(
                event="symbiot_management",
                actor_id=self.state.requested_owner_id,
                opcode=self.state.opcode,
                selected_slot=self.state.managed_record["selected_slot"],
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.record(
                event="symbiot_management_rejected",
                actor_id=self.state.character["id"],
                opcode=self.state.opcode,
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_captured_selection(self):
        from wakfu_server.captured_roster_selection import (
            select,
            request_owner,
            owned_request_character,
        )

        self.state.select = select
        self.state.owned_request_character = owned_request_character
        from psycopg import Error as DatabaseError

        self.state.DatabaseError = DatabaseError
        from psycopg_pool import PoolTimeout

        self.state.PoolTimeout = PoolTimeout

        try:
            self.state.requested_owner_id = request_owner(self.state.body)
            self.state.selected_record = {}
            if self.state.combat_session is not None:
                from wakfu_server.combat_shared import Transition

                self.state.Transition = Transition

                def shared_select(candidate, runtime):
                    owner = self.state.owned_request_character(
                        self.runtime.STORE,
                        self.state.account_id,
                        self.state.generation,
                        self.state.character,
                        self.state.requested_owner_id,
                        fight=candidate,
                    )
                    self.state.selected_record.update(
                        self.state.select(
                            self.runtime.STORE,
                            self.state.account_id,
                            owner,
                            self.state.body,
                            fight=candidate,
                        )
                    )
                    return self.state.Transition(candidate, runtime, ())

                self.runtime.COMBAT_SESSIONS.execute(
                    self.state.combat_session,
                    self.state.fight.id,
                    self.state.requested_owner_id,
                    shared_select,
                    require_turn=self.state.requested_owner_id
                    != self.state.character["id"],
                )
                self.refresh_shared_combat()
                self.checkpoint_fight()
            else:
                self.state.selected_record = self.state.select(
                    self.runtime.STORE,
                    self.state.account_id,
                    self.state.character,
                    self.state.body,
                    fight=self.state.fight,
                )
                if self.state.fight is not None:
                    self.checkpoint_fight()
            if self.state.requested_owner_id == self.state.character["id"]:
                self.state.character["captured_roster"] = self.state.selected_record
            self.runtime.record(
                event="symbiot_selection",
                actor_id=self.state.requested_owner_id,
                slot=self.state.selected_record["selected_slot"],
            )
        except (ValueError, self.state.DatabaseError, self.state.PoolTimeout) as error:
            self.runtime.record(
                event="symbiot_selection_rejected",
                actor_id=self.state.character["id"],
                reason=str(error),
            )
        return DispatchResult.FALLTHROUGH

    def handle_captured_view(self):
        if not self.sync_loaded_world_snapshot(force=True):
            # Private maps cannot use a public world replay. A client may ask
            # for their scene after the bounded startup retries have expired.
            self.sync_static_world(force=True)
        self.runtime.record(
            event="transport_objects_initialized",
            actor_id=self.state.character["id"],
            map_id=self.state.character["map_id"],
        )
        return DispatchResult.FALLTHROUGH
