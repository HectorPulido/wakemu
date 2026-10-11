-- Coalesced transactional wakeups; producers never wait for an ecology HTTP call.
CREATE TABLE ecology_dirty_scopes (
    map_id bigint NOT NULL,
    instance_id bigint NOT NULL,
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    processed_revision bigint NOT NULL DEFAULT 0 CHECK (processed_revision >= 0),
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (map_id,instance_id)
);
CREATE INDEX ecology_dirty_pending ON ecology_dirty_scopes(updated_at)
    WHERE revision > processed_revision;

CREATE TABLE ecology_service_proposals (
    id text PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 128),
    domain text NOT NULL CHECK (domain IN ('plants','mobs','weather','population')),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
    world_epoch text NOT NULL CHECK (length(world_epoch) BETWEEN 1 AND 128),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivered_at timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    last_error_code text
);
CREATE INDEX ecology_proposals_pending ON ecology_service_proposals(created_at,id)
    WHERE delivered_at IS NULL;

CREATE FUNCTION ecology_mark_scope(p_map bigint,p_instance bigint) RETURNS void
LANGUAGE sql AS $$
    INSERT INTO ecology_dirty_scopes(map_id,instance_id) VALUES(p_map,p_instance)
    ON CONFLICT(map_id,instance_id) DO UPDATE
        SET revision=ecology_dirty_scopes.revision+1,updated_at=CURRENT_TIMESTAMP;
$$;

CREATE FUNCTION ecology_scope_changed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        PERFORM ecology_mark_scope(OLD.map_id,OLD.instance_id);
    END IF;
    IF TG_OP <> 'DELETE' THEN
        IF TG_OP='INSERT' OR (NEW.map_id,NEW.instance_id) IS DISTINCT FROM (OLD.map_id,OLD.instance_id) THEN
            PERFORM ecology_mark_scope(NEW.map_id,NEW.instance_id);
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER ecology_plants_dirty AFTER INSERT OR UPDATE OR DELETE ON planted_resources
    FOR EACH ROW EXECUTE FUNCTION ecology_scope_changed();
CREATE TRIGGER ecology_groups_dirty AFTER INSERT OR UPDATE OR DELETE ON combat_groups
    FOR EACH ROW EXECUTE FUNCTION ecology_scope_changed();
CREATE TRIGGER ecology_weather_dirty AFTER INSERT OR UPDATE OR DELETE ON territory_weather
    FOR EACH ROW EXECUTE FUNCTION ecology_scope_changed();

CREATE FUNCTION ecology_harvest_changed() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE resource_id bigint;
BEGIN
    IF TG_OP='DELETE' THEN resource_id:=OLD.resource_uid;
    ELSE resource_id:=NEW.resource_uid; END IF;
    PERFORM ecology_mark_scope(map_id,instance_id) FROM planted_resources
        WHERE resource_uid=resource_id;
    RETURN NULL;
END;
$$;
CREATE TRIGGER ecology_harvest_dirty AFTER INSERT OR UPDATE OR DELETE ON resource_harvest_occupations
    FOR EACH ROW EXECUTE FUNCTION ecology_harvest_changed();

CREATE FUNCTION ecology_policy_changed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM ecology_mark_scope(-1,-1);
    RETURN NULL;
END;
$$;
CREATE TRIGGER ecology_settings_dirty AFTER INSERT OR UPDATE OR DELETE ON settings
    FOR EACH STATEMENT EXECUTE FUNCTION ecology_policy_changed();
SELECT ecology_mark_scope(-1,-1);
