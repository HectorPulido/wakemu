"""Wire external proposals to short authoritative live-world operations."""


def configure_domains(bridge, *, regional_bonuses=None):
    if regional_bonuses is None:
        from wakfu_server.territory_bonus_updates import RegionalBonusUpdates

        regional_bonuses = RegionalBonusUpdates(bridge.store, bridge.world)
    from wakfu_server import ecology_plants, ecology_mobs, ecology_weather
    from wakfu_server import ecology_population

    def authorize_spawn(resource):
        location = (resource["map_id"], resource["instance_id"])
        destination = tuple(resource[key] for key in ("x", "y", "z"))
        if any(
            (player["map_id"], player["instance_id"]) == location
            and tuple(player[key] for key in ("x", "y", "z")) == destination
            for player in bridge.world.ecology_snapshot()
        ):
            return False
        with bridge.store.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM combat_groups g, jsonb_array_elements(g.members) m "
                    "WHERE g.map_id=%s AND g.instance_id=%s "
                    "AND g.status IN ('available','fighting') "
                    "AND (m->>'x')::integer=%s AND (m->>'y')::integer=%s "
                    "AND (m->>'z')::integer=%s LIMIT 1",
                    (*location, *destination),
                ).fetchone()
                is None
            )

    def planting_intent(proposal):
        from wakfu_server import wire
        from wakfu_server.haven_bag_garden import authorize as authorize_garden

        identity, generation = proposal["character_id"], proposal["generation"]
        with bridge.world.lock:
            entry = bridge.world.players.get(identity)
            character = (
                dict(entry[2]) if entry is not None and entry[0] == generation else None
            )
        if character is None:
            bridge.plantings.ecology_intents.cancel(identity, generation)
            return {"applied": False}
        if character["account_id"] != proposal["account_id"] or (
            bridge.combat_sessions is not None
            and bridge.combat_sessions.lookup_character(identity) is not None
        ):
            bridge.plantings.ecology_intents.cancel(identity, generation)
            return {"applied": False}

        def authorize_cell(current, request, seed, resource):
            z = proposal["prepared"]["z"]
            if current["map_id"] == 9:
                z = authorize_garden(bridge.store, current, request, seed, resource)
            if not authorize_spawn(
                dict(
                    map_id=current["map_id"],
                    instance_id=current["instance_id"],
                    x=request["x"],
                    y=request["y"],
                    z=z,
                )
            ):
                raise ValueError("Planting cell is occupied")
            return z

        def begin(db, accepted):
            return bridge.plantings.begin_prepared(
                accepted["account_id"],
                generation,
                character,
                bytes.fromhex(accepted["body_hex"]),
                accepted["prepared"],
                authorize_cell,
                db=db,
            )

        try:
            with bridge.groups.lock, bridge.harvests.lock:
                result = bridge.plantings.ecology_intents.apply(proposal, begin)
        except ValueError as error:
            bridge.plantings.cancel(identity, generation)
            bridge.world.send_to(
                identity,
                generation,
                674,
                wire.chat(dict(character, name="Consola local"), str(error)),
            )
            return {"applied": True, "rejected": True}
        except Exception:
            bridge.plantings.cancel(identity, generation)
            raise
        if result.get("rejected"):
            bridge.world.send_to(
                identity,
                generation,
                674,
                wire.chat(dict(character, name="Consola local"), result["error"]),
            )
        elif result.get("packet"):
            try:
                bridge.world.emit_location_batch(
                    character["map_id"],
                    character["instance_id"],
                    [result["packet"]],
                    require_all=True,
                )
            except Exception:
                bridge.plantings.cancel(identity, generation)
                raise
        return result

    def plants(proposal):
        if proposal.get("kind") in ("planting_begin", "planting_rejected"):
            return planting_intent(proposal)
        feedback = []

        def publish(result):
            ecology = result.get("ecology")
            if ecology and ecology.get("packets"):
                feedback.append(ecology)
            bridge.world.emit_location_batch(
                result["map_id"],
                result["instance_id"],
                result["packets"],
                require_all=True,
            )

        with bridge.groups.lock, bridge.harvests.lock:
            result = ecology_plants.apply(
                bridge.plantings,
                bridge.groups,
                proposal,
                authorize_spawn=authorize_spawn,
                publish=publish,
            )
        # Account hydration is not part of the combat/group critical section.
        for ecology in feedback:
            with bridge.store.connection() as db:
                owner = db.execute(
                    "SELECT account_id FROM characters WHERE id=%s",
                    (ecology["character_id"],),
                ).fetchone()
                if owner is None:
                    continue
                character = bridge.store.character(
                    owner["account_id"], ecology["character_id"], db
                )
            bridge.world.publish_ecology(character)
            if not ecology.get("duplicate") and ecology.get("information"):
                bridge.world.information(
                    ecology["character_id"], ecology["information"]
                )
        return result

    def mobs(proposal):
        return ecology_mobs.apply(
            bridge.store,
            bridge.groups,
            bridge.harvests,
            bridge.world,
            proposal,
            world_epoch=bridge.epoch,
        )

    def weather(proposal):
        return ecology_weather.apply(bridge.store, bridge.world, proposal)

    def population(proposal):
        result = ecology_population.apply(
            bridge.store,
            bridge.groups,
            bridge.harvests,
            bridge.world,
            proposal,
            world_epoch=bridge.epoch,
        )
        return {"status": result} if isinstance(result, str) else result

    bridge.handlers.update(
        plants=plants,
        mobs=mobs,
        weather=weather,
        population=population,
        bonuses=lambda proposal: regional_bonuses.apply(
            proposal, world_epoch=bridge.epoch
        ),
    )
    return bridge
