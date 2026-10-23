"""Refresh exploration food statistics without reconstructing the owned actor."""


def publish(world, generation, character, *, send):
    from wakfu_server.territory_bonuses import world_packet
    from wakfu_server.world_characteristic_publication import packets

    snapshot = world_packet(character)
    # Preserve the existing owned build and native running-effect managers.
    # Format10 has no PUBLIC_CHARACTERISTICS and must not follow this refresh.
    for opcode, body in packets(character, snapshot):
        send(opcode, body)
    # Keep the world registry and observers current. Build selection is private
    # to the owner and is never broadcast to another account.
    world.update(generation, character, *snapshot, include_sender=False)


def synchronize_and_publish(
    store,
    account_id,
    generation,
    character,
    *,
    in_combat,
    allocate_action,
    send,
    broadcast_main,
    publish_main
):
    """Publish committed company clock changes without rebuilding owned actors."""
    from wakfu_server.consumable_buff_wire import delta
    from wakfu_server.consumable_world_lifecycle import synchronize
    from wakfu_server.territory_bonuses import world_packets

    company_updates = []
    updated = synchronize(
        store,
        account_id,
        generation,
        character,
        in_combat=in_combat,
        company_updates=company_updates,
    )
    if in_combat:
        return updated
    main_packets = delta(character, updated, allocate_action=allocate_action)
    if main_packets:
        for opcode, body in main_packets:
            broadcast_main(opcode, body)
        publish_main(updated)
    # Active heroes are loaded only by their company's owner. They have no
    # separate World.players entry and must not be broadcast as scene actors.
    for previous, current in company_updates:
        for opcode, body in delta(previous, current, allocate_action=allocate_action):
            send(opcode, body)
        for opcode, body in world_packets(current):
            send(opcode, body)
    return updated
