"""Application domain helpers extracted from the World bootstrap."""


class EcologyPublication:
    def __init__(self, runtime):
        self.runtime = runtime

    def ecology_admin_coordination(self, scope):
        """Keep administrative application on the existing live-world fences."""
        if not self.runtime.COMBAT_TEST:
            raise ValueError("Persistent ecology administration is unavailable")
        with (
            self.runtime.COMBAT_GROUPS.lock,
            self.runtime.HARVESTS.lock,
            self.runtime.PLANTINGS.publisher_lock,
            self.runtime.PLANTINGS.lock,
            self.runtime.PLANTINGS.growth_lock,
        ):
            yield

    def publish_ecology_admin_outcome(self, outcome):
        """Publish committed scopes without capturing a mutable player session."""
        if outcome.get("command") in ("!nuke", "!nuke-all", "!nuke-all-flora"):
            from wakfu_server.ecology_admin_runtime import cancel_plantings

            cancel_plantings(self.runtime.PLANTINGS, outcome)
        for map_id, instance_id, opcode, payload in outcome.get("location_packets", ()):
            self.runtime.WORLD.emit_location(map_id, instance_id, opcode, payload)
        from wakfu_server.ecology_context import packet as ecology_packet
        from wakfu_server.territory_cells import region_at

        recipients = tuple(self.runtime.WORLD.players.values())
        for player_generation, peer, player in recipients:
            for map_id, instance_id, region_id in outcome.get("scopes", ()):
                if (player["map_id"], player.get("instance_id", 0)) != (
                    map_id,
                    instance_id,
                ):
                    continue
                if (
                    region_id is not None
                    and region_at(map_id, player["x"], player["y"]) != region_id
                ):
                    continue
                try:
                    packet = ecology_packet(
                        self.runtime.STORE,
                        player,
                        open_test_policy=self.runtime.OPEN_PLANTING,
                    )
                except ValueError as error:
                    self.runtime.record(
                        event="ecology_admin_context_unavailable",
                        actor_id=player["id"],
                        reason=str(error),
                    )
                else:
                    self.runtime.WORLD.send_to_if_location(
                        player["id"], player_generation, player, *packet, peer=peer
                    )
                break

    def validate_ecology_admin_job(self, db, job):
        if self.runtime.STOPPING.is_set():
            raise self.runtime.EcologyAdminCancelled("World is stopping")

    def submit_ecology_admin_command(
        self, connection, service, account_id, generation, character, command, text
    ):
        """Accept an authorized ecology command before any foreground checkpoint."""
        if command not in self.runtime.ASYNC_ECOLOGY_COMMANDS:
            return None
        from wakfu_server.ecology_admin_jobs import parse_mob_count

        mob_count = parse_mob_count(command, text.split()[1:])
        from wakfu_server.ecology_feedback import information

        actor_id = character["id"]

        def notify(completed):
            self.runtime.record(
                event="ecology_admin_job_finished",
                actor_id=actor_id,
                command=command,
                handle=completed["handle"],
                status=completed["status"],
                elapsed_ms=completed.get("elapsed_ms"),
                worker_pid=completed.get("worker_pid"),
                error_type=completed.get("error_type"),
                error_code=completed.get("error_code"),
                reason=completed.get("reason"),
                traceback=completed.get("traceback"),
                added=completed.get("added", 0),
                removed=completed.get("removed", 0),
            )
            self.runtime.WORLD.send_to(
                actor_id, generation, *information(completed["message"])
            )

        receipt = self.runtime.ECOLOGY_ADMIN_JOBS.request(
            account_id=account_id,
            generation=generation,
            character=character,
            command=command,
            notify=notify,
            **({"mob_count": mob_count} if mob_count is not None else {}),
        )
        self.runtime.send(connection, service, *information(receipt["message"]))
        self.runtime.record(
            event="ecology_admin_job_submitted",
            actor_id=actor_id,
            command=command,
            handle=receipt["handle"],
            coalesced=receipt["coalesced"],
        )
        return {"message": receipt["message"], "ecology_job": receipt}

    def territory_weather_region_changed(self, map_id, old_position, new_position):
        """Return whether an accepted walk entered a different known region."""
        from wakfu_server.territory_cells import region_at

        try:
            previous = region_at(map_id, old_position["x"], old_position["y"])
        except (KeyError, ValueError):
            previous = None
        try:
            current = region_at(map_id, new_position["x"], new_position["y"])
        except (KeyError, ValueError):
            return False
        return current != previous

    def send_native_planting_bonus(self, connection, character):
        if self.runtime.NATIVE_PLANTING_BONUS:
            self.runtime.PLANTING_BONUSES.publish(
                connection,
                character,
                lambda packets: self.runtime.send_batch(connection, "world", packets),
            )

    def send_planting_context(self, connection, character, *, include_weather=True):
        self.runtime.send_native_planting_bonus(connection, character)
        from wakfu_server.ecology_context import packet as ecology_packet
        from wakfu_server.territory_weather_forecast import packet_for_territory
        from wakfu_server.territory_weather import context as weather_context

        try:
            packet = ecology_packet(
                self.runtime.STORE,
                character,
                open_test_policy=self.runtime.OPEN_PLANTING,
            )
            self.runtime.send(connection, "world", *packet)
        except ValueError as error:
            self.runtime.record(
                event="planting_context_unavailable",
                actor_id=character["id"],
                map_id=character["map_id"],
                reason=str(error),
            )
        try:
            from wakfu_server.territory_bonuses import refresh_world

            entry = self.runtime.WORLD.players.get(character["id"])
            bonus_generation = (
                entry[0] if entry is not None and entry[1] is connection else None
            )
            refreshed = dict(character)
            bonus_packets = refresh_world(
                self.runtime.STORE, refreshed, generation=bonus_generation
            )
            for key in (
                "hp",
                "max_hp",
                "hp_damage",
                "health_dead",
                "hp_zero_valid",
                "territory_health_projection",
                "equipment_hp_projection",
            ):
                if key in refreshed:
                    character[key] = refreshed[key]
            for bonus_packet in bonus_packets:
                self.runtime.send(connection, "world", *bonus_packet)
            character["territory_stat_bonuses"] = refreshed["territory_stat_bonuses"]
            character["_published_territory_stat_bonuses"] = refreshed[
                "_published_territory_stat_bonuses"
            ]
            character["territory_state_id"] = refreshed["territory_state_id"]
            character["_published_territory_state_id"] = refreshed[
                "_published_territory_state_id"
            ]
            self.runtime.REGIONAL_BONUSES.mark_context_refreshed(character)
            if bonus_generation is not None:
                self.runtime.WORLD.update_territory_projection(
                    bonus_generation,
                    character,
                    peer=connection,
                    bonuses=character["territory_stat_bonuses"],
                    regional_state_id=character["territory_state_id"],
                )
        except ValueError as error:
            self.runtime.record(
                event="territory_bonus_unavailable",
                actor_id=character["id"],
                reason=str(error),
            )
        if not include_weather:
            return
        try:
            weather = weather_context(
                self.runtime.STORE,
                character,
                x=character["x"],
                y=character["y"],
                z=character["z"],
            )
        except ValueError as error:
            self.runtime.record(
                event="territory_weather_unavailable",
                actor_id=character["id"],
                map_id=character["map_id"],
                instance_id=character["instance_id"],
                reason=str(error),
            )
            return
        self.runtime.send(connection, "world", 13948, weather["native_payload"])
        try:
            forecast = weather.get("forecast_payload")
            if forecast is None:
                forecast = packet_for_territory(
                    self.runtime.STORE,
                    map_id=character["map_id"],
                    instance_id=character["instance_id"],
                    region_id=weather["region_id"],
                )
        except ValueError as error:
            self.runtime.record(
                event="territory_weather_forecast_unavailable",
                actor_id=character["id"],
                map_id=character["map_id"],
                instance_id=character["instance_id"],
                reason=str(error),
            )
            return
        self.runtime.send(connection, "world", 13895, forecast)
