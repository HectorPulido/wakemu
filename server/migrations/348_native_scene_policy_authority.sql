-- PRIVATE PROPOSAL: reserved migration348. Do not apply until B2 and the next image are ready.
-- Authored gameplay authority is normalized. JSONB below holds only original native
-- descriptors/effects/source provenance; existing receipt snapshots remain unchanged.
CREATE TABLE native_scene_policies (
    policy_id text PRIMARY KEY CHECK (length(policy_id)>0),
    authority text NOT NULL CHECK (length(authority)>0),
    policy_sha256 text NOT NULL CHECK (policy_sha256 ~ '^[0-9a-f]{64}$'),
    published boolean NOT NULL DEFAULT false,
    map_id integer NOT NULL CHECK (map_id>0),
    definition_id integer NOT NULL CHECK (definition_id>0),
    template_id integer NOT NULL CHECK (template_id>0),
    source_id bigint NOT NULL CHECK (source_id>0),
    wire_action integer NOT NULL CHECK (wire_action BETWEEN 0 AND 65535),
    descriptor_id integer NOT NULL CHECK (descriptor_id>0),
    catalog_revision text NOT NULL CHECK (catalog_revision ~ '^[0-9a-f]{64}$'),
    native_group_id integer NOT NULL CHECK (native_group_id>0),
    native_action_id integer NOT NULL CHECK (native_action_id>0),
    native_script_reference integer NOT NULL CHECK (native_script_reference>0),
    native_criterion text NOT NULL CHECK (length(native_criterion)>0),
    price_item_id integer NOT NULL CHECK (price_item_id>0),
    price_quantity integer NOT NULL CHECK (price_quantity>0),
    maximum_members integer NOT NULL CHECK (maximum_members BETWEEN 1 AND 6),
    competitive_ceiling integer CHECK (competitive_ceiling BETWEEN 1 AND 32767),
    profile_mode text NOT NULL CHECK (profile_mode IN ('binary','choices','configured_roster')),
    profile_provenance text,
    compiled_plan_sha256 text CHECK (compiled_plan_sha256 ~ '^[0-9a-f]{64}$'),
    combat_anchor_x integer,
    combat_anchor_y integer,
    combat_anchor_z integer,
    combat_area_provenance text,
    scene_source_uri text,
    native_border_reference integer CHECK (native_border_reference>0),
    environment_enabled boolean NOT NULL DEFAULT false,
    -- NULL preserves legacy133 serialization and formation behavior exactly.
    environment_reserve_spawn_slots boolean,
    environment_area_reference integer CHECK (environment_area_reference>0),
    environment_level integer CHECK (environment_level BETWEEN 0 AND 32767),
    environment_coordinate_authority text,
    environment_map_graphics_sha256 text CHECK (environment_map_graphics_sha256 ~ '^[0-9a-f]{64}$'),
    environment_provenance text,
    environment_source_uri text,
    native_descriptor jsonb NOT NULL CHECK (jsonb_typeof(native_descriptor)='object'),
    native_effects jsonb NOT NULL CHECK (jsonb_typeof(native_effects)='array'),
    source_provenance jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(source_provenance)='object'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((profile_mode='configured_roster')=(compiled_plan_sha256 IS NOT NULL)),
    CHECK ((combat_anchor_x IS NULL)=(combat_anchor_y IS NULL)
       AND (combat_anchor_x IS NULL)=(combat_anchor_z IS NULL)),
    CHECK (NOT environment_enabled OR environment_coordinate_authority IS NOT NULL),
    CHECK (environment_reserve_spawn_slots IS NULL OR environment_enabled)
);
CREATE INDEX native_scene_policy_sources ON native_scene_policies(map_id,source_id) WHERE published;

