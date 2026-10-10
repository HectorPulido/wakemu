-- Local characters have never had a quest progression engine or imported
-- achievement state. Establish that explicit empty baseline once; do not infer
-- unknown state from missing rows during runtime access authorization.
CREATE TABLE character_achievement_authority (
    character_id bigint PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    snapshot jsonb NOT NULL DEFAULT '{"running":[],"completed":[],"objectives":[]}'::jsonb,
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    provenance text NOT NULL DEFAULT 'local_server_initial_empty',
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(snapshot) = 'object')
);
INSERT INTO character_achievement_authority(character_id)
SELECT id FROM characters ON CONFLICT (character_id) DO NOTHING;
CREATE FUNCTION initialize_character_achievement_authority() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO character_achievement_authority(character_id) VALUES (NEW.id)
    ON CONFLICT (character_id) DO NOTHING;
    RETURN NEW;
END;
$$;
CREATE TRIGGER initialize_character_achievement_authority
AFTER INSERT ON characters FOR EACH ROW
EXECUTE FUNCTION initialize_character_achievement_authority();
