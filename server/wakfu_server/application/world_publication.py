"""Application domain helpers extracted from the World bootstrap."""

import base64
import struct


class WorldPublication:
    def __init__(self, runtime):
        self.runtime = runtime

    def consumable_state_packets(self, character):
        from wakfu_server.consumable_buff_wire import snapshot

        return snapshot(
            character, allocate_action=lambda: next(self.runtime.LOCAL_WORLD_ACTIONS)
        )

    def world_state_packets(
        self, character, *, include_territory=True, reset_riding=False
    ):
        from wakfu_server.personal_ecology import snapshot as ecology_snapshot

        from wakfu_server.emotes import retained as emote_snapshot
        from wakfu_server.world_resurrection import snapshot as death_snapshot
        from wakfu_server.territory_bonus_wire import snapshot as territory_snapshot

        return (
            *self.runtime.mount_snapshot(character, reset_riding=reset_riding),
            *ecology_snapshot(character),
            *emote_snapshot(character),
            *self.runtime.consumable_state_packets(character),
            *(
                territory_snapshot(character["id"], character.get("territory_state_id"))
                if include_territory
                else ()
            ),
            *death_snapshot(self.runtime.STORE, character),
        )

    def rich_inventory_packet(self, character):
        """Build the selected character's independent ProtoItem UID registry."""
        from wakfu_server.inventory_items import equipment_inventory

        return equipment_inventory(character)

    def monster_corpse_snapshot(self, map_id, instance_id, *, peer=None, peers=()):
        """Reconcile only corpses delivered to these retained connection scenes."""
        from wakfu_server.monster_corpses import reconcile

        # Preserve identities while the socket temporarily leaves WORLD for a
        # fight/spectator view. A new socket has no historical removal backlog.
        with self.runtime.CORPSE_SCENES_LOCK:
            known = self.runtime.CORPSE_SCENES.get(peer, ()) if peer is not None else ()
            with self.runtime.STORE.connection() as db:
                packets, active = reconcile(db, map_id, instance_id, known)
            if peer is not None:
                self.runtime.CORPSE_SCENES[peer] = active
            for recipient in peers:
                # Exploration peers receive scheduler removals directly. Their
                # complete current-map replay supersedes previous tracked IDs.
                self.runtime.CORPSE_SCENES[recipient] = active
            return packets

    def join_world(
        self,
        generation,
        connection,
        character,
        *,
        hydrate_heroes=True,
        defer_scene_snapshot=False,
    ):
        if character.get("map_id") == 312 and self.runtime.is_dungeon_run(
            character.get("instance_id", 0)
        ):
            connection.pending_astrub_cat_story_bootstrap = True
        from wakfu_server.profession_store import ensure_all_learned
        from wakfu_server.consumable_world_lifecycle import synchronize

        character.update(
            synchronize(
                self.runtime.STORE,
                character["account_id"],
                generation,
                character,
                mode="resume",
            )
        )
        # A fresh scene load creates a new native world, unlike spectator return.
        with connection.write_lock:
            connection.marker_publications.reset(connection.native_instance_scope())

        profession = ensure_all_learned(
            self.runtime.STORE,
            character["account_id"],
            generation,
            character["id"],
        )
        from wakfu_server.achievements.intro_profession_bootstrap import (
            packets as profession_packets,
        )

        for packet in profession_packets(
            character.get("map_id"), profession["packets"]
        ):
            self.runtime.send(connection, "world", *packet)
        for packet in self.runtime.HAVEN_BAG_EXTERIORS.snapshots(character):
            self.runtime.send(connection, "world", *packet)
        self.runtime.send_planting_context(connection, character)
        if not defer_scene_snapshot:
            for packet in self.runtime.PLANTINGS.snapshots(
                character["map_id"], character["instance_id"], position=character
            ):
                self.runtime.send(connection, "world", *packet)
        from wakfu_server import npc_world, npc_placements

        if character.get("map_id") == 1361:
            from wakfu_server.achievements import incarnam_encounters

            tutorial_actor = incarnam_encounters.ensure_spawn(
                self.runtime.STORE, self.runtime.COMBAT_GROUPS, character
            )
            if tutorial_actor is not None:
                self.runtime.send(connection, "world", *tutorial_actor)

        with self.runtime.STORE.connection() as db:
            dialogue_npcs = npc_world.load_scene(
                db, character["map_id"], character["instance_id"]
            )
            if character["map_id"] == 1387:
                from wakfu_server.achievements import rii_guardian_battle

                dialogue_npcs = rii_guardian_battle.visible_dialogue_npcs(
                    db, character, dialogue_npcs
                )
            positioned_npcs = npc_placements.load_scene(
                db, character["map_id"], character["instance_id"]
            )
        for npc in dialogue_npcs:
            self.runtime.send(connection, "world", *npc_world.spawn(npc))
        for npc in positioned_npcs:
            self.runtime.send(connection, "world", *npc_placements.spawn(npc))
        from wakfu_server import owned_physical_offers

        with self.runtime.STORE.connection() as offer_db:
            physical_offers = owned_physical_offers.spawn_packets(
                offer_db, self.runtime.STORE, character
            )
        for packet in physical_offers:
            self.runtime.send(connection, "world", *packet)
        from wakfu_server import heroes, hero_wire

        hero_roster = heroes.ensure_company_party(
            self.runtime.STORE, character["account_id"], generation, character["id"]
        )
        if hydrate_heroes:
            for hero in hero_roster["heroes"]:
                self.runtime.send(
                    connection,
                    "world",
                    *hero_wire.activate(self.runtime.OWNED_HERO_TEMPLATE, hero),
                )
                self.runtime.send(connection, "world", *hero_wire.statistics(hero))
        # Repeated cue activation replaces owned objects without an activation
        # event. COMPANY rebuilds native hero rows from the final owned registry.
        self.runtime.send(
            connection,
            "world",
            *hero_wire.company(
                character["account_id"],
                character["id"],
                guild_id=(character.get("guild_native") or {}).get("guildId", 0),
                nation_id=character.get("nation_id", 0),
                company_snapshot=character["equipment_criterion_context"][
                    "company_snapshot"
                ],
            ),
        )
        if not self.runtime.COMBAT_TEST:
            self.runtime.WORLD.join(generation, connection, character)
            self.runtime.refresh_guild(generation, character)
            self.runtime.refresh_party(generation, character)
            return
        from wakfu_server.combat_monster_world import spawn_group

        # Snapshot and publishes use the same lock as group claims.
        with self.runtime.COMBAT_GROUPS.lock:
            self.runtime.WORLD.join(generation, connection, character)
            from wakfu_server.ecology_admin import admin_removed_packets

            with self.runtime.STORE.connection() as db:
                from wakfu_server.achievements.rii_lesson_visibility import (
                    scene_cleanup,
                )

                for packet in scene_cleanup(
                    db, character["map_id"], character["instance_id"]
                ):
                    self.runtime.send(connection, "world", *packet)
                for packet in admin_removed_packets(
                    db, character["map_id"], character["instance_id"]
                ):
                    self.runtime.send(connection, "world", *packet)
            for packet in self.runtime.monster_corpse_snapshot(
                character["map_id"], character["instance_id"], peer=connection
            ):
                self.runtime.send(connection, "world", *packet)
            if not defer_scene_snapshot:
                groups = self.runtime.COMBAT_GROUPS.available(
                    character["map_id"], character["instance_id"]
                )
                if character["map_id"] in (1387, 1388):
                    from wakfu_server.achievements.rii_lesson_visibility import (
                        visible_groups,
                    )

                    with self.runtime.STORE.connection() as db:
                        groups = visible_groups(db, groups, character["id"])
                from wakfu_server.achievements import source_quest_encounters

                if any(
                    source_quest_encounters.candidate_monsters(group["members"])
                    for group in groups
                ):
                    with self.runtime.STORE.connection() as db:
                        groups = source_quest_encounters.visible_groups(
                            db, groups, character["id"]
                        )
                for group in groups:
                    self.runtime.send(
                        connection,
                        "world",
                        12608,
                        self.runtime.owned_scene_spawn_group(
                            group["members"], group_id=group["key"][2]
                        ),
                    )
        for packet in self.runtime.HARVESTS.availability_snapshot(
            character["map_id"], character["instance_id"]
        ):
            self.runtime.send(connection, "world", *packet)
        for packet in self.runtime.EXTERNAL_FIGHT_MARKERS.world_snapshots(
            character["map_id"],
            character["instance_id"],
            exclude_character_id=character["id"],
        ):
            self.runtime.send(connection, "world", *packet)
        self.runtime.refresh_party(generation, character)

        self.runtime.refresh_guild(generation, character)

    def owned_scene_spawn_group(self, members, *, group_id, direction=3):
        """Keep native NPC world identity aligned with durable private ownership."""
        from wakfu_server.combat_monster_world import spawn_group
        from wakfu_server.guild_haven_world import scene_context

        members = tuple(members)
        if not members:
            raise ValueError("Cannot publish an empty monster group")
        first = members[0]
        context = scene_context(
            self.runtime.STORE, first["map_id"], first["instance_id"]
        )
        return spawn_group(
            members, group_id=group_id, direction=direction, world_context=context
        )

    def publish_available_group(self, key, members, *, exclude_generation=None):
        """Publish an available group only to its owner when it is private."""
        owner = None
        if key[0] in (1387, 1388):
            from wakfu_server.achievements.rii_lesson_visibility import group_owners

            with self.runtime.STORE.connection() as db:
                owner = group_owners(db, [{"key": key, "members": members}]).get(key)
        from wakfu_server.achievements import source_quest_encounters

        if owner is None and source_quest_encounters.candidate_monsters(members):
            with self.runtime.STORE.connection() as db:
                owner = source_quest_encounters.group_owners(
                    db, [{"key": key, "members": members}]
                ).get(key)
        self.runtime.WORLD.emit_location(
            key[0],
            key[1],
            12608,
            self.runtime.owned_scene_spawn_group(members, group_id=key[2]),
            exclude_generation=exclude_generation,
            only_character_id=owner,
        )

    def release_groups(self, generation):
        if not self.runtime.COMBAT_TEST or generation is None:
            return
        if self.runtime.COMBAT_SESSIONS.registry.lease_generation_active(generation):
            return
        from wakfu_server.combat_monster_world import spawn_group

        with self.runtime.COMBAT_GROUPS.lock:
            for group in self.runtime.COMBAT_GROUPS.release_session(generation):
                map_id, instance_id, group_id = group["key"]
                self.runtime.publish_available_group(group["key"], group["members"])
                for packet in self.runtime.HARVESTS.availability_for(
                    map_id, instance_id, [m["id"] for m in group["members"]]
                ):
                    self.runtime.WORLD.emit_location(map_id, instance_id, *packet)

    def reconcile_closed_rift_login(
        self,
        store,
        positions,
        account_id,
        generation,
        character,
        *,
        live_reconnect=False,
        fighting=None,
    ):
        """Return an interrupted, closed Rift company through its native exterior.

        This is login recovery, not a fabricated portal interaction. Native paid
        or conditional exits are never inferred, and terminal earned runs retain
        their ordinary report/exit flow. Relocation owns all company/position CAS.
        """
        instance_id = character.get("instance_id", 0)
        if live_reconnect or type(instance_id) is not int or instance_id <= 0:
            return None
        from wakfu_server.rift_interrupted_rewards import POLICY as interruption_policy

        with store.connection() as db:
            row = db.execute(
                "SELECT r.catalog FROM rift_instances r JOIN combat_fights f ON f.id=r.fight_id "
                "WHERE r.instance_id=%s AND r.status IN('running','closed') AND f.status='aborted' "
                "AND (NOT EXISTS(SELECT 1 FROM rift_settlement_receipts s "
                "WHERE s.instance_id=r.instance_id) OR EXISTS("
                "SELECT 1 FROM rift_settlement_receipts s WHERE s.instance_id=r.instance_id "
                "AND s.fight_id=f.id AND s.outcome='closed' "
                "AND s.result->'recovery'->>'policy'=%s "
                "AND s.result->'recovery'->>'reason'='startup_interruption'))",
                (instance_id, interruption_policy),
            ).fetchone()
        if row is None:
            return None
        catalog = row["catalog"]
        if catalog["map_id"] != character["map_id"]:
            raise ValueError("Closed Rift login differs from its native interior")
        from wakfu_server import generic_transports, rift_exit

        destinations = []
        for entry in catalog["objects"]:
            if entry["type"] != "Teleporter" or entry["map_id"] != character["map_id"]:
                continue
            source = generic_transports.source(entry["map_id"], entry["id"])
            if source is None:
                continue
            for target in source["destinations"]:
                if (
                    target["criterion"].strip()
                    or target["cyW"] != 0
                    or target["cyX"] != 0
                    or target["cyZ"] >= 0
                    or target["native_altitude_walkable"] is not True
                    or target["map_id"] == character["map_id"]
                ):
                    continue
                destinations.append(
                    {
                        **{key: target[key] for key in ("map_id", "x", "y", "z")},
                        "instance_id": 0,
                    }
                )
        if len(destinations) != 1:
            raise ValueError("Closed Rift login requires one unconditional native exit")
        moved = rift_exit.relocate(
            store,
            positions,
            account_id,
            generation,
            character["id"],
            character,
            destinations[0],
            fighting=fighting,
        )
        if moved is None:
            raise ValueError("Closed Rift login lost its owned departure scope")
        return store.character(account_id, character["id"])

    def acknowledge_rift_login_bootstrap(self, account_id, generation, character):
        """Called only after initial native bootstrap and World join succeeded."""
        from wakfu_server import rift_transition_delivery

        destination = rift_transition_delivery.pending(
            account_id, generation, character["id"]
        )
        if (
            destination is not None
            and destination.get("refresh_current_owned_position") is True
        ):
            if not self.runtime.STORE.current_character_session(
                account_id, generation, character["id"]
            ):
                raise ValueError("Owned position refresh belongs to a replaced session")
            saved = self.runtime.STORE.character(account_id, character["id"])
            if any(
                saved[key] != character[key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            ):
                return
            rift_transition_delivery.acknowledge(
                account_id, generation, character["id"], destination
            )
            return
        if destination is not None and all(
            character[key] == destination[key]
            for key in ("map_id", "instance_id", "x", "y", "z")
        ):
            rift_transition_delivery.acknowledge(
                account_id, generation, character["id"], destination
            )

    def is_dungeon_run(self, instance_id):
        if (
            not self.runtime.DUNGEON_ROOM_RUNTIME_AVAILABLE
            or type(instance_id) is not int
            or instance_id <= 0
        ):
            return False
        with self.runtime.STORE.connection() as db:
            return db.execute(
                "SELECT EXISTS(SELECT 1 FROM dungeon_instances WHERE instance_id=%s AND status='active') AS present",
                (instance_id,),
            ).fetchone()["present"]

    def owned_native_bootstrap(self, character, **options):
        if (character.get("map_id"), character.get("instance_id", 0)) == (1385, 0):
            from wakfu_server import npc_protectors

            with self.runtime.STORE.connection() as db:
                options["protector_records"] = npc_protectors.bootstrap_records(
                    db, character
                )
        if self.runtime.is_dungeon_run(character.get("instance_id", 0)):
            from wakfu_server import dungeon_context

            with self.runtime.STORE.connection() as db:
                fighting = db.execute(
                    "SELECT EXISTS(SELECT 1 FROM combat_fights f JOIN dungeon_room_encounters e "
                    "ON e.fight_id=f.id WHERE e.instance_id=%s AND e.status='active' "
                    "AND f.status IN ('placement','active')) AS fighting",
                    (character["instance_id"],),
                ).fetchone()["fighting"]
            options["dungeon_context"] = dungeon_context.for_instance(
                self.runtime.STORE, character["instance_id"], fight_in_progress=fighting
            )
        messages = self.runtime.native_transports.bootstrap(character, **options)
        if not self.runtime.is_dungeon_run(character.get("instance_id", 0)):
            return messages
        from wakfu_server import (
            dungeon_object_states,
            dungeon_runtime,
            generic_transports,
            owned_noncombat_context,
        )

        with self.runtime.STORE.connection() as db:
            _, configuration = dungeon_runtime.configuration_for_instance(
                db, character["instance_id"]
            )
            progress = db.execute(
                "SELECT current_room, status FROM dungeon_room_runs WHERE instance_id=%s",
                (character["instance_id"],),
            ).fetchone()
            noncombat = owned_noncombat_context.authenticate_bootstrap(
                db, self.runtime.STORE, character, configuration
            )
        if noncombat and progress is not None:
            raise ValueError("Noncombat owned bootstrap has unexpected room progress")
        if not noncombat and progress is None:
            raise ValueError("Dungeon bootstrap has no committed room progress")
        from wakfu_server import dungeon_native_flow, dungeon_optional_continuations

        from wakfu_server import native_scene_start, owned_story_npcs

        # A full native bootstrap must publish instance NPCs before their
        # continuation scenes. Its existing successful-write acknowledgement
        # then unlocks interactions/scene arguments after a context refresh.
        with self.runtime.STORE.connection() as npc_db:
            messages = tuple(messages) + tuple(
                owned_story_npcs.spawn_packets(
                    npc_db, self.runtime.STORE, character, context_bootstrap=True
                )
            )
        continuation_packets = dungeon_optional_continuations.packets(
            configuration["topology"]
        ) + native_scene_start.packets(configuration["topology"])
        if noncombat:
            return tuple(messages) + continuation_packets
        if dungeon_native_flow.enabled(configuration["topology"]):
            return (
                tuple(messages)
                + dungeon_native_flow.packets(
                    configuration["topology"],
                    map_id=character["map_id"],
                    instance_id=character["instance_id"],
                    unlocked_room=progress["current_room"],
                    completed=progress["status"] == "completed",
                    recipient_character_id=character["id"],
                )
                + continuation_packets
            )
        sources = [
            row
            for row in generic_transports._CATALOG
            if row["map_id"] == character["map_id"]
        ]
        return (
            tuple(messages)
            + dungeon_object_states.packets(
                configuration["topology"],
                sources,
                map_id=character["map_id"],
                instance_id=character["instance_id"],
                unlocked_room=progress["current_room"],
                completed=progress["status"] == "completed",
            )
            + continuation_packets
        )

    def owned_haven_leave(self, body, character):
        from wakfu_server.haven_bag import leave_messages

        messages = leave_messages(body, character)
        if not self.runtime.is_dungeon_run(character.get("instance_id", 0)):
            return messages
        context_packet = next(
            payload
            for message_id, payload in self.runtime.owned_native_bootstrap(character)
            if message_id == 13974
        )
        return tuple(
            (message_id, context_packet if message_id == 13974 else payload)
            for message_id, payload in messages
        )

    def native_current_xp_rate(self):
        """Publish the canonical server rate through the native single-key carrier."""
        with self.runtime.STORE.connection() as db:
            policy = db.execute(
                "SELECT v.xp_rate_bp FROM combat_reward_policy_active a "
                "JOIN combat_reward_policy_versions v USING(version) WHERE a.singleton"
            ).fetchone()
        if policy is None:
            raise ValueError("Missing canonical XP presentation policy")
        return self.runtime.wire.native_xp_rate_packet(policy["xp_rate_bp"])

    def replay(
        self, connection, start, end, account_id, character=None, *, generation=None
    ):
        from wakfu_server.haven_chest_wire import CAPTURE_STATE_OPCODES

        account_characters = None
        registry_actor_ids = ()
        temporary_followups = []
        temporary_entity_sent = False
        if character is not None:
            from wakfu_server.combat_drop_delivery import temporary_bootstrap

            with self.runtime.STORE.connection() as db:
                self.runtime.STORE.lock_character(
                    db, account_id, generation, character["id"]
                )
                temporary_section, temporary_followups = temporary_bootstrap(
                    db, character["id"]
                )
                character = {
                    **character,
                    "temporary_inventory_section": temporary_section,
                }
                registry_actor_ids = tuple(
                    row["actor_id"]
                    for row in db.execute(
                        "SELECT actor_id FROM world_dialogue_npcs "
                        "UNION SELECT actor_id FROM world_native_npc_placements"
                    )
                )

        def owned_characters():
            nonlocal account_characters
            if account_characters is None:
                account_characters = self.runtime.STORE.characters(account_id)
            return account_characters

        if character is not None and start == 45:
            self.runtime.send(
                connection, "world", *self.runtime.native_current_xp_rate()
            )
        for frame in self.runtime.FRAMES[start:end]:
            if frame["direction"] == "in":
                if frame["opcode"] in (12705, 12728):
                    # Reference running effects belong to the captured actor. An
                    # identity rewrite can target our player with foreign visual
                    # state; only authoritative live emitters may publish effects.
                    continue
                if frame["opcode"] in CAPTURE_STATE_OPCODES:
                    # Account chest compartments and updates belong exclusively
                    # to PostgreSQL-owned custody, never the reference account.
                    continue
                if frame["opcode"] == 13369:
                    # Authoritative owned task/gift publication replaces fixture state.
                    continue
                if frame["opcode"] in (12789, 13948):
                    # Ecology comes from the current native region and our own
                    # population; weather is published from exact territory state.
                    # Never apply a captured region's climate to another region.
                    continue
                if (
                    character is not None
                    and character["map_id"] != 1134
                    and frame["opcode"]
                    in {
                        12318,
                        12549,
                        12608,
                        12789,
                        13369,
                        13411,
                        13664,
                        13753,
                        13877,
                        13984,
                    }
                ):
                    # These fixture packets belong to the original1134 map. A
                    # verified destination bootstrap supplies its own world data.
                    continue
                if (
                    frame["opcode"] == 13974
                    and character is not None
                    and self.runtime.is_dungeon_run(character.get("instance_id", 0))
                ):
                    for message_id, payload in self.runtime.owned_native_bootstrap(
                        character
                    ):
                        if message_id == 13974:
                            self.runtime.send(connection, "world", message_id, payload)
                    continue
                original = base64.b64decode(frame["body_base64"])
                if frame["opcode"] == 22995:
                    # Never replay an official account's HTTP shop credentials.
                    continue
                if frame["opcode"] == 630 and generation is not None:
                    for social_packet in self.runtime.SOCIAL_ACTIONS.bootstrap(
                        account_id, generation
                    ):
                        self.runtime.send(connection, "world", *social_packet)
                    continue
                if frame["opcode"] == 23082 and character is not None:
                    from wakfu_server.builds import capacity_message

                    self.runtime.send(connection, "world", *capacity_message(character))
                if frame["opcode"] in (12722, 13369):
                    from wakfu_server.gifts import empty_message

                    self.runtime.send(
                        connection,
                        "world",
                        frame["opcode"],
                        empty_message(frame["opcode"]),
                    )
                    continue
                if frame["opcode"] == 23354:
                    self.runtime.send(
                        connection,
                        "world",
                        23354,
                        self.runtime.world_clock.packet(
                            offset_ms=self.runtime.CLOCK_OFFSET_MS
                        ),
                    )
                    continue
                if frame["opcode"] == 13873 and original[:8] == struct.pack(
                    ">II", 1, 4
                ):
                    from wakfu_server.exploration_secrets import (
                        account_packet as exploration_account_packet,
                    )

                    with self.runtime.STORE.connection() as db:
                        secret_packet = exploration_account_packet(db, account_id)
                    self.runtime.send(connection, "world", *secret_packet)
                    continue
                if (
                    character is not None
                    and frame["opcode"] == 13873
                    and original[:8] == struct.pack(">II", 1, 1)
                ):
                    from wakfu_server.hero_wire import company as hero_company

                    self.runtime.send(
                        connection,
                        "world",
                        *hero_company(
                            account_id,
                            character["id"],
                            guild_id=(character.get("guild_native") or {}).get(
                                "guildId", 0
                            ),
                            nation_id=character.get("nation_id", 0),
                            company_snapshot=character["equipment_criterion_context"][
                                "company_snapshot"
                            ],
                        ),
                    )
                    continue
                if frame["opcode"] == 13873 and original[:8] == struct.pack(
                    ">II", 1, 10
                ):
                    from wakfu_server.emotes import (
                        packet as emote_account_packet,
                    )

                    self.runtime.send(
                        connection,
                        "world",
                        *emote_account_packet(self.runtime.STORE, account_id),
                    )
                    continue
                if frame["opcode"] == 13873 and original[:8] == struct.pack(
                    ">II", 1, 11
                ):
                    from wakfu_server.haven_bag_furniture_knowledge import (
                        packet as furniture_account_packet,
                    )

                    self.runtime.send(
                        connection,
                        "world",
                        *furniture_account_packet(self.runtime.STORE, account_id),
                    )
                    from wakfu_server.haven_ranch_building_knowledge import (
                        packet as ranch_building_account_packet,
                    )

                    self.runtime.send(
                        connection,
                        "world",
                        *ranch_building_account_packet(self.runtime.STORE, account_id),
                    )
                    continue
                if frame["opcode"] == 13873 and original[:8] == struct.pack(
                    ">II", 1, 18
                ):
                    # The preceding furniture component publishes owned Ranch
                    # knowledge; never overwrite it with the captured template.
                    continue
                if frame["opcode"] == 13873 and original[:8] == struct.pack(
                    ">II", 1, 12
                ):
                    (
                        message_id,
                        message_body,
                    ) = self.runtime.transport_discovery.account_packet(
                        self.runtime.known_transports(account_id)
                    )
                    self.runtime.send(connection, "world", message_id, message_body)
                    continue
                if frame["opcode"] == 13873 and original[:8] == struct.pack(
                    ">II", 1, 13
                ):
                    from wakfu_server.tutorials import payload as tutorial_payload

                    self.runtime.send(
                        connection,
                        "world",
                        13873,
                        struct.pack(">II", 1, 13)
                        + tutorial_payload(self.runtime.STORE, account_id),
                    )
                    continue
                if frame["opcode"] == 13873 and original[:8] == struct.pack(
                    ">II", 1, 14
                ):
                    from wakfu_server.profession_store import account_packet

                    with self.runtime.STORE.connection() as db:
                        craft_packet = account_packet(db, account_id)
                    self.runtime.send(connection, "world", *craft_packet)
                    continue
                owned = (
                    owned_characters()
                    if frame["opcode"] == 13873
                    and original[:8] == struct.pack(">II", 2, 0)
                    else None
                )
                if frame["opcode"] == 22790:
                    from wakfu_server import companions

                    with self.runtime.STORE.connection() as companion_db:
                        companion_packet = companions.collection_packet(
                            companions.collection(companion_db, account_id)
                        )
                    self.runtime.send(connection, "world", *companion_packet)
                    continue
                social_body = self.runtime.social.adapt(
                    frame["opcode"],
                    original,
                    account_id,
                    character,
                    owned,
                    cosmetic_record=(
                        self.runtime.STORE.cosmetic_record(account_id)
                        if frame["opcode"] == 13873
                        and original[:8]
                        in (
                            struct.pack(">II", 1, 8),
                            struct.pack(">II", 1, 9),
                            struct.pack(">II", 2, 8),
                        )
                        else None
                    ),
                )
                if social_body is not None:
                    self.runtime.send(connection, "world", frame["opcode"], social_body)
                    continue
                if frame["opcode"] == 13078 and character is None:
                    # Account equipment inventories precede character selection.
                    # Only seed owned characters from the known Pekebu inventory.
                    if (
                        struct.unpack(">q", original[:8])[0]
                        == self.runtime.wire.TEMPLATE_CHARACTER
                    ):
                        for owned in owned_characters():
                            self.runtime.send(
                                connection,
                                "world",
                                13078,
                                self.runtime.wire.adapt(
                                    13078, original, account_id, owned
                                ),
                            )
                    continue
                if frame["opcode"] == 23053:
                    from wakfu_server.hero_wire import (
                        configuration as hero_configuration,
                    )

                    self.runtime.send(
                        connection, "world", *hero_configuration(original)
                    )
                    self.runtime.send(
                        connection, "world", *self.runtime.native_current_xp_rate()
                    )
                    continue
                if frame["opcode"] in (23992, 23548):
                    from wakfu_server.selection_capacity import (
                        packet as capacity_packet,
                    )

                    self.runtime.send(
                        connection,
                        "world",
                        *capacity_packet(self.runtime.STORE.max_characters),
                    )
                    if frame["opcode"] == 23992:
                        continue
                if frame["opcode"] == 23548:
                    body = self.runtime.wire.character_list(
                        self.runtime.CHARACTERS, account_id, owned_characters()
                    )
                elif frame["opcode"] == 12393:
                    body = self.runtime.wire.attribute_sheets(
                        original, owned_characters()
                    )
                elif frame["opcode"] == 12608:
                    body = self.runtime.wire.without_captured_players(original)
                    if character is not None:
                        from wakfu_server.npc_capture_scene import (
                            filter_reference_actors,
                        )

                        body = filter_reference_actors(
                            body, character, registry_actor_ids=registry_actor_ids
                        )
                elif frame["opcode"] == 13664:
                    body = self.runtime.wire.without_captured_haven_bags(original)
                    self.runtime.send(
                        connection,
                        "world",
                        13082,
                        self.runtime.wire.remove_captured_haven_bags(original),
                    )
                else:
                    body = self.runtime.wire.adapt(
                        frame["opcode"],
                        original,
                        account_id,
                        character,
                        kamas=self.runtime.STORE.account_kamas(account_id),
                    )
                self.runtime.send(connection, "world", frame["opcode"], body)
                if character is not None and frame["opcode"] in (12666, 13713, 15548):
                    temporary_entity_sent = True
        if temporary_entity_sent:
            for packet in temporary_followups:
                self.runtime.send(connection, "world", *packet)

    def combat_group_for_target(self, registry, character, target):
        """Select the authoritative available roster in the actor's map instance."""
        candidates = [
            group
            for group in registry.available(
                character["map_id"], character["instance_id"]
            )
            if any(member["id"] == target for member in group["members"])
        ]
        if len(candidates) != 1:
            raise ValueError("No unique available combat group for this target")
        group = candidates[0]
        if (
            group["key"][:2] != (character["map_id"], character["instance_id"])
            or not group["members"]
            or any(
                member["map_id"] != character["map_id"]
                or member.get("instance_id", 0) != character["instance_id"]
                for member in group["members"]
            )
        ):
            raise ValueError("Combat group has a foreign map or instance")
        return group

    def harvest_target(self, character, target):
        try:
            group = self.runtime.combat_group_for_target(
                self.runtime.COMBAT_GROUPS, character, target
            )
        except ValueError:
            from wakfu_server.monster_corpses import resolve_target

            with self.runtime.STORE.connection() as db:
                return resolve_target(db, character, target)
        member = next(m for m in group["members"] if m["id"] == target)
        return dict(member, instance_id=group["key"][1])