CREATE TABLE native_scene_policy_objects (
    policy_id text NOT NULL REFERENCES native_scene_policies,
    object_role text NOT NULL CHECK (object_role IN ('gate','evidence')),
    ordinal integer NOT NULL CHECK (ordinal>0),
    object_id bigint NOT NULL CHECK (object_id>0),
    native_type text NOT NULL CHECK (length(native_type)>0),
    x integer NOT NULL, y integer NOT NULL, z integer NOT NULL,
    payload_hex text NOT NULL CHECK (payload_hex ~ '^([0-9a-f]{2})+$'),
    PRIMARY KEY (policy_id,object_role,ordinal),
    UNIQUE (policy_id,object_role,object_id)
);
CREATE TABLE native_scene_policy_approaches (
    policy_id text NOT NULL REFERENCES native_scene_policies,
    ordinal integer NOT NULL CHECK (ordinal>0),
    x integer NOT NULL, y integer NOT NULL, z integer NOT NULL,
    PRIMARY KEY (policy_id,ordinal), UNIQUE (policy_id,x,y,z)
);
CREATE TABLE native_scene_policy_combat_cells (
    policy_id text NOT NULL REFERENCES native_scene_policies,
    ordinal integer NOT NULL CHECK (ordinal>0),
    x integer NOT NULL, y integer NOT NULL, z integer NOT NULL,
    PRIMARY KEY (policy_id,ordinal), UNIQUE (policy_id,x,y,z)
);
CREATE TABLE native_scene_profile_states (
    policy_id text NOT NULL REFERENCES native_scene_policies,
    ordinal integer NOT NULL CHECK (ordinal>0),
    state_id integer NOT NULL CHECK (state_id>0),
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (policy_id,ordinal), UNIQUE (policy_id,state_id)
);
CREATE TABLE native_scene_profile_state_levels (
    policy_id text NOT NULL,
    state_ordinal integer NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal>0),
    -- NULL is the explicit native alternative that installs no state.
    level integer CHECK (level BETWEEN 1 AND 32767),
    PRIMARY KEY (policy_id,state_ordinal,ordinal),
    FOREIGN KEY (policy_id,state_ordinal) REFERENCES native_scene_profile_states(policy_id,ordinal)
);
CREATE UNIQUE INDEX native_scene_profile_distinct_levels ON native_scene_profile_state_levels
    (policy_id,state_ordinal,level) WHERE level IS NOT NULL;
CREATE UNIQUE INDEX native_scene_profile_single_omission ON native_scene_profile_state_levels
    (policy_id,state_ordinal) WHERE level IS NULL;
CREATE TABLE native_scene_profile_targets (
    policy_id text NOT NULL REFERENCES native_scene_policies,
    ordinal integer NOT NULL CHECK (ordinal>0),
    reference_id integer NOT NULL CHECK (reference_id>0),
    PRIMARY KEY (policy_id,ordinal), UNIQUE (policy_id,reference_id)
);
CREATE TABLE native_scene_environment_placements (
    policy_id text NOT NULL REFERENCES native_scene_policies,
    ordinal integer NOT NULL CHECK (ordinal>0),
    x integer NOT NULL, y integer NOT NULL, z integer NOT NULL,
    -- NULL preserves legacy inheritance; non-NULL is a literal per-slot native area.
    area_reference integer CHECK (area_reference>0),
    level integer CHECK (level BETWEEN 0 AND 32767),
    original_graphic integer CHECK (original_graphic>0),
    PRIMARY KEY (policy_id,ordinal)
);

-- The special outer admission is another normalized child of its paid scene.
-- Its native route identities are literal; there is no JSON rule extension.
CREATE TABLE native_scene_admission_policies (
    policy_id text PRIMARY KEY REFERENCES native_scene_policies,
    admission_policy_id text NOT NULL UNIQUE CHECK (length(admission_policy_id)>0),
    admission_sha256 text NOT NULL CHECK (admission_sha256 ~ '^[0-9a-f]{64}$'),
    route_key text NOT NULL CHECK (length(route_key)>0),
    authority text NOT NULL CHECK (length(authority)>0),
    entry_map_id integer NOT NULL CHECK (entry_map_id>0),
    entry_object_id bigint NOT NULL CHECK (entry_object_id>0),
    destination_id integer NOT NULL CHECK (destination_id>0),
    minimum_configuration_version integer NOT NULL CHECK (minimum_configuration_version>0),
    provenance text NOT NULL CHECK (length(provenance)>0)
);

