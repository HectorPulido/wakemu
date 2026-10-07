-- Local maturation policy. Levels/classes come from native exported metadata.
INSERT INTO settings(name,value) VALUES ('monster_maturation',
    '{"interval_ms":60000,"base_probability":0.25,"stage_decay":0.5,"boss_probability":0.00001}'::jsonb);
CREATE TABLE monster_maturation_timers (
    map_id integer NOT NULL,
    instance_id bigint NOT NULL,
    monster_id bigint NOT NULL,
    reference integer NOT NULL,
    remaining_ms bigint NOT NULL CHECK (remaining_ms>=0),
    last_active_ms bigint,
    observer_generation text,
    due boolean NOT NULL DEFAULT false,
    cycle bigint NOT NULL DEFAULT 0 CHECK (cycle>=0),
    PRIMARY KEY(map_id,instance_id,monster_id),
    FOREIGN KEY(map_id,instance_id,monster_id)
        REFERENCES combat_group_members(map_id,instance_id,monster_id) ON DELETE CASCADE
);
