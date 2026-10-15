-- Expose only the fixed Astrub return command; preserve existing privileges.
INSERT INTO settings(name,value)
VALUES ('player_allowed_commands','["!ayuda","!pos","!astrub"]'::jsonb)
ON CONFLICT(name) DO UPDATE
SET value = CASE
    WHEN jsonb_typeof(settings.value) = 'array'
         AND NOT settings.value @> '["!astrub"]'::jsonb
    THEN settings.value || '["!astrub"]'::jsonb
    ELSE settings.value
END;
