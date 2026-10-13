"""Native bPi NPC branch: share the source bje's blj visual prototype.

bje.dsC reads blj.dvT, including for a bje with an ijZ copy override. Unlike
bjo, this branch never synthesizes a blp from connected-player appearance.
The prototype handle keeps nullable blp/category values unresolved: the client
already owns the same prototype and performs bje.ac/bPi when reading creation.
"""
from .combat_runtime_adapter import NativeActorAuthority
from .combat_character_copy_equipment import copied_equipment_source


def npc_visual_copy_plan(metadata, source_actor_id):
    if (
        not isinstance(metadata, NativeActorAuthority)
        or metadata.is_player is not False
        or metadata.native_actor_type != 1
        or type(metadata.native_npc_prototype_ref) is not int
        or metadata.native_npc_prototype_ref != metadata.breed_id
    ):
        raise ValueError("Missing actual bje visual prototype authority")
    from wakfu_server.monsters import reference

    prototype = reference(metadata.native_npc_prototype_ref)
    model = prototype.get("sprite_id")
    if type(model) is not int or not -(1 << 31) <= model < (1 << 31):
        raise ValueError("Missing native blj.aHf visual model")
    return dict(
        producer="bje.ac.bPi.bje_prototype.v1",
        source_actor_id=source_actor_id,
        model=model,
        # These are references to native prototype members, not fabricated
        # empty component values or copied player wire bytes. Null remains
        # native-null when the corresponding prototype member is null.
        prototype_visual=dict(
            producer="bje.dsC.blj.dvT.shared_reference",
            reference=metadata.native_npc_prototype_ref,
        ),
        prototype_categories=dict(
            producer="bje.don.blj.don.shared_reference",
            reference=metadata.native_npc_prototype_ref,
        ),
        equipment=copied_equipment_source(metadata, source_actor_id),
        source="bPi.a.bje.bwX_Dt_Di.dsC_blp.don.PJ",
    )
