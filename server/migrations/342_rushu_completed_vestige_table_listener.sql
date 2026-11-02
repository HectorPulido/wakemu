-- Renew completed vestige markers through their actual retained native root.
-- Global1003 is only published at combat opening by the generic lifecycle;
-- root325771 requires table >=6, so it needs the reviewed encounter clock.
-- Native325772 still requires the corresponding earned level99 vestige state.
INSERT INTO encounter_table_listener_versions
    (policy,authority,map_id,monster_references,catalog_revision,boss_reference,
     boss_constructor_state,owner_reference,owner_constructor_state,
     effect_reference,event_id,channel,timing)
VALUES
    ('wakemu-rushu-completed-vestige-table-listener-v1',
     'wakemu-reconstructed-owned-table-publication-native7000-325771-325772-325773',
     1332,ARRAY[5306],
     '0793e23d94afe346c4ae25532417355f3dd5e290da1b0588189523b31ae5cbde',
     5306,7000,5306,7000,325771,1003,61,'owned_boss_table_start');
INSERT INTO encounter_table_listener_active(map_id,monster_references,policy)
VALUES (1332,ARRAY[5306],'wakemu-rushu-completed-vestige-table-listener-v1');
