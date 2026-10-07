-- Keep creature identities outside the existing random 62-bit namespace.
-- Sequence values are never reused after rollback or restart.
CREATE SEQUENCE monster_entity_uid AS bigint
    MINVALUE 4611686018427387905
    MAXVALUE 9223372036854775807
    START WITH 4611686018427387905
    NO CYCLE;

INSERT INTO settings(name,value) VALUES
    ('monster_reproduction', '{"interval_ms":60000,"birth_probability":0.05,"birth_stage_decay":0.5,"new_group_probability":0.5,"max_members":8,"max_zone_members":128,"max_zone_groups":32}'::jsonb);
