-- Move immutable dungeon versions and active selections out of generic settings.
CREATE TABLE IF NOT EXISTS dungeon_runtime_configurations (
    route_key text NOT NULL CHECK (length(route_key) > 0),
    policy_version integer NOT NULL CHECK (policy_version > 0),
    configuration jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (route_key, policy_version),
    CHECK (jsonb_typeof(configuration) = 'object'),
    CHECK (configuration #>> '{route,key}' IS NOT NULL
        AND configuration #>> '{route,key}' = route_key),
    CHECK (jsonb_typeof(configuration->'version') = 'number'
        AND configuration->'version' IS NOT NULL
        AND configuration->'version' = to_jsonb(policy_version))
);

CREATE TABLE IF NOT EXISTS dungeon_runtime_active_configurations (
    route_key text PRIMARY KEY,
    policy_version integer NOT NULL,
    FOREIGN KEY (route_key, policy_version)
        REFERENCES dungeon_runtime_configurations(route_key, policy_version)
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM settings
        WHERE starts_with(name, 'dungeon_runtime_config:')
          AND name !~ '^dungeon_runtime_config:(.+):v([1-9][0-9]*)$'
    ) THEN
        RAISE EXCEPTION 'Malformed legacy dungeon configuration key';
    END IF;
    IF EXISTS (
        SELECT 1 FROM settings
        WHERE starts_with(name, 'dungeon_runtime_active:')
          AND (length(substring(name FROM length('dungeon_runtime_active:') + 1)) = 0
            OR jsonb_typeof(value->'version') IS DISTINCT FROM 'number'
            OR (value->>'version') !~ '^[1-9][0-9]*$'
            OR (value ? 'key' AND value->>'key' IS DISTINCT FROM
                'dungeon_runtime_config:' || substring(name FROM length('dungeon_runtime_active:') + 1)
                || ':v' || (value->>'version')))
    ) THEN
        RAISE EXCEPTION 'Malformed legacy dungeon active selection';
    END IF;
END $$;

INSERT INTO dungeon_runtime_configurations(route_key, policy_version, configuration)
SELECT matched.parts[1], matched.parts[2]::integer, settings.value
FROM settings
CROSS JOIN LATERAL regexp_match(settings.name,
    '^dungeon_runtime_config:(.+):v([1-9][0-9]*)$') AS matched(parts)
WHERE starts_with(settings.name, 'dungeon_runtime_config:')
ON CONFLICT (route_key, policy_version) DO NOTHING;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM settings
        CROSS JOIN LATERAL regexp_match(settings.name,
            '^dungeon_runtime_config:(.+):v([1-9][0-9]*)$') AS matched(parts)
        JOIN dungeon_runtime_configurations AS stored
          ON stored.route_key = matched.parts[1]
         AND stored.policy_version = matched.parts[2]::integer
        WHERE starts_with(settings.name, 'dungeon_runtime_config:')
          AND stored.configuration IS DISTINCT FROM settings.value
    ) THEN
        RAISE EXCEPTION 'Legacy dungeon version conflicts with immutable configuration';
    END IF;
END $$;

INSERT INTO dungeon_runtime_active_configurations(route_key, policy_version)
SELECT substring(name FROM length('dungeon_runtime_active:') + 1),
       (value->>'version')::integer
FROM settings WHERE starts_with(name, 'dungeon_runtime_active:')
ON CONFLICT (route_key) DO NOTHING;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM settings
        JOIN dungeon_runtime_active_configurations AS selected
          ON selected.route_key = substring(settings.name FROM length('dungeon_runtime_active:') + 1)
        WHERE starts_with(settings.name, 'dungeon_runtime_active:')
          AND selected.policy_version <> (settings.value->>'version')::integer
    ) THEN
        RAISE EXCEPTION 'Legacy dungeon active selection conflicts with stored selection';
    END IF;
END $$;

-- Only remove legacy rows after every version and pointer has been verified.
DELETE FROM settings WHERE starts_with(name, 'dungeon_runtime_config:')
    OR starts_with(name, 'dungeon_runtime_active:');

CREATE OR REPLACE FUNCTION preserve_dungeon_runtime_configuration()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Dungeon configuration versions are immutable';
    END IF;
    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Dungeon configuration versions are immutable';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS dungeon_runtime_configuration_immutable
    ON dungeon_runtime_configurations;
CREATE TRIGGER dungeon_runtime_configuration_immutable
    BEFORE UPDATE OR DELETE ON dungeon_runtime_configurations
    FOR EACH ROW EXECUTE FUNCTION preserve_dungeon_runtime_configuration();
