"""Trusted replay of observed server providers, without Store or client writes.

Sources are inputs; serialized outputs are independently recomputed by the real
native serializers and compared to the observed bytes. This module never uses
recorded packets as a substitute for running an effect or a serializer.
"""
import random

from .combat_input_observation import (
    InputReplayMismatch,
    replay_prepare_rng_argument,
    suspend_input_replay,
)


RECIPE = "observed-live-server-v1"
SUPPORTED_ACTIONS = {
    "player_spell",
    "player_weapon",
    "player_unarmed",
    "move",
    "end_turn",
    "end_server_turn",
    "ack",
}
_READY = "CombatSessionAdapter.ready_transition.<locals>."


class LiveProviderReplayError(InputReplayMismatch):
    """Missing or divergent actual provider evidence, never a game rejection."""


class LiveReplayContext:
    def __init__(self, runtime, action, inputs, clock, observations):
        if type(inputs) is not dict or inputs.get("authority_recipe", RECIPE) != RECIPE:
            raise LiveProviderReplayError("Unsupported observed live authority recipe")
        if action is not None and (
            type(action) is not dict or action.get("type") not in SUPPORTED_ACTIONS
        ):
            raise LiveProviderReplayError("Unsupported observed live action")
        if (
            type(observations) is not dict
            or observations.get("schema") != "wakemu-combat-observed-inputs-v1"
            or observations.get("incomplete") != []
        ):
            raise LiveProviderReplayError("Incomplete observed provider inputs")
        rows = observations.get("events")
        if type(rows) is not list or any(
            type(row) is not dict
            or type(row.get("label")) is not str
            or type(row.get("kind")) is not str
            for row in rows
        ):
            raise LiveProviderReplayError("Malformed observed provider inputs")
        self.inputs = inputs
        self.events = [row for row in rows if row.get("kind") in ("authority", "fact")]
        self.index = 0
        self.runtime = runtime
        self.clock = clock
        self.identities = inputs.get("live_provider_identity")
        if type(self.identities) is not dict:
            raise LiveProviderReplayError("Explicit live provider identities required")
        self._validate_providers()
        self._bind(runtime)

    def _validate_providers(self):
        ready_names = {
            "stats_serializer": "stats_serializer",
            "runtime_stats_serializer": "stats_serializer",
            "turn_start_provider": "turn_start",
            "turn_end_provider": "turn_end",
            "expiration_runtime_factory": "expiration_factory",
        }
        local_names = {
            "stats_serializer": {"session.<locals>.current_combat_stats"},
            "runtime_stats_serializer": {"session.<locals>.current_combat_stats"},
            "turn_start_provider": {"session.<locals>.area_boundary_provider"},
            "turn_end_provider": {"session.<locals>.apply_readiness.<locals>.<lambda>"},
            "expiration_runtime_factory": {
                "session.<locals>.apply_readiness.<locals>.<lambda>"
            },
        }
        for field, identity in self.identities.items():
            if field == "clock":
                continue  # The separate strict input tape owns every clock read.
            if field not in ready_names or type(identity) is not dict:
                raise LiveProviderReplayError("Unknown live provider identity")
            module, name = identity.get("module"), identity.get("qualname")
            ready = (
                module == "wakfu_server.combat_session_adapter"
                and name == _READY + ready_names[field]
            )
            local = (
                module in ("__main__", "local_game_server")
                and name in local_names[field]
            )
            if not ready and not local:
                raise LiveProviderReplayError("Unqualified live provider: " + field)

    def _peek(self, label=None):
        if self.index >= len(self.events):
            if label is None:
                return None
            raise LiveProviderReplayError("Missing observed provider input: " + label)
        row = self.events[self.index]
        if label is not None and row.get("label") != label:
            raise LiveProviderReplayError(
                "Observed provider input order differs: " + label
            )
        return row

    def _take(self, label):
        row = self._peek(label)
        kind = (
            "authority"
            if label in {"combat.player_sources", "server_runtime.authority"}
            else "fact"
        )
        if row.get("kind") != kind:
            raise LiveProviderReplayError("Observed provider input kind differs")
        if "value" not in row:
            raise LiveProviderReplayError("Observed provider input has no value")
        self.index += 1
        return row["value"]

    def _sources(self):
        value = self._take("combat.player_sources")
        if (
            type(value) is not tuple
            or len(value) != 2
            or any(type(part) is not dict for part in value)
            or set(value[0]) != set(value[1])
        ):
            raise LiveProviderReplayError("Malformed observed player source read")
        return value

    def _authority(self, action_id, *, critical=None, default=True):
        if (
            self._peek() is not None
            and self._peek()["label"] == "combat.player_sources"
        ):
            characters, decks = self._sources()
        else:
            characters = decks = None
        source = self._take("server_runtime.authority")
        required = {
            "character",
            "monsters",
            "deck_blob",
            "player_characters",
            "deck_blobs",
            "action_id",
            "critical",
            "compiled_is_default",
        }
        if (
            type(source) is not dict
            or set(source) != required
            or source["action_id"] != action_id
            or type(source["compiled_is_default"]) is not bool
            or source["compiled_is_default"] != default
        ):
            raise LiveProviderReplayError(
                "Unknown or divergent server runtime authority"
            )
        if critical is not None and source["critical"] is not critical:
            raise LiveProviderReplayError("Observed factory critical branch differs")
        if characters is not None and (
            characters != source["player_characters"] or decks != source["deck_blobs"]
        ):
            raise LiveProviderReplayError(
                "Provider factory differs from actual player source read"
            )
        return source

    @staticmethod
    def _kwargs(source):
        return {
            "player_characters": source["player_characters"],
            "deck_blobs": source["deck_blobs"],
            "rng": replay_prepare_rng_argument("server_runtime", None),
        }

    def _factory(self, *, action_id):
        from .combat_server_spell import server_runtime

        source = self._authority(action_id, critical=False)
        return server_runtime(
            source["character"],
            source["monsters"],
            source["deck_blob"],
            action_id=action_id,
            critical=False,
            **self._kwargs(source)
        )[0]

    def _turn_start(self, fight, **boundary):
        from .combat_server_spell import prepare_server_turn_start

        if any(
            type(self.inputs.get(flag)) is not bool
            for flag in ("native_events", "area_callbacks")
        ):
            raise LiveProviderReplayError("Missing observed turn-start policy")
        source = self._authority(boundary["action_id"], critical=False)
        return prepare_server_turn_start(
            source["character"],
            source["monsters"],
            fight,
            source["deck_blob"],
            native_events=self.inputs["native_events"],
            area_callbacks=self.inputs["area_callbacks"],
            **self._kwargs(source),
            **boundary
        )

    def _turn_end(self, fight, **boundary):
        from .combat_server_spell import prepare_server_turn_end

        source = self._authority(boundary["action_id"], critical=False)
        return prepare_server_turn_end(
            source["character"],
            source["monsters"],
            fight,
            source["deck_blob"],
            **self._kwargs(source),
            **boundary
        )

    def movement(self, fight, **boundary):
        from .combat_area_transaction import prepare_area_movement

        source = self._authority(boundary["action_id"], critical=False)
        return prepare_area_movement(
            source["character"],
            source["monsters"],
            fight,
            source["deck_blob"],
            **self._kwargs(source),
            **boundary
        )

    def _serialize(self, actor, fight, *, ready):
        from .combat_actor import actual_actor_stats, actual_monster_actor_stats
        from .combat_summon_stats import registered_summon_stats

        prefix = "ready_stats_serializer" if ready else "current_combat_stats"
        if actor.id in getattr(fight, "native_summon_registrations", {}):
            if ready:
                context = self._take(prefix + ".summon_context")
                if (
                    type(context) is not dict
                    or context.get("actor_id") != actor.id
                    or type(context.get("map_id")) is not int
                ):
                    raise LiveProviderReplayError(
                        "Observed summon serializer context differs"
                    )
                map_id = context["map_id"]
            else:
                if (
                    self._take(prefix + ".summon_actor") != actor.id
                    or type(self.inputs.get("map_id")) is not int
                ):
                    raise LiveProviderReplayError(
                        "Missing actual summon serializer map"
                    )
                map_id = self.inputs["map_id"]
            stats = registered_summon_stats(actor, fight, map_id)
            kind = "summon"
        else:
            if getattr(actor, "native_summon_source", None) is not None:
                raise ValueError("Summon stats require current native registration")
            if (
                not isinstance(actor.effect_stats, dict)
                or not isinstance(actor.effect_maxima, dict)
                or 4 not in actor.effect_stats
                or 4 not in actor.effect_maxima
            ):
                raise ValueError("Missing authoritative combat WP snapshot")
            kind = "player" if actor.controlled else "monster"
            source = self._take(prefix + "." + kind + "_source")
            if type(source) is not dict or source.get("id") != actor.id:
                raise LiveProviderReplayError(
                    "Observed actor serializer identity differs"
                )
            kwargs = dict(
                wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
            )
            if ready:
                kwargs["fight"] = fight
            if actor.controlled:
                stats = actual_actor_stats(source, actor, fight.id, **kwargs)
            else:
                if not ready:
                    kwargs["direction"] = 3
                stats = actual_monster_actor_stats(source, actor, fight.id, **kwargs)
        expected = self._take(prefix + "." + kind)
        if type(expected) is not bytes or stats != expected:
            raise LiveProviderReplayError("Recomputed native actor snapshot differs")
        return stats

    def serialize_current(self, actor, fight=None):
        return self._serialize(
            actor, self.runtime.fight if fight is None else fight, ready=False
        )

    def serialize_runtime(self, actor, fight=None):
        identity = self.identities.get(
            "runtime_stats_serializer", self.identities.get("stats_serializer")
        )
        if identity is None:
            raise LiveProviderReplayError("Missing actual runtime serializer identity")
        ready = identity["qualname"] == _READY + "stats_serializer"
        return self._serialize(
            actor, self.runtime.fight if fight is None else fight, ready=ready
        )

    def _bind(self, runtime, *, initial=True):
        self.runtime = runtime
        runtime.clock = self.clock
        runtime.runtime_stats_serializer = (
            self.serialize_runtime
            if "runtime_stats_serializer" in self.identities
            else None
        )
        runtime.stats_serializer = (
            self.serialize_runtime if "stats_serializer" in self.identities else None
        )
        runtime.turn_start_provider = (
            self._turn_start if "turn_start_provider" in self.identities else None
        )
        runtime.turn_end_provider = (
            self._turn_end if "turn_end_provider" in self.identities else None
        )
        runtime.expiration_runtime_factory = (
            self._factory if "expiration_runtime_factory" in self.identities else None
        )
        # No source is invented for ACK-only replays. Bind the omitted movement
        # service only when authoritative snapshots were actually captured.
        if not initial:
            return
        source = next(
            (
                row["value"]
                for row in self.events
                if row["label"] == "server_runtime.authority"
            ),
            None,
        )
        if source is None and all(
            key in self.inputs
            for key in (
                "character",
                "monsters",
                "deck_blob",
                "player_characters",
                "deck_blobs",
            )
        ):
            source = self.inputs
        if source is not None:
            from .combat_server_spell import server_runtime

            with suspend_input_replay():
                factory, _ = server_runtime(
                    source["character"],
                    source["monsters"],
                    source["deck_blob"],
                    action_id=runtime.action_id + 1,
                    critical=False,
                    rng=random.Random(0),
                    player_characters=source["player_characters"],
                    deck_blobs=source["deck_blobs"],
                )
            runtime.fight.native_rail_movement_authority = (
                factory.native_rail_movement_authority
            )

    def rebind_copy(self, runtime):
        """Bind a Registry-owned runtime copy without consuming any input seam."""
        self._bind(runtime, initial=False)
        return runtime

    def execute(self, runtime, action):
        if type(action) is not dict or action.get("type") not in SUPPORTED_ACTIONS:
            raise LiveProviderReplayError("Invalid live replay operation")
        self.rebind_copy(runtime)
        kind = action["type"]
        start = runtime.fight.sequence
        transaction = None
        if kind in {"player_spell", "player_weapon", "player_unarmed", "move"}:
            characters, decks = self._sources()
            if characters != self.inputs.get(
                "player_characters"
            ) or decks != self.inputs.get("deck_blobs"):
                raise LiveProviderReplayError(
                    "Initial operation authority differs from actual source read"
                )
        if kind == "player_unarmed":
            from .combat_reproduction_actions import (
                unarmed_entry_resources,
                prepare_reproduced_unarmed,
            )
            from .combat_spell_commit import commit_spell_transaction
            from .combat_death import death_messages

            if action.get("critical") is not False:
                raise LiveProviderReplayError("Unarmed live policy must be normal")
            wp = unarmed_entry_resources(
                action["body"], self.inputs["character"], runtime.fight
            )
            effect_uid = self._take("shared_weapon.unarmed_effect_uid")
            next_source = self._peek()
            if (
                next_source is not None
                and next_source["label"] == "server_runtime.authority"
            ):
                source = self._authority(
                    runtime.action_id + 1, critical=False, default=False
                )
                for field in (
                    "character",
                    "monsters",
                    "deck_blob",
                    "player_characters",
                    "deck_blobs",
                ):
                    if source[field] != self.inputs.get(field):
                        raise LiveProviderReplayError("Unarmed factory source differs")
            transaction = prepare_reproduced_unarmed(
                action["body"],
                self.inputs["character"],
                self.inputs["monsters"],
                runtime.fight,
                action["owner_id"],
                action_id=runtime.action_id + 1,
                effect_uid=effect_uid,
                wp=wp,
                player_characters=self.inputs["player_characters"],
                deck_blobs=self.inputs["deck_blobs"],
            )
            packets = list(
                commit_spell_transaction(
                    runtime, transaction, stats_serializer=self.serialize_current
                )
            )
            for event in transaction.events:
                if event["kind"] == "death":
                    packets.extend(
                        runtime.prepare_delivery(
                            death_messages(runtime, event["actor_id"])
                        )
                    )
        elif kind in {"player_spell", "player_weapon"}:
            from .combat_server_spell import prepare_server_spell
            from .combat_weapon import prepare_server_weapon
            from .combat_spell_commit import commit_spell_transaction
            from .combat_los import authoritative_visible
            from .combat_death import death_messages

            next_source = self._peek()
            if (
                next_source is not None
                and next_source["label"] == "server_runtime.authority"
            ):
                source = self._authority(
                    runtime.action_id + 1, default=kind == "player_spell"
                )
                for field in (
                    "character",
                    "monsters",
                    "deck_blob",
                    "player_characters",
                    "deck_blobs",
                ):
                    if source[field] != self.inputs.get(field):
                        raise LiveProviderReplayError(
                            "Main action factory source differs"
                        )
            prepare = (
                prepare_server_spell
                if kind == "player_spell"
                else prepare_server_weapon
            )
            label = (
                "player_spell.before_critical"
                if kind == "player_spell"
                else "player_weapon.before_critical"
            )
            transaction = prepare(
                action["body"],
                self.inputs["character"],
                self.inputs["monsters"],
                runtime.fight,
                action["owner_id"],
                self.inputs["deck_blob"],
                action_id=runtime.action_id + 1,
                critical=action["critical"],
                rng=replay_prepare_rng_argument(label, None),
                player_characters=self.inputs["player_characters"],
                deck_blobs=self.inputs["deck_blobs"],
                line_of_sight=lambda origin, target, state: authoritative_visible(
                    self.inputs["map_id"],
                    origin,
                    target,
                    state,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in state.actors.values()
                        if actor.hp > 0
                    },
                ),
            )
            packets = list(
                commit_spell_transaction(
                    runtime, transaction, stats_serializer=self.serialize_current
                )
            )
            for event in transaction.events:
                if event["kind"] == "death":
                    packets.extend(
                        runtime.prepare_delivery(
                            death_messages(runtime, event["actor_id"])
                        )
                    )
        elif kind == "move":
            from .combat_movement_runtime import apply_client

            packets, _ = apply_client(
                runtime,
                action["owner_id"],
                action["body"],
                self.serialize_current,
                runtime_stats_serializer=self.serialize_current,
                area_provider=self.movement
                if self.inputs.get("area_callbacks") is True
                else None,
            )
            packets = runtime.prepare_delivery(packets)
        elif kind == "end_turn":
            packets = runtime.end_turn(
                action["owner_id"], action["actor_id"], action["turn_id"]
            )
        elif kind == "end_server_turn":
            packets = runtime.end_server_turn(action["actor_id"], action["turn_id"])
        else:
            packets = runtime.acknowledge_turn(action["body"])
        return dict(
            state=runtime.fight,
            packets=tuple(packets),
            events=tuple(
                event for event in runtime.fight.events if event["sequence"] > start
            ),
            plan=None if transaction is None else transaction.plan,
            outcomes=() if transaction is None else transaction.outcomes,
        )

    def assert_complete(self):
        if self.index != len(self.events):
            raise LiveProviderReplayError(
                "Execution left observed provider inputs unused"
            )


def prepare_live_context(runtime, action, inputs, clock, observations):
    """Bind only trusted observed providers; execute inside the strict input tape."""
    return LiveReplayContext(runtime, action, inputs, clock, observations)
