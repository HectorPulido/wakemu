"""Generic world-native query SDK; all code lives with ai-service.

It contains transaction orchestration, not spell formulas or AI policy. Native
handlers, ownership, targeting, timers and packet codecs remain authoritative.
The stable world shim supplies the encounter and complete authority maps once.
"""
from ..native.native_control import (
    effective_server_controlled,
    effective_affiliation,
    effective_input_owner,
)
from copy import deepcopy
import hashlib
import inspect
import json
import random
import struct
from wakfu_server.combat_input_observation import observe_rng

from ..context.native_context import encode, encode_bytes
from .native_stats import NativeStats
from .native_actor_source import registered_source
from .native_deadline import check
from ..context.native_fingerprint import fingerprint as complete_fingerprint
from ..planning.feature_values import validate_features


class NativeOracle:
    def __init__(
        self,
        runtime,
        *,
        characters,
        monsters,
        decks,
        excluded_decks,
        viewer_id,
        flags,
        outcome_features=None
    ):
        self.runtime = runtime
        self.characters = deepcopy(characters)
        self.monsters = deepcopy(monsters)
        self.decks = deepcopy(decks)
        self.excluded_decks = deepcopy(excluded_decks)
        self.viewer_id = viewer_id
        self.flags = deepcopy(flags)
        if outcome_features is not None and not callable(outcome_features):
            raise ValueError("Native outcome feature provider must be callable")
        self.outcome_features_provider = outcome_features
        if set(self.characters) != set(self.decks) or set(self.characters) != set(
            self.excluded_decks
        ):
            raise ValueError("Missing complete character/deck authority")
        if viewer_id not in self.characters:
            raise ValueError("Missing native viewer authority")
        registrations = getattr(runtime.fight, "native_summon_registrations", {})
        ordinary = set(runtime.fight.actors) - set(registrations)
        if ordinary != set(self.characters) | set(self.monsters):
            raise ValueError("Incomplete encounter actor authority")
        for identity, actor in runtime.fight.actors.items():
            if identity in registrations:
                continue
            source = (
                self.characters.get(identity)
                if actor.controlled
                else self.monsters.get(identity)
            )
            if source is None or source.get("id") != identity:
                raise ValueError("Native actor kind/source mismatch")

    def authorities(self, runtime=None):
        authorities = dict(
            characters=self.characters,
            monsters=self.monsters,
            decks=self.decks,
            excludedDecks=self.excluded_decks,
            viewerId=self.viewer_id,
            registrations=getattr(
                (runtime or self.runtime).fight, "native_summon_registrations", {}
            ),
        )
        if self.outcome_features_provider is not None:
            provider = self.outcome_features_provider
            if inspect.isroutine(provider):
                # Routine descriptors are intentionally not executed or
                # introspected by NativeGraph. Include their bound owner and
                # data parameters explicitly so configured provider context is
                # part of the complete source identity as well.
                authority = {
                    "callable": provider,
                    "owner": getattr(provider, "__self__", None),
                    "defaults": getattr(provider, "__defaults__", None),
                    "kwdefaults": getattr(provider, "__kwdefaults__", None),
                }
                closure = getattr(provider, "__closure__", None)
                if closure:
                    try:
                        authority["closure"] = tuple(
                            cell.cell_contents for cell in closure
                        )
                    except ValueError as error:
                        raise ValueError(
                            "Outcome feature provider has an empty closure cell"
                        ) from error
                authorities["outcomeFeaturesProvider"] = authority
            else:
                authorities["outcomeFeaturesProvider"] = provider
        return authorities

    def outcome_features(self, runtime):
        """Measure an isolated full runtime and reject any provider mutation."""
        provider = self.outcome_features_provider
        actor = runtime.fight.current
        builtin = {}
        if actor is not None and actor.hp > 0 and not actor.controlled:
            from wakfu_server.combat_ai_state_progress import progress
            from wakfu_server.combat_native_spell_casting import catalog

            amount = progress(actor, self.owned_spells(runtime.fight), catalog())
            if amount:
                builtin["owned_state_progress"] = amount
        if provider is None:
            return builtin or None
        check()
        live_source = complete_fingerprint(runtime)
        private = deepcopy(runtime)
        private_source = complete_fingerprint(private)
        try:
            measurements = provider(private)
        except BaseException:
            if complete_fingerprint(runtime) != live_source:
                raise ValueError(
                    "Native source changed while measuring outcome features"
                )
            if complete_fingerprint(private) != private_source:
                raise ValueError(
                    "Outcome feature provider mutated its runtime snapshot"
                )
            check()
            raise
        if complete_fingerprint(private) != private_source:
            raise ValueError("Outcome feature provider mutated its runtime snapshot")
        if complete_fingerprint(runtime) != live_source:
            raise ValueError("Native source changed while measuring outcome features")
        checked = validate_features(measurements, "native outcome features", 1e9)
        if "owned_state_progress" in checked:
            raise ValueError("Custom provider overrides native owned-state progress")
        checked.update(builtin)
        check()
        return checked

    def unobserved_areas(self, runtime):
        """Hidden fbc traps are unknown to hostile observers, not immune."""
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_trap_area import verified_trap_characteristics

        observer = runtime.fight.current
        if observer is None:
            return frozenset()
        result = set()
        definitions = None
        for row in getattr(runtime.fight, "native_effect_areas", {}).values():
            if row.get("native_area_contract") != "fbc":
                continue
            if definitions is None:
                definitions = native_effect_areas()
            definition = definitions.get(str(row["reference"]))
            if definition is None:
                raise ValueError("Missing native observer trap prototype")
            verified_trap_characteristics(row, definition)
            owner = runtime.fight.actors.get(row["owner_id"])
            if row["native_trap_constructor"]["fqx"] and (
                owner is None
                or effective_affiliation(runtime.fight, owner)
                != effective_affiliation(runtime.fight, observer)
            ):
                result.add(row["uid"])
        return frozenset(result)

    def observation_properties(self, runtime):
        """Read current PB through the same profile/live authority as casting.

        Fresh ordinary fighters legitimately have no live override: their
        complete baseline is owned by OrdinaryActorAuthority's catalog.
        """
        _, adapter = self.factory(
            runtime.fight, runtime.action_id + 1, random.Random(0)
        )
        return {
            actor.id: adapter.actor_authority.properties(runtime.fight, actor)
            for actor in runtime.fight.actors.values()
            if actor.hp > 0
        }

    def factory(self, fight, action_id, rng, *, critical=False, compiled=None):
        from wakfu_server.spells import validate_deck
        from wakfu_server.combat_ordinary_authority import (
            OrdinaryActorAuthority,
            ordinary_cast_authority,
        )
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.spell_audit import states_catalog
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_relative_probability import RelativeGroupAuthority
        from wakfu_server.combat_random_group import RandomGroupAuthority

        registrations = getattr(fight, "native_summon_registrations", {})
        ordinary_ids = set(fight.actors) - set(registrations)
        chars = {i: c for i, c in self.characters.items() if i in ordinary_ids}
        monsters = {i: c for i, c in self.monsters.items() if i in ordinary_ids}
        selected = {
            i: validate_deck(self.decks[i], c["breed"], c["level"])
            for i, c in chars.items()
        }
        actors = RegisteredSummonAuthority(
            OrdinaryActorAuthority(
                characters=chars,
                monsters=monsters,
                decks={
                    i: frozenset(d["active"] + d["passive"])
                    for i, d in selected.items()
                },
                excluded_decks={i: frozenset(self.excluded_decks[i]) for i in chars},
                deck_blobs={i: self.decks[i] for i in chars},
                deck_caps={
                    i: d["level_cap"] if d["level_cap"] >= 0 else None
                    for i, d in selected.items()
                },
            )
        )
        states = states_catalog()
        cast = ordinary_cast_authority(
            actors=actors,
            timing=NativeEffectTimingProvider(states),
            rng=rng,
            critical=critical,
        )
        adapter = NativeServerRuntimeAdapter(
            actor_authority=actors, cast=cast, viewer_id=self.viewer_id
        )
        contexts = adapter.contexts()
        from .native_damage_observer import current, observe

        damage_observations = current()
        if damage_observations is not None:
            from dataclasses import replace

            contexts = replace(
                contexts, damage=observe(contexts.damage, damage_observations)
            )
        if compiled is None:
            compiled = npc_runtime_catalog(imported=False)
        factory = NativeEffectRuntimeFactory(
            effects=compiled.source_effects,
            state_catalog=states,
            characteristic_registry=characteristic_registry(),
            compiled_effects=compiled,
            action_id=action_id,
            contexts=contexts,
            displacement_authority=actors,
            summon_authority=actors,
        )
        factory.native_rail_movement_authority = actors
        factory.relative_group_children = RelativeGroupAuthority(
            effects=factory.effects,
            actor_authority=actors,
            condition_context=adapter.condition,
            draw_integer=lambda total: rng.randint(1, total),
            draw_fraction=lambda fraction: rng.random() < fraction,
        )
        factory.random_group_children = RandomGroupAuthority(
            effects=factory.effects,
            condition_context=adapter.condition,
            draw_integer=lambda total: rng.randrange(total),
        )
        return factory, adapter

    def fork(self, fight=None, *, runtime=None):
        private = deepcopy(runtime or self.runtime)
        if fight is not None:
            private.fight = deepcopy(fight)
        # Rebind pure callbacks to the complete encounter authority, rather
        # than calling closures belonging to the live socket's single viewer.
        private.turn_start_provider = (
            self.start_boundary if private.turn_start_provider is not None else None
        )
        private.turn_end_provider = (
            self.end_boundary if private.turn_end_provider is not None else None
        )
        private.stats_serializer = None
        return private

    def _rng(self, fight, action):
        actor = fight.current
        if (
            action.get("type") == "cast"
            and actor is not None
            and actor.id not in self.characters
        ):
            # Compare NPC alternatives with common forecast randomness. Costs,
            # facing and native buffs still affect execution, never the sample.
            # Native usage counters are optional (only tracked for enabled
            # limits); successful NPC cast events provide the universal ordinal.
            target = action.get("targetId")
            ordinal = sum(
                event.get("kind") == "npc_cast"
                and event.get("turn_id") == fight.turn_id
                and event.get("actor_id") == actor.id
                and event.get("spell_id") == action.get("spellId")
                and event.get("target_id") == target
                for event in fight.events
            )
            seed = dict(
                schema="npc-cast-common-randomness-v1",
                fight=fight.id,
                turn=fight.turn_id,
                caster=actor.id,
                caster_turn=actor.turn_count,
                spell=action.get("spellId"),
                level=action.get("level"),
                target=target,
                ordinal=ordinal,
            )
            if target is None:
                seed["cell"] = action.get("target")
        else:
            from wakfu_server.combat_tactical_ai import state_key

            seed = dict(state=state_key(fight), action=action)
        encoded = json.dumps(
            seed,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        return random.Random(int(hashlib.sha256(encoded).hexdigest(), 16))

    def start_boundary(self, fight, *, actor_id, action_id, forecast=True):
        from wakfu_server.combat_turn_events import deliver_turn_start

        private = deepcopy(fight)
        rng = (
            self._rng(private, dict(boundary="start", actorId=actor_id))
            if forecast
            else observe_rng(
                "native_oracle.start_boundary", random.Random(), external=False
            )
        )
        factory, _ = self.factory(private, action_id, rng)
        dispatcher, packets = factory(
            private, {"native_retained_container": {"present": False}}
        )
        with private.effect_resolution():
            if self.flags.get("native_start_events", True):
                deliver_turn_start(dispatcher, actor_id=actor_id)
            if (
                self.flags.get("native_area_callbacks", False)
                and private.phase == "active"
            ):
                dispatcher.native_area_events.turn_start(actor_id)
        return private, tuple(packets)

    def end_boundary(self, fight, *, actor_id, action_id, forecast=True):
        from wakfu_server.combat_turn_events import deliver_turn_end

        private = deepcopy(fight)
        rng = (
            self._rng(private, dict(boundary="end", actorId=actor_id))
            if forecast
            else observe_rng(
                "native_oracle.end_boundary", random.Random(), external=False
            )
        )
        factory, _ = self.factory(private, action_id, rng)
        dispatcher, packets = factory(
            private, {"native_retained_container": {"present": False}}
        )
        with private.effect_resolution():
            deliver_turn_end(dispatcher, actor_id=actor_id)
        return private, tuple(packets)

    def live_start_boundary(self, fight, **boundary):
        return self.start_boundary(fight, forecast=False, **boundary)

    def live_end_boundary(self, fight, **boundary):
        return self.end_boundary(fight, forecast=False, **boundary)

    def owned_spells(self, fight, actor_id=None):
        from wakfu_server.spells import validate_deck
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.monsters import native_abilities

        actor = fight.current if actor_id is None else fight.actors.get(actor_id)
        if actor is None or actor.hp <= 0:
            raise ValueError("Missing active native caster")
        if actor.id in self.characters:
            from wakfu_server.combat_class_ai_spell import canonical_class_actions

            actions = canonical_class_actions(
                fight, actor, self.characters[actor.id], self.decks[actor.id]
            )
            return {spell: entry["level"] for spell, entry in actions.items()}
        elif actor.id in self.monsters or actor.id in getattr(
            fight, "native_summon_registrations", {}
        ):
            result = {
                row["spell_id"]: row["spell_level"]
                for row in native_abilities(
                    self.descriptor(fight, actor)["ref"], actor.effective_level
                )
            }
        else:
            raise ValueError("Missing native spell ownership source")
        grants = granted_spells(fight, actor.id)
        if actor.id not in self.characters and any(
            grant["uid"] != spell for spell, grant in grants.items()
        ):
            raise ValueError("Unsupported native NPC temporary spell UID")
        result.update({spell: grant["level"] for spell, grant in grants.items()})
        return result

    def native_target_envelope(self, fight, actor_id, *, action_id=None):
        """Return a current-state, fail-open range envelope for the repertoire."""
        check()
        actor = fight.actors.get(actor_id)
        if (
            actor is None
            or actor.hp <= 0
            or fight.current is None
            or fight.current.id != actor_id
        ):
            return None
        try:
            from wakfu_server.combat_native_spell_casting import (
                catalog as native_casting_catalog,
                definition as native_casting_definition,
            )
            from wakfu_server.combat_casting_context import casting_root_catalog
            from wakfu_server.combat_casting_range import resolve_range
            from .native_target_mask import derive_native_target_envelope

            roots = casting_root_catalog()
            overrides = roots.get("normal_casting_overrides")
            area_types = (
                overrides.get("area_types") if isinstance(overrides, dict) else None
            )
            if (
                not isinstance(overrides, dict)
                or set(overrides) != {"categories", "area_types"}
                or not isinstance(overrides.get("categories"), dict)
                or set(overrides["categories"]) != {"txX", "txZ", "tya", "tyb"}
                or any(
                    type(value) is not int for value in overrides["categories"].values()
                )
                or len(set(overrides["categories"].values())) != 4
                or not isinstance(area_types, dict)
                or set(area_types) != {"rNX", "rNI"}
                or any(type(value) is not int for value in area_types.values())
                or len(set(area_types.values())) != 2
            ):
                return None
            override_categories = {
                overrides["categories"][key] for key in ("txX", "txZ", "tyb")
            }
            owned = self.owned_spells(fight, actor_id)
            # One complete authority/adapter per actor state; only the native
            # condition context and exact table selection vary per ability.
            check()
            factory, adapter = self.factory(
                fight,
                (
                    getattr(self.runtime, "action_id", 0)
                    if action_id is None
                    else action_id
                )
                + 1,
                random.Random(0),
            )
            del factory
            check()

            def select(spell, level):
                request = dict(
                    actor_id=actor_id,
                    spell_uid=spell,
                    target=tuple(actor.position),
                )
                context = adapter.cast_condition(fight, request)
                selected = native_casting_definition(
                    spell,
                    level,
                    context,
                    actor.spell_ap_cost_modifiers,
                    calculate_costs=False,
                )
                return selected, context

            def range_for(spell, level, rule, context):
                # `resolve_range` reads the actual caster RANGE, carried state,
                # fight property 2 and category modifiers from this live state.
                return resolve_range(rule, actor, context)

            position = tuple(actor.position)
            return derive_native_target_envelope(
                actor_id=actor_id,
                origin=position,
                owned_spells=owned,
                casting_catalog=native_casting_catalog(),
                override_categories=override_categories,
                resolve_current=select,
                resolve_range=range_for,
            )
        except TimeoutError:
            raise
        except Exception:
            # The repertoire itself remains available. Any missing or newer
            # native authority simply disables this optional advisory mask.
            return None

    def native_casting_root_prerequisites(
        self, fight, actor_id, source_state, *, owned_spells=None
    ):
        """Certify NPC spells blocked by absent authoritative casting roots.

        The NPC cast path selects roots from the positive-level baseline row,
        independent of target cell and conditional range selection. A missing
        root record therefore rejects every target for that spell. Unknown
        schemas and level-zero records are omitted so the planner fails open.
        """
        check()
        actor = fight.actors.get(actor_id)
        registrations = getattr(fight, "native_summon_registrations", {})
        if (
            actor is None
            or actor.hp <= 0
            or actor_id in self.characters
            or (actor_id not in self.monsters and actor_id not in registrations)
            or type(source_state) is not str
            or type(fight.sequence) is not int
        ):
            return None
        try:
            from wakfu_server.combat_native_spell_casting import catalog
            from wakfu_server.combat_casting_context import casting_root_catalog

            owned = (
                self.owned_spells(fight, actor_id)
                if owned_spells is None
                else owned_spells
            )
            if not isinstance(owned, dict):
                return None
            casting = catalog()
            root_catalog = casting_root_catalog()
            root_records = root_catalog.get("roots")
            if not isinstance(casting, dict) or not isinstance(root_records, dict):
                return None
            unavailable = []
            for spell_id, level in sorted(owned.items()):
                check()
                if type(spell_id) is not int or type(level) is not int or level <= 0:
                    continue
                record = casting.get(str(spell_id))
                if record is None:
                    unavailable.append(
                        dict(
                            spellId=spell_id,
                            level=level,
                            reason="missing_casting_table",
                            missingRootIds=[],
                        )
                    )
                    continue
                levels = record.get("levels") if isinstance(record, dict) else None
                index = level - 1
                if not isinstance(levels, list) or index < 0 or index >= len(levels):
                    continue
                baseline = levels[index]
                if (
                    not isinstance(baseline, list)
                    or len(baseline) != 3
                    or not isinstance(baseline[2], list)
                    or any(type(root) is not int for root in baseline[2])
                ):
                    continue
                missing = [
                    root
                    for root in baseline[2]
                    if not isinstance(root_records.get(str(root)), dict)
                    or "native_casting_collision_area" not in root_records[str(root)]
                ]
                if missing:
                    unavailable.append(
                        dict(
                            spellId=spell_id,
                            level=level,
                            reason="missing_root_metadata",
                            missingRootIds=sorted(set(missing)),
                        )
                    )
            check()
            return dict(
                schema="native-casting-root-prerequisites-v1",
                sourceState=source_state,
                actorId=actor_id,
                stateRevision=fight.sequence,
                complete=True,
                unavailable=unavailable,
            )
        except TimeoutError:
            raise
        except Exception:
            # A newer/unknown catalog shape is not evidence of unavailability.
            return None

    def descriptor(self, fight, actor):
        registrations = getattr(fight, "native_summon_registrations", {})
        if actor.id in registrations:
            return registered_source(actor, registrations[actor.id])
        source = (
            self.characters.get(actor.id)
            if actor.id in self.characters
            else self.monsters.get(actor.id)
        )
        if source is None or source.get("id") != actor.id:
            raise ValueError("Missing native actor source")
        return source

    def visible(self, fight, source, target):
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint

        actor = fight.current
        descriptor = self.descriptor(fight, actor)
        map_id = descriptor.get("map_id")
        if map_id is None:
            raise ValueError("Missing native encounter map authority")
        return authoritative_visible(
            map_id,
            source,
            target,
            fight,
            blocking_footprints={
                a.id: footprint(a.position, a.physical_radius)
                for a in fight.actors.values()
                if a.hp > 0
            },
        )

    def coordination_for_action(self, action):
        """Draft only; the publication owner confirms it after native delivery."""
        if action.get("type") != "cast":
            return None
        from wakfu_server.combat_native_spell_casting import definition

        from ..planning.corridor_reservations import draft

        fight, actor = self.runtime.fight, self.runtime.fight.current
        # The turn driver owns NPC casts. Their conditional casting authority
        # is exactly the one used by cast(), including current modifiers.
        if actor.id in self.characters:
            return None
        _, adapter = self.factory(
            fight, self.runtime.action_id + 1, self._rng(fight, action)
        )
        context = adapter.cast_condition(
            fight,
            dict(
                actor_id=actor.id,
                spell_uid=action["spellId"],
                target=tuple(action["target"]),
            ),
        )
        rule = definition(
            action["spellId"], action["level"], context, actor.spell_ap_cost_modifiers
        )
        if not rule["line_of_sight"]:
            return None
        record = draft(fight, actor, action, self.descriptor(fight, actor)["map_id"])
        if record is not None:
            record.update(
                instanceId=self.runtime.tactical_encounter_id,
                sourceRevision=fight.sequence,
            )
        return record

    def cast(self, runtime, action, *, forecast=True):
        from wakfu_server.combat_spell_transaction import prepare_spell_transaction
        from wakfu_server.combat_cast import _validate_target
        from wakfu_server.combat_native_spell_casting import definition
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_npc_spell import prepare_validated_npc_spell
        from wakfu_server.combat_npc_attack import (
            npc_runtime_catalog,
            npc_spell_catalog,
        )
        from wakfu_server.combat_npc_activation import imports_enabled

        fight, actor = runtime.fight, runtime.fight.current
        if fight.phase != "active" or actor is None or actor.hp <= 0:
            raise ValueError("Missing active native caster")
        if (
            not isinstance(action, dict)
            or action.get("type") != "cast"
            or set(action) - {"type", "spellId", "level", "targetId", "target"}
        ):
            raise ValueError("Invalid native oracle cast")
        spells = self.owned_spells(fight)
        spell, level, target = (
            action.get("spellId"),
            action.get("level"),
            action.get("target"),
        )
        if (
            type(spell) is not int
            or spell not in spells
            or type(level) is not int
            or level != spells[spell]
            or not isinstance(target, list)
            or len(target) != 3
            or any(type(c) is not int for c in target)
        ):
            raise ValueError("Native caster does not own requested spell/level/target")
        rng = (
            self._rng(fight, action)
            if forecast
            else observe_rng("native_oracle.cast", random.Random(), external=False)
        )
        compiled = None
        if actor.id not in self.characters:
            descriptor = self.descriptor(fight, actor)
            policy = npc_spell_catalog().get("activation_policy")
            imported = imports_enabled(
                policy, descriptor["ref"], actor.effective_level, spell
            )
            if not imported and actor.id in getattr(
                fight, "native_summon_registrations", {}
            ):
                from .native_summon_dependencies import registered_dependency_enabled

                imported = registered_dependency_enabled(
                    fight, actor, self.monsters, policy, spell, level
                )
            compiled = npc_runtime_catalog(imported=imported)
        factory, adapter = self.factory(
            fight, runtime.action_id + 1, rng, compiled=compiled
        )
        if actor.id in self.characters:
            char = self.characters[actor.id]
            from wakfu_server.combat_class_ai_spell import (
                canonical_class_actions,
                prepare_class_ai_plan,
            )
            from wakfu_server.combat_spell_transaction import _prepare_spell_transaction

            entry = canonical_class_actions(fight, actor, char, self.decks[actor.id])[
                spell
            ]
            uid = entry["uid"]
            server_ai = effective_server_controlled(fight, actor)
            prepare = (
                _prepare_spell_transaction if server_ai else prepare_spell_transaction
            )
            tx = prepare(
                struct.pack(">qqiih", actor.id, uid, *target),
                char,
                fight,
                effective_input_owner(fight, actor),
                self.decks[actor.id],
                wp_current=actor.effect_stats[4],
                action_id=runtime.action_id + 1,
                line_of_sight=lambda a, b, state: self.visible(state, a, b),
                runtime_factory=factory,
                conditional_context=lambda request, state: adapter.cast_condition(
                    state, request
                ),
                critical=False,
                **({"plan_builder": prepare_class_ai_plan} if server_ai else {}),
            )
            if action.get("targetId") != tx.plan["target_id"]:
                raise ValueError(
                    "Native cast target identity differs from requested cell"
                )
            return tx
        request = dict(actor_id=actor.id, spell_uid=spell, target=tuple(target))
        from wakfu_server.combat_npc_area_preflight import npc_cast_condition

        context = npc_cast_condition(
            adapter,
            fight,
            request,
            factory=factory,
            enabled=imported,
        )
        rule = definition(spell, level, context, actor.spell_ap_cost_modifiers)
        plan = _validate_target(
            request,
            actor,
            fight,
            actor.effect_stats[4],
            rule["costs"],
            rule,
            rule["roots"],
            level,
            lambda a, b, state: self.visible(state, a, b),
            spell,
            context,
        )
        if action.get("targetId") != plan["target_id"]:
            raise ValueError(
                "Native NPC cast target identity differs from requested cell"
            )
        return prepare_validated_npc_spell(
            fight,
            plan,
            rule,
            descriptor,
            factory=factory,
            action_id=runtime.action_id + 1,
        )

    def preview_with_evidence(self, runtime, action):
        from .native_damage_observer import capture

        with capture() as samples:
            private, packets, transaction = self.preview(runtime, action)
        return private, packets, transaction, samples

    def preview(self, runtime, action, *, forecast=True):
        check()
        from wakfu_server.combat_cast_facing import DIRECTIONS
        from wakfu_server.combat_movement import movement

        if runtime.awaiting_ack is not None or runtime.pending:
            raise ValueError("Native preview source has pending presentation")
        private = self.fork(runtime=runtime)
        if not isinstance(action, dict):
            raise ValueError("Invalid native oracle action")
        kind = action.get("type")
        if kind == "cast":
            tx = self.cast(private, action, forecast=forecast)
            private.fight = tx.fight
            private.action_id = tx.action_id
            return private, tx.packets, tx
        actor = private.fight.current
        if private.fight.phase != "active" or actor is None or actor.hp <= 0:
            raise ValueError("Missing active native actor")
        if kind == "move":
            if set(action) != {"type", "path"} or not isinstance(action["path"], list):
                raise ValueError("Invalid native movement action")
            path, origin = action["path"], actor.position
            if (
                not 1 <= len(path) <= actor.mp
                or private.fight.edges is None
                or any(
                    not isinstance(cell, list)
                    or len(cell) != 3
                    or any(type(v) is not int for v in cell)
                    for cell in path
                )
            ):
                raise ValueError(
                    "Native movement requires a complete directed XYZ route"
                )
            # A forecast can start from a reconstructed encounter whose pure
            # runtime providers are intentionally absent from checkpoints.
            # Bind the same complete owned actor authority as native casts.
            movement_rng = random.Random()
            if not forecast:
                movement_rng = observe_rng(
                    "native_oracle.movement", movement_rng, external=False
                )
            movement_factory, _ = self.factory(
                private.fight,
                private.action_id + 2,
                movement_rng,
            )
            private.fight.native_rail_movement_authority = (
                movement_factory.native_rail_movement_authority
            )
            callbacks = []
            step_callback = None
            # Player movement retains its established transaction path. NPC
            # previews and real commits share this stepwise resource delivery.
            if effective_server_controlled(private.fight, actor) and self.flags.get(
                "native_area_callbacks", False
            ):
                if forecast:
                    movement_rng.setstate(self._rng(private.fight, action).getstate())
                dispatcher, callbacks = movement_factory(
                    private.fight, {"native_retained_container": {"present": False}}
                )

                def step_callback(fight, moving_actor, before, cell):
                    moving_actor.direction = DIRECTIONS[
                        (cell[0] - before[0], cell[1] - before[1])
                    ]
                    from wakfu_server.combat_voluntary_movement_events import (
                        deliver_voluntary_movement,
                    )

                    deliver_voluntary_movement(
                        dispatcher,
                        actor_id=moving_actor.id,
                        from_cell=before,
                        to_cell=cell,
                        action_id=private.action_id + 1,
                    )
                    dispatcher.native_area_events.movement(
                        moving_actor.id, from_cell=before, to_cell=cell
                    )

            if not effective_server_controlled(private.fight, actor):
                event = private.fight.move(
                    effective_input_owner(private.fight, actor), actor.id, path
                )
            else:
                with private.fight.effect_resolution():
                    event = private.fight.server_move(
                        actor.id, path, step_callback=step_callback
                    )
            if not effective_server_controlled(private.fight, actor) and self.flags.get(
                "native_area_callbacks", False
            ):
                previous = origin if len(path) == 1 else path[-2]
                actor.direction = DIRECTIONS[
                    (path[-1][0] - previous[0], path[-1][1] - previous[1])
                ]
                # Preserve the established controlled-actor callback path.
                if forecast:
                    movement_rng.setstate(self._rng(private.fight, action).getstate())
                dispatcher, callbacks = movement_factory(
                    private.fight, {"native_retained_container": {"present": False}}
                )
                before = origin
                with private.fight.effect_resolution():
                    for cell in map(tuple, path):
                        from wakfu_server.combat_qi_fight import move_registered_actor

                        move_registered_actor(private.fight, actor, cell)
                        dispatcher.native_area_events.movement(
                            actor.id, from_cell=before, to_cell=cell
                        )
                        before = cell
                        if private.fight.phase != "active" or actor.hp <= 0:
                            break
                if actor.position != tuple(path[-1]):
                    raise ValueError(
                        "Native movement interrupted before requested destination"
                    )
            path = [tuple(cell) for cell in event["path"]]
            if not self.flags.get("native_area_callbacks", False):
                previous = origin if len(path) == 1 else path[-2]
                actor.direction = DIRECTIONS[
                    (path[-1][0] - previous[0], path[-1][1] - previous[1])
                ]
            private.action_id += 1
            packets = [
                movement(
                    private.fight.id,
                    private.action_id,
                    actor.id,
                    [origin, *path],
                    actor.direction,
                )
            ]
            if callbacks:
                private.action_id += 1
                packets.extend(callbacks)
            return private, tuple(packets), None
        if kind == "end_turn":
            if set(action) != {"type"}:
                raise ValueError("Invalid native end-turn action")
            packets = (
                private.end_turn(
                    effective_input_owner(private.fight, actor),
                    actor.id,
                    actor.turn_count,
                )
                if not effective_server_controlled(private.fight, actor)
                else private.end_server_turn(actor.id, private.fight.turn_id)
            )
            # These acknowledgments are confined to the forecast instance.
            if private.awaiting_ack is not None:
                packets += private.acknowledge_turn(
                    struct.pack(">i", private.awaiting_ack)
                )
            return private, tuple(packets), None
        raise ValueError("Unsupported native oracle action")

    def commit(self, action, *, stats_serializer):
        from wakfu_server.combat_npc_reproduction import npc_commit_scope

        with npc_commit_scope(self, action, stats_serializer) as capture:
            packets = self._commit(action, stats_serializer=stats_serializer)
            if capture is not None:
                capture.packets(packets)
            return packets

    def _commit(self, action, *, stats_serializer):
        """Stage all native packets before adopting the selected live action.

        This runs only on the encounter owner thread. End-turn ACKs remain
        real client barriers; private forecast ACKs never enter this path.
        """
        from wakfu_server.combat_area_boundary import adopt_runtime
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_wire import actor_state

        check()
        runtime = self.runtime
        if runtime.awaiting_ack is not None or runtime.pending:
            raise ValueError("Previous native action is not synchronized")
        if not callable(stats_serializer) or not isinstance(action, dict):
            raise ValueError("Missing native commit action or serializer")

        def fingerprint():
            return complete_fingerprint(
                dict(
                    runtime=runtime,
                    authorities=self.authorities(runtime),
                    flags=self.flags,
                )
            )

        source = fingerprint()
        candidate = deepcopy(runtime)
        candidate.turn_start_provider = (
            self.live_start_boundary
            if candidate.turn_start_provider is not None
            else None
        )
        candidate.turn_end_provider = (
            self.live_end_boundary if candidate.turn_end_provider is not None else None
        )
        if isinstance(stats_serializer, NativeStats):
            candidate.stats_serializer = stats_serializer.for_fight(candidate.fight)
        kind = action.get("type")
        if kind == "end_turn":
            if set(action) != {"type"} or candidate.fight.current is None:
                raise ValueError("Invalid native end-turn commit")
            actor = candidate.fight.current
            packets = (
                candidate.end_turn(
                    effective_input_owner(candidate.fight, actor),
                    actor.id,
                    actor.turn_count,
                )
                if not effective_server_controlled(candidate.fight, actor)
                else candidate.end_server_turn(actor.id, candidate.fight.turn_id)
            )
        elif kind == "cast":
            transaction = self.cast(candidate, action, forecast=False)
            packets = commit_spell_transaction(
                candidate, transaction, stats_serializer=stats_serializer
            )
        elif kind == "move":
            from wakfu_server.combat_movement_runtime import movement_stats_snapshot

            private, effects, _ = self.preview(runtime, action, forecast=False)
            packets = list(effects) + [candidate._flush()]
            from wakfu_server.combat_snapshot_actor_visibility import (
                hidden_snapshot_actor_ids,
            )

            hidden = hidden_snapshot_actor_ids(private.fight)
            for actor in private.fight.actors.values():
                if actor.id in hidden:
                    continue
                stats = stats_serializer(actor, private.fight)
                previous = runtime.fight.actors.get(actor.id)
                if previous is not None and (
                    actor.id == runtime.fight.current.id
                    or actor.position == previous.position
                ):
                    stats = movement_stats_snapshot(
                        stats,
                        stats_serializer(previous, runtime.fight),
                        position_owned=actor.id == runtime.fight.current.id,
                    )
                packets.append(
                    (
                        12873,
                        actor_state(
                            12873,
                            private.fight.id,
                            actor.id,
                            stats,
                        ),
                    )
                )
            packets.append(candidate._flush())
            candidate.fight, candidate.action_id = private.fight, private.action_id
            packets = candidate.prepare_delivery(packets)
        else:
            raise ValueError("Unsupported native commit action")
        # AI actions use the same death presentation boundary as player casts.
        # Damage/retirement alone releases geometry but leaves the client actor
        # visible. Stage these packets on the private candidate so a failure
        # cannot publish a partial action or mark a live death as delivered.
        from wakfu_server.combat_death import newly_registered_death_messages

        packets = list(packets)
        packets.extend(
            newly_registered_death_messages(
                candidate, after_sequence=runtime.fight.sequence
            )
        )
        if fingerprint() != source:
            raise ValueError("Native source changed while staging action delivery")
        check()
        adopt_runtime(runtime, candidate)
        return packets

    def complete_state(self, runtime):
        return encode(
            dict(
                runtime=runtime, authorities=self.authorities(runtime), flags=self.flags
            )
        )

    def state_identity(self, runtime):
        return complete_fingerprint(
            dict(
                runtime=runtime, authorities=self.authorities(runtime), flags=self.flags
            )
        )

    def complete_transition_state(self, runtime, transition):
        # Transaction.fight and runtime.fight share one graph node. Preserve
        # every transaction field, packet and future extension without a
        # second terrain copy or a projection of selected effect outcomes.
        return encode(
            dict(
                runtime=runtime,
                authorities=self.authorities(runtime),
                flags=self.flags,
                transition=transition,
            )
        )

    def complete_transition_bytes(self, runtime, transition):
        return encode_bytes(
            dict(
                runtime=runtime,
                authorities=self.authorities(runtime),
                flags=self.flags,
                transition=transition,
            )
        )

    def complete_state_bytes(self, runtime):
        return encode_bytes(
            dict(
                runtime=runtime, authorities=self.authorities(runtime), flags=self.flags
            )
        )

    def complete_state_parts(self, runtime, transition=None):
        from ..context.native_graph_parts import encode_parts

        value = dict(
            runtime=runtime, authorities=self.authorities(runtime), flags=self.flags
        )
        if transition is not None:
            value["transition"] = transition
        return encode_parts(value)
