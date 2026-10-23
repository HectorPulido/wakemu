-- Shared, source-qualified environmental profiles and durable event lifecycle.
-- No original scenario is enabled by this schema migration.
CREATE TABLE environmental_runtime_profiles (
 profile_key text NOT NULL CHECK(length(profile_key) BETWEEN 1 AND 128),
 version integer NOT NULL CHECK(version>0), native_scenario_id integer,
 family text NOT NULL CHECK(family IN ('monster_defeat','group_defeat','resource_collect','resource_plant','monster_destroy')),
 mode text NOT NULL CHECK(mode IN ('solo','collaborative','race','competitive')),
 minimum_contribution bigint NOT NULL DEFAULT 1 CHECK(minimum_contribution>0),
 map_id integer NOT NULL CHECK(map_id>0),region_id integer,
 duration_ms bigint NOT NULL CHECK(duration_ms>0),
 recurrence_period_ms bigint CHECK(recurrence_period_ms>=duration_ms),
 anchor_ms bigint NOT NULL CHECK(anchor_ms>=0),
 proposal_ms bigint NOT NULL DEFAULT 0 CHECK(proposal_ms>=0),
 level_min integer NOT NULL CHECK(level_min>0),level_max integer NOT NULL CHECK(level_max>=level_min),
 authority text NOT NULL CHECK(length(authority)>0),
 source_sha256 text NOT NULL CHECK(length(source_sha256)=64),
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 enabled boolean NOT NULL DEFAULT false,sealed boolean NOT NULL DEFAULT false,
 PRIMARY KEY(profile_key,version),CHECK(NOT enabled OR sealed)
);
CREATE UNIQUE INDEX environmental_one_enabled_version ON environmental_runtime_profiles(profile_key) WHERE enabled;
CREATE TABLE environmental_profile_bindings (
 profile_key text NOT NULL,version integer NOT NULL,
 producer text NOT NULL CHECK(producer IN ('committed_planting','existing_declared_groups')),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(profile_key,version,producer),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles(profile_key,version)
);
CREATE TABLE environmental_profile_evaluation (
 profile_key text NOT NULL,version integer NOT NULL,
 evaluator text NOT NULL CHECK(evaluator IN ('first_completion','score_at_deadline')),
 winner_count integer NOT NULL CHECK(winner_count BETWEEN 1 AND 32767),
 tie_policy text NOT NULL CHECK(tie_policy IN ('commit_order','share_boundary','character_id')),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(profile_key,version),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles(profile_key,version),
 CHECK((evaluator='first_completion' AND tie_policy='commit_order') OR
       (evaluator='score_at_deadline' AND tie_policy IN ('share_boundary','character_id')))
);
CREATE TABLE environmental_profile_objectives (
 profile_key text NOT NULL,version integer NOT NULL,
 objective_key text NOT NULL CHECK(length(objective_key) BETWEEN 1 AND 128),
 family text NOT NULL CHECK(family IN ('monster_defeat','group_defeat','resource_collect','resource_plant','monster_destroy')),
 target_reference integer,action_id integer,resource_step integer,
 unit text NOT NULL DEFAULT 'interaction' CHECK(unit IN ('interaction','quantity')),
 required_quantity bigint NOT NULL CHECK(required_quantity>0),
 PRIMARY KEY(profile_key,version,objective_key),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles(profile_key,version)
);
CREATE TABLE environmental_profile_group_composition (
 profile_key text NOT NULL,version integer NOT NULL,
 group_reference integer NOT NULL CHECK(group_reference>0),
 monster_reference integer NOT NULL CHECK(monster_reference>0),
 quantity integer NOT NULL CHECK(quantity>0),source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(profile_key,version,group_reference,monster_reference),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles(profile_key,version)
);
CREATE TABLE environmental_profile_rewards (
 profile_key text NOT NULL,version integer NOT NULL,ordinal integer NOT NULL CHECK(ordinal>=0),
 kind text NOT NULL CHECK(kind IN ('xp','item','kamas')),
 reference integer,quantity bigint NOT NULL CHECK(quantity>0 AND quantity<2147483648),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(profile_key,version,ordinal),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles(profile_key,version),
 CHECK((kind='item' AND reference>0) OR (kind IN ('xp','kamas') AND reference IS NULL))
);
CREATE TABLE environmental_profile_publication (
 profile_key text NOT NULL,version integer NOT NULL,challenge_id integer NOT NULL,
 secondary_id integer NOT NULL,protector_id integer NOT NULL,
 native_time bigint,time_mode text NOT NULL CHECK(time_mode IN ('constant','remaining_ms')),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(profile_key,version),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles(profile_key,version),
 CHECK(time_mode<>'constant' OR native_time IS NOT NULL)
);
CREATE TABLE environmental_profile_publication_states (
 profile_key text NOT NULL,version integer NOT NULL,
 lifecycle_state text NOT NULL CHECK(lifecycle_state IN ('proposed','active','completed','expired','cancelled')),
 state_ordinal smallint NOT NULL CHECK(state_ordinal BETWEEN 0 AND 3),
 PRIMARY KEY(profile_key,version,lifecycle_state),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_profile_publication(profile_key,version)
);
CREATE TABLE environmental_profile_variables (
 profile_key text NOT NULL,version integer NOT NULL,variable_index integer NOT NULL CHECK(variable_index>=0),
 name text NOT NULL CHECK(length(name)>0),objective_key text,constant_value bigint,
 PRIMARY KEY(profile_key,version,variable_index),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_profile_publication(profile_key,version),
 FOREIGN KEY(profile_key,version,objective_key) REFERENCES environmental_profile_objectives(profile_key,version,objective_key),
 CHECK((objective_key IS NULL)<>(constant_value IS NULL))
);
CREATE TABLE environmental_event_instances (
 instance_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 profile_key text NOT NULL,version integer NOT NULL,map_id integer NOT NULL CHECK(map_id>0),
 world_instance_id bigint NOT NULL CHECK(world_instance_id>=0),region_id integer,
 cycle_key bigint NOT NULL CHECK(cycle_key>=0),started_at_ms bigint NOT NULL CHECK(started_at_ms>=0),
 deadline_ms bigint NOT NULL CHECK(deadline_ms>started_at_ms),
 state text NOT NULL DEFAULT 'active' CHECK(state IN ('proposed','active','completed','expired','cancelled')),
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),terminal_at_ms bigint,cancel_reason text,
 CHECK((state='cancelled')=(cancel_reason IS NOT NULL)),
 FOREIGN KEY(profile_key,version) REFERENCES environmental_runtime_profiles(profile_key,version),
 UNIQUE(profile_key,version,map_id,world_instance_id,cycle_key)
);
CREATE INDEX environmental_instances_scope ON environmental_event_instances(map_id,world_instance_id,state,deadline_ms);
CREATE TABLE environmental_participants (
 instance_id bigint NOT NULL REFERENCES environmental_event_instances(instance_id),
 character_id bigint NOT NULL,account_id bigint NOT NULL,
 joined_at_ms bigint NOT NULL CHECK(joined_at_ms>=0),eligible boolean NOT NULL DEFAULT true,
 completed_at_ms bigint,
 PRIMARY KEY(instance_id,character_id),UNIQUE(instance_id,character_id,account_id),
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id)
);
CREATE TABLE environmental_event_memberships (
 instance_id bigint NOT NULL REFERENCES environmental_event_instances(instance_id),
 entity_kind text NOT NULL CHECK(entity_kind IN ('monster','group','resource')),
 entity_id bigint NOT NULL CHECK(entity_id<>0),reference integer,
 source_key text NOT NULL CHECK(length(source_key) BETWEEN 1 AND 200),
 spawn_owned boolean NOT NULL DEFAULT false,
 PRIMARY KEY(instance_id,entity_kind,entity_id)
);
CREATE TABLE environmental_event_groups (
 instance_id bigint NOT NULL,group_id bigint NOT NULL CHECK(group_id>0),
 entity_kind text NOT NULL DEFAULT 'group' CHECK(entity_kind='group'),
 admitted_revision bigint NOT NULL CHECK(admitted_revision>=0),
 PRIMARY KEY(instance_id,group_id),
 FOREIGN KEY(instance_id,entity_kind,group_id)
  REFERENCES environmental_event_memberships(instance_id,entity_kind,entity_id)
);
CREATE TABLE environmental_event_group_members (
 instance_id bigint NOT NULL,group_id bigint NOT NULL,
 monster_id bigint NOT NULL CHECK(monster_id<0),monster_reference integer NOT NULL CHECK(monster_reference>0),
 PRIMARY KEY(instance_id,group_id,monster_id),
 FOREIGN KEY(instance_id,group_id) REFERENCES environmental_event_groups(instance_id,group_id)
);
CREATE TABLE environmental_event_rankings (
 instance_id bigint NOT NULL,character_id bigint NOT NULL,
 position integer NOT NULL CHECK(position>0),display_rank integer NOT NULL CHECK(display_rank>0),
 score bigint NOT NULL CHECK(score>=0),rewarded boolean NOT NULL,
 finalized_at_ms bigint NOT NULL CHECK(finalized_at_ms>=0),
 PRIMARY KEY(instance_id,character_id),UNIQUE(instance_id,position),
 FOREIGN KEY(instance_id,character_id) REFERENCES environmental_participants(instance_id,character_id)
);
CREATE TABLE environmental_cleanup_outbox (
 instance_id bigint NOT NULL,entity_kind text NOT NULL,entity_id bigint NOT NULL,
 reference integer NOT NULL,source_key text NOT NULL,
 action text NOT NULL CHECK(action IN ('despawn_owned','release_membership')),
 requested_at_ms bigint NOT NULL CHECK(requested_at_ms>=0),completed_at_ms bigint,
 PRIMARY KEY(instance_id,entity_kind,entity_id),
 FOREIGN KEY(instance_id,entity_kind,entity_id)
  REFERENCES environmental_event_memberships(instance_id,entity_kind,entity_id)
);
CREATE TABLE environmental_progress (
 instance_id bigint NOT NULL,character_id bigint NOT NULL,objective_key text NOT NULL,
 quantity bigint NOT NULL DEFAULT 0 CHECK(quantity>=0),
 PRIMARY KEY(instance_id,character_id,objective_key),
 FOREIGN KEY(instance_id,character_id) REFERENCES environmental_participants(instance_id,character_id)
);
CREATE TABLE environmental_fact_receipts (
 instance_id bigint NOT NULL,character_id bigint NOT NULL,objective_key text NOT NULL,
 receipt_key text NOT NULL CHECK(length(receipt_key) BETWEEN 1 AND 200),
 entity_kind text NOT NULL,entity_id bigint NOT NULL,
 fact_digest text NOT NULL CHECK(length(fact_digest)=64),quantity bigint NOT NULL CHECK(quantity>0),
 occurred_at_ms bigint NOT NULL CHECK(occurred_at_ms>=0),
 PRIMARY KEY(instance_id,character_id,objective_key,receipt_key,entity_kind,entity_id),
 FOREIGN KEY(instance_id,character_id) REFERENCES environmental_participants(instance_id,character_id)
);
CREATE TABLE environmental_reward_entitlements (
 entitlement_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 instance_id bigint NOT NULL,character_id bigint NOT NULL,account_id bigint NOT NULL,
 earned_at_ms bigint NOT NULL CHECK(earned_at_ms>=0),claimed_at_ms bigint,companions_frozen_at_ms bigint,
 UNIQUE(instance_id,character_id),UNIQUE(entitlement_id,account_id,character_id),
 FOREIGN KEY(instance_id,character_id,account_id) REFERENCES environmental_participants(instance_id,character_id,account_id)
);
CREATE TABLE environmental_reward_components (
 entitlement_id bigint NOT NULL REFERENCES environmental_reward_entitlements(entitlement_id),
 ordinal integer NOT NULL CHECK(ordinal>=0),kind text NOT NULL CHECK(kind IN ('xp','item','kamas')),
 reference integer,quantity bigint NOT NULL CHECK(quantity>0 AND quantity<2147483648),
 source_authority text NOT NULL CHECK(length(source_authority)>0),
 PRIMARY KEY(entitlement_id,ordinal),
 CHECK((kind='item' AND reference>0) OR (kind IN ('xp','kamas') AND reference IS NULL))
);
CREATE TABLE environmental_entitlement_companions (
 entitlement_id bigint NOT NULL REFERENCES environmental_reward_entitlements(entitlement_id),
 companion_id bigint NOT NULL REFERENCES account_companions(id),account_id bigint NOT NULL,
 owner_character_id bigint NOT NULL,frozen_at_ms bigint NOT NULL CHECK(frozen_at_ms>=0),
 owner_xp bigint CHECK(owner_xp>=0),experience_award bigint CHECK(experience_award>=0),
 delivered_at_ms bigint,
 PRIMARY KEY(entitlement_id,companion_id),
 FOREIGN KEY(entitlement_id,account_id,owner_character_id)
  REFERENCES environmental_reward_entitlements(entitlement_id,account_id,character_id)
);
CREATE TABLE environmental_claim_receipts (
 entitlement_id bigint PRIMARY KEY REFERENCES environmental_reward_entitlements(entitlement_id),
 account_id bigint NOT NULL REFERENCES accounts(id),character_id bigint NOT NULL REFERENCES characters(id),
 claimed_at_ms bigint NOT NULL CHECK(claimed_at_ms>=0),owner_xp bigint NOT NULL CHECK(owner_xp>=0),
 kamas bigint NOT NULL CHECK(kamas>=0),component_count integer NOT NULL CHECK(component_count>=0)
);
CREATE TABLE environmental_publication_outbox (
 delivery_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 delivery_key text NOT NULL UNIQUE CHECK(length(delivery_key) BETWEEN 1 AND 200),
 instance_id bigint NOT NULL,character_id bigint NOT NULL,account_id bigint NOT NULL,
 kind text NOT NULL CHECK(kind IN ('snapshot','progress','completed','expired','claimed')),
 revision bigint NOT NULL CHECK(revision>0),created_at_ms bigint NOT NULL CHECK(created_at_ms>=0),acknowledged_at_ms bigint,
 FOREIGN KEY(instance_id,character_id,account_id) REFERENCES environmental_participants(instance_id,character_id,account_id)
);
CREATE INDEX environmental_pending_publications ON environmental_publication_outbox(account_id,character_id,delivery_id) WHERE acknowledged_at_ms IS NULL;
CREATE FUNCTION environmental_profile_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.sealed THEN
  IF TG_OP='DELETE' OR (to_jsonb(OLD)-'enabled')<>(to_jsonb(NEW)-'enabled') THEN
   RAISE EXCEPTION 'Sealed environmental profile is immutable';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER environmental_profile_immutable BEFORE UPDATE OR DELETE ON environmental_runtime_profiles
 FOR EACH ROW EXECUTE FUNCTION environmental_profile_immutable();
CREATE FUNCTION environmental_profile_child_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text;v integer;previous_k text;previous_v integer;
BEGIN
 IF TG_OP<>'DELETE' THEN k:=NEW.profile_key;v:=NEW.version; END IF;
 IF TG_OP<>'INSERT' THEN previous_k:=OLD.profile_key;previous_v:=OLD.version; END IF;
 IF EXISTS(SELECT 1 FROM environmental_runtime_profiles p WHERE p.sealed
   AND ((p.profile_key=k AND p.version=v) OR (p.profile_key=previous_k AND p.version=previous_v))) THEN
  RAISE EXCEPTION 'Sealed environmental profile content is immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['environmental_profile_group_composition','environmental_profile_bindings','environmental_profile_evaluation','environmental_profile_objectives','environmental_profile_rewards',
  'environmental_profile_publication','environmental_profile_publication_states','environmental_profile_variables'] LOOP
  EXECUTE format('CREATE TRIGGER %I BEFORE INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION environmental_profile_child_immutable()',t||'_immutable',t);
 END LOOP;
END $$;
