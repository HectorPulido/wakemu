-- Native boss opening applies these counters to real players. Their original
-- global1003 roots require table>=2 and otherwise never receive a later event.
CREATE TABLE encounter_player_table_listeners (
    policy text PRIMARY KEY CHECK (length(policy)>0),
    authority text NOT NULL CHECK (length(authority)>0),
    map_id integer NOT NULL,
    boss_reference integer NOT NULL CHECK (boss_reference>0),
    boss_constructor_state integer NOT NULL CHECK (boss_constructor_state>0),
    installer_reference integer NOT NULL CHECK (installer_reference>0),
    player_state integer NOT NULL CHECK (player_state>0),
    effect_reference integer NOT NULL CHECK (effect_reference>0),
    catalog_revision text NOT NULL CHECK (length(catalog_revision)=64),
    UNIQUE(map_id,boss_reference,player_state,effect_reference)
);
CREATE TRIGGER encounter_player_table_listeners_immutable
    BEFORE UPDATE OR DELETE ON encounter_player_table_listeners
    FOR EACH ROW EXECUTE FUNCTION forbid_encounter_role_version_mutation();
CREATE TRIGGER encounter_player_table_listeners_no_truncate
    BEFORE TRUNCATE ON encounter_player_table_listeners
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_encounter_role_version_mutation();
INSERT INTO encounter_player_table_listeners VALUES
    ('wakemu-nogord-player-time-counter-table-v1',
     'wakemu-reviewed-round-publication-original4509-186439-player4510-186113',
     1092,3433,4509,186439,4510,186113,
     '0793e23d94afe346c4ae25532417355f3dd5e290da1b0588189523b31ae5cbde'),
    ('wakemu-shadow-player-shadow-counter-table-v1',
     'wakemu-reviewed-round-publication-original5649-266405-player5662-266774',
     1229,4770,5649,266405,5662,266774,
     '0793e23d94afe346c4ae25532417355f3dd5e290da1b0588189523b31ae5cbde');
