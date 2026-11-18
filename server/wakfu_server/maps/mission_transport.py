"""Settle mission facts in the same transaction as native travel."""


def _changed(source, destination):
    return (source["map_id"], source.get("instance_id", 0)) != (
        destination["map_id"],
        destination.get("instance_id", 0),
    )


def departure_packets(db, store, source, destination):
    """A qualified movement's actual destination, evaluated at its origin."""
    if not _changed(source, destination):
        return []
    from uuid import uuid4
    from wakfu_server.achievements import mission_toolkit

    return mission_toolkit.settle(
        db,
        store,
        source,
        token="departure:" + uuid4().hex,
        kind="map_departure",
        reference=destination["map_id"],
    )


def arrival_packets(db, store, source, saved):
    """Observe the actual saved map after its authenticated compare-and-set."""
    if not _changed(source, saved):
        return []
    from uuid import uuid4
    from wakfu_server.achievements import mission_toolkit

    return mission_toolkit.settle(
        db,
        store,
        saved,
        token="travel:" + uuid4().hex,
        kind="map_enter",
        reference=saved["map_id"],
    )


def public_transition_locked(db, store, account_id, generation, source, destination):
    """Public NPC journeys share the caller's accepted-action SQL transaction."""
    packets = departure_packets(db, store, source, destination)
    saved = store.transition_map_in_transaction(
        db, account_id, generation, source["id"], source, destination
    )
    packets.extend(arrival_packets(db, store, source, saved))
    return store.character(account_id, saved["id"], db), packets


def transition(
    store, account_id, generation, source, route, *, native_zaap, incarnam_exit=False
):
    """Move an owned character and apply any qualified zone or Zaap events.

    ``route`` has already passed the transport resolver and its authorization.
    A rejected transition or failed mission settlement rolls back both together.
    Returned packets are sent only after the destination scene is published.
    """
    from wakfu_server.achievements import rii_dojo_arrival, zone_missions

    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        if incarnam_exit:
            from wakfu_server.achievements import storage

            store.lock_character(
                db, account_id, generation, source["id"], selected=True
            )
            current = store.character(account_id, source["id"], db)
            state = storage.load_locked(db, source["id"])
            receipt = db.execute(
                "SELECT 1 FROM character_achievement_events WHERE character_id=%s "
                "AND event_key=%s",
                (source["id"], "incarnam-final-fight:won"),
            ).fetchone()
            if (
                current.get("map_id") != 1361
                or 5139 not in state["running"]
                or receipt is None
                or route["destination"].get("map_id") != 1385
            ):
                raise ValueError("Incarnam final scene is not eligible for departure")
        departing = departure_packets(db, store, source, route["destination"])
        saved = store.transition_map_in_transaction(
            db, account_id, generation, source["id"], source, route["destination"]
        )
        from wakfu_server.achievements import native_transport_objectives

        transport_packets = native_transport_objectives.on_transition(
            db, store, source, saved, route
        )
        if transport_packets:
            saved = store.character(account_id, saved["id"], db)
        packets = departing + zone_missions.enter_rii(
            db, store, saved, previous_map=source["map_id"]
        )
        if source["map_id"] == 1465 and saved["map_id"] == 1361:
            from wakfu_server.achievements import incarnam_tutorial

            packets += incarnam_tutorial.enter(
                db, store, saved, previous_map=source["map_id"]
            )
        first_rii_arrival = bool(packets)
        packets += transport_packets
        if source["map_id"] != 1385 and saved["map_id"] == 1385:
            from wakfu_server.achievements import rii_class_mission

            packets += rii_class_mission.start(
                db, store, saved, previous_map=source["map_id"]
            )
        if (route.get("interactive_element_id"), route.get("destination_id")) == (
            34619,
            4560,
        ):
            from wakfu_server.achievements import rii_sanctuary

            packets += rii_sanctuary.enter(db, store, source, saved, route)
        if (
            saved["map_id"] == rii_dojo_arrival.DOJO_MAP
            and source["map_id"] != rii_dojo_arrival.DOJO_MAP
        ):
            # Native dojo script bootstrap: the client needs the scene actor
            # identities and the ready event before its lesson UI is valid.
            packets += rii_dojo_arrival.arrival_packets(rii_dojo_arrival.scene_uids(db))
        if native_zaap:
            from wakfu_server.achievements import transport_missions

            packets += transport_missions.on_native_transport(
                db, store, source, saved, route
            )
        if (source["map_id"], source["instance_id"]) != (
            saved["map_id"],
            saved["instance_id"],
        ):
            packets += arrival_packets(db, store, source, saved)
            saved = store.character(account_id, saved["id"], db)
        if (
            source["map_id"] != 1385
            and saved["map_id"] == 1385
            and saved.get("instance_id", 0) == 0
        ):
            from wakfu_server import rii_scenario

            packets.append(rii_scenario.packet(rii_scenario.ENTRY))
            if first_rii_arrival:
                packets.append(rii_scenario.packet(rii_scenario.INTRO))
    return saved, packets
