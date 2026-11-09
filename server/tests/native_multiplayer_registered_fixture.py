"""Private registered multiplayer Ready fixture using native server constructors."""
from native_multiplayer_roster_fixture import fixture
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats


def registered_multiplayer_fixture():
    """Exercise actual Registry admissions, per-owner bootstrap and native Ready.

    Leases are private fixture identities. Durable Store admission is not claimed.
    """
    import struct
    from wakfu_server.combat_shared import Registry, Session, Transition
    from wakfu_server.combat_session_adapter import CombatSessionAdapter
    from wakfu_server.combat_heroes import player_actor
    from wakfu_server.combat_bootstrap import player_payload
    from wakfu_server.combat_actor import actor_effects, actual_monster_actor_stats
    from wakfu_server.combat_ready import prepare_ready
    from wakfu_server.combat_server_spell import prepare_server_initialization
    from wakfu_server.spells import default_deck

    runtime, characters, monsters, decks, excluded, description = fixture(
        player_count=3,
        owner_accounts=(9001,) * 3,
        monster_references=(5525,) * 7,
        ready=False,
    )
    sessions = [
        Session(account, actor, "private-" + str(account), 1134, 0)
        for account, actor in ((9001, 7001), (9002, 7004), (9003, 7005))
    ]
    registry = Registry(lambda candidate: candidate in sessions)

    def payload(fight, actor, owner):
        if actor.controlled:
            return player_payload(characters[actor.id], actor, fight.id, wp=6)
        source = monsters[actor.id]
        return (
            actual_monster_actor_stats(
                source,
                actor,
                fight.id,
                wp_current=source["wp"],
                wp_maximum=source["wp"],
                fight=fight,
            ),
            actor_effects(),
        )

    context = dict(
        description.join_context,
        actor_payload=payload,
        frozen_company_members=(7001, 7002, 7003, 7004, 7005),
    )
    shared = registry.register(runtime.fight, sessions[0], join_context=context)
    placement = set(description.arena["placement_cells"][0])
    occupied = {actor.position for actor in shared.fight.actors.values()}
    bootstrap = {}
    for session in sessions[1:]:
        position = sorted(placement - occupied)[0]
        occupied.add(position)
        character = dict(
            characters[7001],
            id=session.character_id,
            account_id=session.account_id,
            x=position[0],
            y=position[1],
            z=position[2],
        )
        characters[session.character_id] = character
        decks[session.character_id] = default_deck(character)
        excluded[session.character_id] = frozenset()
        actor = player_actor(character, 0)
        registry.join(
            session,
            struct.pack(">qB", 7001, 0),
            actor,
            actor_payload=payload,
            bootstrap_packets=CombatSessionAdapter.placement_bootstrap,
        )
        bootstrap[session.account_id] = [
            op
            for batch in registry.drain(shared.fight.id, session)
            for op, _ in batch.packets
        ]
    provider = OwnedExpirationFactory(
        characters=characters,
        monsters=monsters,
        decks=decks,
        actor_id=7001,
        area_callbacks=True,
    )
    serializer = NativeStats(
        characters=characters, monsters=monsters, fight_id=shared.fight.id
    )

    def initialize(preview, action_id):
        packets = []
        for index, character in enumerate(characters.values()):
            preview, owned = prepare_server_initialization(
                character,
                monsters,
                preview,
                character["account_id"],
                decks[character["id"]],
                action_id=action_id,
                fight_start=(index == len(characters) - 1),
                player_characters=characters,
                deck_blobs=decks,
            )
            packets.extend(owned)
        return preview, packets

    for session in sessions:

        def operation(fight, native):
            prepared, native, packets = prepare_ready(
                fight,
                session.account_id,
                True,
                initialize=initialize,
                stats_serializer=serializer,
                effects_serializer=actor_effects,
                runtime_stats_serializer=serializer,
                turn_start_provider=provider.turn_start,
                turn_end_provider=provider.turn_end,
                expiration_runtime_factory=provider,
            )
            return Transition(prepared, native, packets)

        registry.execute(
            shared.fight.id,
            session,
            session.character_id,
            operation,
            require_turn=False,
        )
    assert len(shared.fight.actors) == 12
    assert shared.fight.phase == "active"
    assert len(shared.participants) == 3
    assert shared.runtime.fight is shared.fight
    assert shared.fight.native_start_event_delivered
    return registry, shared, sessions, characters, monsters, decks, excluded, bootstrap
