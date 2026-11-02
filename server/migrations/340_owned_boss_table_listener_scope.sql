-- Self-owned constructors may renew independently of a dungeon's scaled roster.
-- Existing exact-roster policies and already frozen fights remain unchanged.
-- Fresh installs apply the entire migration prefix in one transaction.
SET CONSTRAINTS encounter_table_version_callbacks_complete,
    encounter_table_callback_inventory_complete IMMEDIATE;
ALTER TABLE encounter_table_listener_versions ADD COLUMN roster_scope TEXT
    NOT NULL DEFAULT 'exact' CHECK (roster_scope IN ('exact', 'owned_boss'));
ALTER TABLE encounter_table_listener_versions ADD CONSTRAINT
    encounter_table_listener_owned_boss_scope CHECK (
        roster_scope = 'exact' OR (
            monster_references = ARRAY[boss_reference]
            AND owner_reference = boss_reference
            AND owner_constructor_state = boss_constructor_state
        )
    );
SET CONSTRAINTS encounter_table_version_callbacks_complete,
    encounter_table_callback_inventory_complete DEFERRED;

-- Native state2334/root316157 removes old own glyphs1603/623, creates two new
-- transformation tokens and restores2324. The per-table producer is explicit
-- Wakemu authoring, supported by the original root and WakfuStrat 2024-07-21.
-- Profile2778 and paid spell4019 continue to use the ordinary native handlers.
INSERT INTO encounter_table_listener_versions
    (policy,authority,map_id,monster_references,catalog_revision,boss_reference,
     boss_constructor_state,owner_reference,owner_constructor_state,
     effect_reference,event_id,channel,timing,roster_scope)
VALUES
    ('wakemu-wild-gobball-owned-totems-table-listener-v2',
     'wakemu-reviewed-each-table-totem-renewal-native2334-316157-and-WakfuStrat20240721',
     712,ARRAY[2768],
     '0793e23d94afe346c4ae25532417355f3dd5e290da1b0588189523b31ae5cbde',
     2768,2334,2768,2334,316157,1003,61,'owned_boss_table_start','owned_boss');
INSERT INTO encounter_table_listener_active(map_id,monster_references,policy)
VALUES (712,ARRAY[2768],'wakemu-wild-gobball-owned-totems-table-listener-v2');
