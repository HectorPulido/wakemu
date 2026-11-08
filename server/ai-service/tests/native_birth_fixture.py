"""Actual accepted-command admission fixture; importing builds no fight."""


def admitted_native_birth():
    from test_rift_native_wave import RiftNativeWaveTests
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.rift_dispatch_combat import finish_accepted_action

    fixture = RiftNativeWaveTests()
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.rift_npc_creation import prepare_wave_npcs
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.combat_qi_fight import (
        prepare_fresh_actor_slots,
        install_fresh_actor_slots,
    )

    npc = prepare_wave_npcs([fixture.monster(-200, 2)])[0]
    pc = Actor(1, 0, (0, 0, 0), 100, 6, 3, 10000, 1, 1, True)
    pc.physical_radius = 0
    cells = {(x, y, 0) for x in range(8) for y in range(8)}
    fight = Fight(7, [pc, npc], cells, {0: {pc.position}, 1: {npc.position}})
    # Unlike the packet-only fixture's 0x100 cells, this arena must really be
    # traversable by the accepted-command placement producer.
    fight.native_qi_snapshot = dict(
        x=0,
        y=0,
        width=8,
        height=8,
        cell_masks=[0] * 64,
    )
    initialize_global_pv_collections(fight, tuple(fight.actors))
    install_fresh_actor_slots(
        fight,
        prepare_fresh_actor_slots(
            fight,
            physical_radii={
                actor.id: actor.physical_radius for actor in fight.actors.values()
            },
        ),
    )
    fight.edges = {
        (cell, (cell[0] + dx, cell[1] + dy, 0))
        for cell in cells
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if (cell[0] + dx, cell[1] + dy, 0) in cells
    }
    fight.rift_wave_state = dict(
        instance_id=9,
        wave=1,
        turn_budget=40,
        wave_actor_ids=[npc.id],
    )
    fight.ready(1)
    fight.apply_damage(pc.id, npc.id, npc.hp)
    fight.rift_monsters = {-200: fixture.monster(-200, 2)}
    fight.rift_wave_state.update(
        catalog=dict(wave_id=3, map_id=1134, type="INFINITE_WAVE", species_refs=[5525]),
        policy=dict(
            enabled=True,
            policy_kind="local_dev_not_official",
            turn_budget=40,
            max_members=4,
            classic_wave_size=1,
            ultimate_wave_size=1,
            starting_wave=1,
            selection="uniform_with_replacement",
            scaling="native_base_grade",
            quest_requirements=False,
            key_requirements=False,
            rewards="callback_only",
        ),
        seed="test",
        actor_id_pool=[-201],
    )
    runtime = RuntimeMessages(fight)
    runtime.clock = lambda: 100
    runtime.turn_deadline = 123
    result = finish_accepted_action(
        fight, runtime, (), initialize_actor=lambda *args: []
    )
    # The accepted-command producer publishes the actual source, including its
    # instance identity; never fill it from a separately fabricated monster.
    return fight, fight.rift_monsters[-201], tuple(result.packets[:2])