CREATE FUNCTION native_scene_policy_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE identity text; frozen boolean;
BEGIN
    IF TG_TABLE_NAME='native_scene_policies' THEN
        IF TG_OP='INSERT' AND NEW.published THEN
            RAISE EXCEPTION 'Publish a native scene only after its normalized children are complete';
        ELSIF TG_OP IN ('UPDATE','DELETE') AND OLD.published THEN
            RAISE EXCEPTION 'Published native scene policies are immutable; create a new policy identity';
        END IF;
        IF TG_OP='UPDATE' AND NEW.published THEN
            IF NOT EXISTS (SELECT 1 FROM native_scene_policy_approaches WHERE policy_id=NEW.policy_id)
               OR NOT EXISTS (SELECT 1 FROM native_scene_policy_objects WHERE policy_id=NEW.policy_id AND object_id=NEW.source_id)
               OR (NEW.combat_anchor_x IS NOT NULL AND NOT EXISTS (
                 SELECT 1 FROM native_scene_policy_combat_cells WHERE policy_id=NEW.policy_id
                 AND (x,y,z)=(NEW.combat_anchor_x,NEW.combat_anchor_y,NEW.combat_anchor_z)))
               OR (NEW.environment_enabled AND NOT EXISTS (
                 SELECT 1 FROM native_scene_environment_placements WHERE policy_id=NEW.policy_id)) THEN
                RAISE EXCEPTION 'Native scene publication lacks its source, approach or declared terrain';
            END IF;
            IF NEW.environment_enabled AND EXISTS (
                SELECT 1 FROM native_scene_environment_placements WHERE policy_id=NEW.policy_id
                AND coalesce(area_reference,NEW.environment_area_reference) IS NULL) THEN
                RAISE EXCEPTION 'Native scene environmental placement lacks its literal native area';
            END IF;
            IF NEW.profile_mode<>'configured_roster' AND (
                NOT EXISTS (SELECT 1 FROM native_scene_profile_targets WHERE policy_id=NEW.policy_id)
                OR NOT EXISTS (SELECT 1 FROM native_scene_profile_states WHERE policy_id=NEW.policy_id)
                OR EXISTS (SELECT 1 FROM native_scene_profile_states s WHERE s.policy_id=NEW.policy_id
                  AND NOT EXISTS (SELECT 1 FROM native_scene_profile_state_levels l
                    WHERE l.policy_id=s.policy_id AND l.state_ordinal=s.ordinal AND l.level IS NOT NULL))) THEN
                RAISE EXCEPTION 'Native scene publication lacks its typed state alternatives or recipients';
            END IF;
            IF NEW.profile_mode='binary' AND EXISTS (
                SELECT 1 FROM native_scene_profile_states s WHERE s.policy_id=NEW.policy_id
                AND (SELECT array_agg(l.level ORDER BY l.ordinal) FROM native_scene_profile_state_levels l
                  WHERE l.policy_id=s.policy_id AND l.state_ordinal=s.ordinal) IS DISTINCT FROM ARRAY[1,2]) THEN
                RAISE EXCEPTION 'Legacy binary scene alternatives must preserve native levels one and two';
            END IF;
        END IF;
    ELSE
        identity := CASE WHEN TG_OP='DELETE' THEN OLD.policy_id ELSE NEW.policy_id END;
        SELECT published INTO frozen FROM native_scene_policies WHERE policy_id=identity FOR SHARE;
        IF frozen THEN RAISE EXCEPTION 'Published native scene children are immutable'; END IF;
        IF TG_OP='UPDATE' AND OLD.policy_id<>NEW.policy_id THEN
            SELECT published INTO frozen FROM native_scene_policies WHERE policy_id=OLD.policy_id FOR SHARE;
            IF frozen THEN RAISE EXCEPTION 'Published native scene children cannot move to another policy'; END IF;
        END IF;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER native_scene_policy_immutable BEFORE INSERT OR UPDATE OR DELETE ON native_scene_policies
    FOR EACH ROW EXECUTE FUNCTION native_scene_policy_immutable();
DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['native_scene_policy_objects','native_scene_policy_approaches',
      'native_scene_policy_combat_cells','native_scene_profile_states','native_scene_profile_state_levels',
      'native_scene_profile_targets','native_scene_environment_placements','native_scene_admission_policies']
    LOOP
        EXECUTE format('CREATE TRIGGER native_scene_policy_immutable BEFORE INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION native_scene_policy_immutable()',table_name);
    END LOOP;
END $$;

