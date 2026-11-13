"""Settle mission facts in the same transaction as native travel."""


def transition(
    store, account_id, generation, source, route, *, native_zaap, incarnam_exit=False
):
    """Move an owned character and apply any qualified zone or Zaap events.

    ``route`` has already passed the transport resolver and its authorization.
    A rejected transition or failed mission settlement rolls back both together.
    Returned packets are sent only after the destination scene is published.
    """
    from wakfu_server.achievements import zone_missions

    with store.connection() as db:
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
        saved = store.transition_map_in_transaction(
            db, account_id, generation, source["id"], source, route["destination"]
        )
        packets = zone_missions.enter_rii(
            db, store, saved, previous_map=source["map_id"]
        )
        if source["map_id"] == 1465 and saved["map_id"] == 1361:
            from wakfu_server.achievements import incarnam_tutorial

            packets += incarnam_tutorial.enter(
                db, store, saved, previous_map=source["map_id"]
            )
        first_rii_arrival = bool(packets)
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
        if native_zaap:
            from wakfu_server.achievements import transport_missions

            packets += transport_missions.on_native_transport(
                db, store, source, saved, route
            )
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
