"""Initialize frozen dungeon effects before registering a placement fight."""


def initialize(db, fight, monsters):
    from . import dungeon_combat_scaling, dungeon_scaling_catalog

    catalog = dungeon_scaling_catalog.load(db)
    if catalog is None:
        if (
            db.execute(
                "SELECT 1 FROM dungeon_encounter_difficulties WHERE fight_id=%s",
                (fight.id,),
            ).fetchone()
            is not None
        ):
            raise ValueError("Frozen dungeon encounter has no scaling catalog")
        return fight, None

    def runtime_factory(preview, identity):
        from wakfu_server.combat_npc_initialization import _runtime

        factory, _ = _runtime(monsters, identity)
        dispatcher, _ = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        return dispatcher

    return dungeon_combat_scaling.initialize(
        db, fight, monsters, catalog=catalog, runtime_factory=runtime_factory
    )
