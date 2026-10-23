"""Verified Haven World identity carried into one ordinary combat instance.

The monster source records remain the exact ``monsters.owned_instance``
records. This authority is attached to the server-owned Fight/Actor objects and
is derived only from the selected PC's projected, SQL-backed world position.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class HavenWorldCombatContext:
    fight_id: int
    owner_character_id: int
    map_id: int
    instance_id: int
    native_world_id: int
    position_authority: object

    def __post_init__(self):
        from wakfu_server.guild_haven_world import world_identity

        if (
            type(self.fight_id) is not int
            or self.fight_id <= 0
            or type(self.owner_character_id) is not int
            or self.owner_character_id <= 0
            or type(self.map_id) is not int
            or self.map_id <= 0
            or type(self.instance_id) is not int
            or self.instance_id <= 0
            or type(self.native_world_id) is not int
            or self.native_world_id >= 0
        ):
            raise ValueError("Invalid verified Haven World combat identity")
        projection = dict(
            map_id=self.map_id,
            instance_id=self.instance_id,
            native_world_id=self.native_world_id,
            _native_haven_world_position=self.position_authority,
        )
        if world_identity(projection) != self.native_world_id:
            raise ValueError("Haven World combat identity lost its SQL authority")


def placement_context(character, members, *, fight_id):
    """Capture the selected PC's verified private scope for the exact placement.

    Normal positive-map fights return ``None`` and retain their existing NPC
    map identity. A private context cannot be inferred from a positive instance
    or client-provided fields; it must carry the projected Haven World proof.
    """
    from wakfu_server.guild_haven_world import world_identity

    if not isinstance(character, dict):
        raise ValueError("Missing selected owned PC for Haven World placement")
    identity = world_identity(character)
    if "native_world_id" not in character:
        if "_native_haven_world_position" in character:
            raise ValueError("Incomplete projected Haven World PC context")
        return None
    authority = character.get("_native_haven_world_position")
    context = HavenWorldCombatContext(
        fight_id=fight_id,
        owner_character_id=character.get("id"),
        map_id=character.get("map_id"),
        instance_id=character.get("instance_id"),
        native_world_id=identity,
        position_authority=authority,
    )
    members = tuple(members)
    if not members or any(
        not isinstance(member, dict)
        or member.get("map_id") != context.map_id
        or member.get("instance_id") != context.instance_id
        for member in members
    ):
        raise ValueError("Haven World NPC roster differs from the selected PC scope")
    if len({member.get("id") for member in members}) != len(members):
        raise ValueError("Duplicate NPC identity in Haven World placement")
    return context


def bind_placement(fight, context):
    """Attach the verified scope to live ordinary NPC actors, never source rows."""
    if context is None:
        return None
    from .combat_encounter_roles import assigned_roles

    roles = assigned_roles(fight)
    if (
        not isinstance(context, HavenWorldCombatContext)
        or fight.id != context.fight_id
        or context.owner_character_id not in fight.actors
        or fight.actors[context.owner_character_id].team != roles.player_team
    ):
        raise ValueError("Haven World combat scope does not own this Fight")
    for actor in fight.actors.values():
        if actor.team == roles.player_team:
            continue
        actor.native_haven_world_combat_context = context
    fight.native_haven_world_combat_context = context
    return context


def validate_placement(fight, characters, monsters):
    """Recheck the immutable scope at the all-actor snapshot/Ready boundary."""
    context = getattr(fight, "native_haven_world_combat_context", None)
    if not isinstance(characters, dict) or not isinstance(monsters, dict):
        raise ValueError("Missing Haven World snapshot source maps")
    if context is None:
        if monsters and any(
            "native_world_id" in character for character in characters.values()
        ):
            raise ValueError("Private Haven World PC lacks combat NPC identity binding")
        return
    from wakfu_server.guild_haven_world import world_identity

    owner = characters.get(context.owner_character_id)
    if (
        not isinstance(context, HavenWorldCombatContext)
        or fight.id != context.fight_id
        or owner is None
        or world_identity(owner) != context.native_world_id
        or owner.get("map_id") != context.map_id
        or owner.get("instance_id") != context.instance_id
        or set(monsters) != set(fight.actors) - set(characters)
    ):
        raise ValueError("Haven World combat source changed before snapshot")
    for identity, monster in monsters.items():
        actor = fight.actors.get(identity)
        if (
            actor is None
            or getattr(actor, "native_haven_world_combat_context", None) is not context
            or monster.get("id") != identity
            or monster.get("map_id") != context.map_id
            or monster.get("instance_id") != context.instance_id
        ):
            raise ValueError("Haven World NPC source lost its verified combat scope")


def position_identity(source, *, context=None, world_actor=None, fight=None):
    """Resolve native arM from a PC projection or its bound NPC combat scope."""
    from wakfu_server.guild_haven_world import world_identity

    if context is None and world_actor is not None:
        context = getattr(world_actor, "native_haven_world_combat_context", None)
    if context is None:
        return world_identity(source)
    if not isinstance(context, HavenWorldCombatContext):
        raise ValueError("Untrusted Haven World combat identity")
    if (
        not isinstance(source, dict)
        or source.get("map_id") != context.map_id
        or source.get("instance_id") != context.instance_id
        or type(source.get("id")) is not int
    ):
        raise ValueError("NPC source differs from its verified Haven World scope")
    if world_actor is not None and (
        source["id"] != world_actor.id
        or getattr(world_actor, "native_haven_world_combat_context", None)
        is not context
    ):
        raise ValueError("NPC Actor is not bound to the Haven World source")
    if fight is not None and (
        fight.id != context.fight_id
        or getattr(fight, "native_haven_world_combat_context", None) is not context
        or world_actor is None
        or fight.actors.get(world_actor.id) is not world_actor
    ):
        raise ValueError("NPC arM context belongs to a different Fight")
    return context.native_world_id