-- Migration-local canonical encoder for this already published ASCII/integer
-- legacy policy only. Runtime digesting remains Python's existing digest().
CREATE FUNCTION pg_temp.native_scene_legacy_canonical(value jsonb) RETURNS text
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE result text;
BEGIN
    CASE jsonb_typeof(value)
    WHEN 'object' THEN
        SELECT '{'||coalesce(string_agg(to_jsonb(key)::text||':'||pg_temp.native_scene_legacy_canonical(val),',' ORDER BY key COLLATE "C"),'')||'}'
        INTO result FROM jsonb_each(value) AS fields(key,val);
    WHEN 'array' THEN
        SELECT '['||coalesce(string_agg(pg_temp.native_scene_legacy_canonical(val),',' ORDER BY ordinal),'')||']'
        INTO result FROM jsonb_array_elements(value) WITH ORDINALITY AS entries(val,ordinal);
    ELSE result:=value::text;
    END CASE;
    RETURN result;
END $$;

-- Migrate only the exact existing published133 authority. No legacy setting or
-- receipt is changed or deleted, and no new13/134/164 policy is activated here.
DO $$
DECLARE document jsonb; legacy jsonb; admission jsonb; identity text;
BEGIN
    SELECT value INTO document FROM settings WHERE name='native_scene_start_contracts' FOR SHARE;
    IF document IS NULL THEN
        IF EXISTS (SELECT 1 FROM native_scene_start_receipts) THEN
            RAISE EXCEPTION 'Existing scene receipts require their published legacy source';
        END IF;
        RETURN;
    END IF;
    IF document->>'schema' IS DISTINCT FROM 'native-scene-start-contracts-v1'
       OR jsonb_array_length(document->'policies') IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'Normalize only the reviewed legacy scene publication';
    END IF;
    legacy:=document->'policies'->0;
    identity:=legacy->>'policy_id';
    IF identity IS DISTINCT FROM 'wakemu.mineral_tower_36.native_start.v1'
       OR encode(sha256(convert_to(pg_temp.native_scene_legacy_canonical(legacy),'UTF8')),'hex')
          IS DISTINCT FROM '693a6bef35d211ec8d7f7749952e005f860f50660b7a9c64ab3fe5320c7c51b6' THEN
        RAISE EXCEPTION 'Legacy scene policy differs from its reviewed receipt identity';
    END IF;
    INSERT INTO native_scene_policies(policy_id,authority,policy_sha256,map_id,definition_id,template_id,
      source_id,wire_action,descriptor_id,catalog_revision,native_group_id,native_action_id,native_script_reference,
      native_criterion,price_item_id,price_quantity,maximum_members,competitive_ceiling,profile_mode,profile_provenance,
      combat_anchor_x,combat_anchor_y,combat_anchor_z,combat_area_provenance,environment_enabled,
      environment_area_reference,environment_level,environment_coordinate_authority,environment_map_graphics_sha256,
      environment_provenance,native_descriptor,native_effects,source_provenance)
    SELECT identity,legacy->>'authority','693a6bef35d211ec8d7f7749952e005f860f50660b7a9c64ab3fe5320c7c51b6',
      (legacy->>'map_id')::integer,(legacy->>'definition_id')::integer,(legacy->>'template_id')::integer,
      (legacy->>'source_id')::bigint,(legacy->>'wire_action')::integer,(legacy->>'descriptor_id')::integer,legacy->>'catalog_revision',
      (legacy#>>'{native_descriptor,groups,0,id}')::integer,(legacy#>>'{native_descriptor,groups,0,actions,0,id}')::integer,
      (legacy#>>'{native_effects,0,reference}')::integer,legacy#>>'{native_descriptor,groups,0,actions,0,criterion}',
      (legacy#>>'{native_descriptor,groups,0,cod}')::integer,(legacy#>>'{native_descriptor,groups,0,coe}')::integer,
      (legacy->>'maximum_members')::integer,(legacy->>'competitive_ceiling')::integer,'binary',legacy#>>'{profile,provenance}',
      (legacy#>>'{combat_anchor,0}')::integer,(legacy#>>'{combat_anchor,1}')::integer,(legacy#>>'{combat_anchor,2}')::integer,
      legacy->>'combat_area_provenance',true,(legacy#>>'{environment,area_reference}')::integer,
      (legacy#>>'{environment,level}')::integer,legacy#>>'{environment,coordinate_authority}',
      legacy#>>'{environment,map_graphics_sha256}',legacy#>>'{environment,provenance}',
      legacy->'native_descriptor',legacy->'native_effects',document->'source_provenance';
    INSERT INTO native_scene_policy_objects
    SELECT identity,'gate',ordinal,(row->>'id')::bigint,row->>'type',(row#>>'{position,0}')::integer,
      (row#>>'{position,1}')::integer,(row#>>'{position,2}')::integer,row->>'payload_hex'
    FROM jsonb_array_elements(legacy->'gates') WITH ORDINALITY AS items(row,ordinal);
    INSERT INTO native_scene_policy_approaches
    SELECT identity,ordinal,(row->>0)::integer,(row->>1)::integer,(row->>2)::integer
    FROM jsonb_array_elements(legacy->'approaches') WITH ORDINALITY AS items(row,ordinal);
    INSERT INTO native_scene_policy_combat_cells
    SELECT identity,ordinal,(row->>0)::integer,(row->>1)::integer,(row->>2)::integer
    FROM jsonb_array_elements(legacy->'combat_cells') WITH ORDINALITY AS items(row,ordinal);
    INSERT INTO native_scene_profile_states
    SELECT identity,ordinal,(row#>>'{}')::integer,legacy#>>ARRAY['profile','native_state_source_digests',row#>>'{}']
    FROM jsonb_array_elements(legacy#>'{profile,native_binary_state_ids}') WITH ORDINALITY AS items(row,ordinal);
    INSERT INTO native_scene_profile_state_levels
    SELECT policy_id,ordinal,level,level FROM native_scene_profile_states CROSS JOIN generate_series(1,2) level
    WHERE policy_id=identity;
    INSERT INTO native_scene_profile_targets
    SELECT identity,ordinal,(row#>>'{}')::integer
    FROM jsonb_array_elements(legacy#>'{profile,target_references}') WITH ORDINALITY AS items(row,ordinal);
    INSERT INTO native_scene_environment_placements(policy_id,ordinal,x,y,z,original_graphic)
    SELECT identity,ordinal,(row#>>'{cell,0}')::integer,(row#>>'{cell,1}')::integer,
      (row#>>'{cell,2}')::integer,(row->>'original_graphic')::integer
    FROM jsonb_array_elements(legacy#>'{environment,placements}') WITH ORDINALITY AS items(row,ordinal);
    SELECT value#>'{routes,native_dungeon_133}' INTO admission FROM settings WHERE name='native_special_instance_admission' FOR SHARE;
    -- B3 ships this attested admission source but may never publish its setting.
    -- Source file SHA256: 64ef4a88826a464a12e52cea0ee24872317b5787d091e56e131613c0a1926a40.
    -- Convert its exact scalar authority only when the key is absent. A present
    -- malformed publication must still fail the unchanged policy digest below.
    -- This temporary JSON value is serialization proof, not a new rules setting.
    IF NOT FOUND THEN
        admission:=jsonb_build_object(
          'policy_id','wakemu.mineral_tower_36.admission.v1',
          'authority','reconstructed_wakemu_native_scene_v1',
          'route',jsonb_build_object('template_id',136,'definition_id',133,
            'entry_map_id',1202,'entry_object_id',29076,'destination_id',3117,'start_map_id',1159),
          'maximum_members',3,'competitive_ceiling',50,
          'provenance','Original free outer teleporter3117/template136, three-player format and forced competitive ceiling50. Native item28028x1 is charged by inside GenericActivable33366/descriptor1485 to the activating nonhero participant; never at this outer transition.',
          'native_paid_start',jsonb_build_object('map_id',1159,'object_id',33366,'descriptor_id',1485),
          'minimum_configuration_version',5);
    END IF;
    IF admission IS NULL OR encode(sha256(convert_to(pg_temp.native_scene_legacy_canonical(admission),'UTF8')),'hex')
      IS DISTINCT FROM 'affab21db7c0e259e68458d8919dbf3810eb6581f9caaf7548ae1abd8249bce7' THEN
        RAISE EXCEPTION 'Legacy outer admission differs from its published source';
    END IF;
    INSERT INTO native_scene_admission_policies
    SELECT identity,admission->>'policy_id','affab21db7c0e259e68458d8919dbf3810eb6581f9caaf7548ae1abd8249bce7',
      'native_dungeon_133',admission->>'authority',(admission#>>'{route,entry_map_id}')::integer,
      (admission#>>'{route,entry_object_id}')::bigint,(admission#>>'{route,destination_id}')::integer,
      (admission->>'minimum_configuration_version')::integer,admission->>'provenance';
    UPDATE native_scene_policies SET published=true WHERE policy_id=identity;
END $$;
DROP FUNCTION pg_temp.native_scene_legacy_canonical(jsonb);
