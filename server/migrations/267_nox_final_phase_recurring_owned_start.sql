-- Reconstructed recurring final-phase calendar, not a recovered server publisher.
-- Preserve immutable266 and the native401749 ->401750 ->8472 program.
-- A complete fresh migration prefix shares one transaction; settle266 inventory first.
SET CONSTRAINTS encounter_table_version_callbacks_complete,
    encounter_table_callback_inventory_complete IMMEDIATE;
ALTER TABLE encounter_table_listener_callbacks
    DROP CONSTRAINT encounter_table_listener_callbacks_execution_count_check;
ALTER TABLE encounter_table_listener_callbacks
    ADD CONSTRAINT encounter_table_listener_callbacks_execution_count_check
    CHECK(execution_count<>0);
SET CONSTRAINTS encounter_table_version_callbacks_complete,
    encounter_table_callback_inventory_complete DEFERRED;

INSERT INTO encounter_table_listener_versions (
    policy,authority,map_id,monster_references,catalog_revision,boss_reference,
    boss_constructor_state,owner_reference,owner_constructor_state,effect_reference,
    event_id,channel,timing,additional_effect_references
)
SELECT 'wakemu-nox-owned-boundaries-v4',
       'wakemu-reconstructed-guide-recurring-final-owned-start;native401544-401749-consumers;original-publisher-unrecovered',
       map_id,monster_references,catalog_revision,boss_reference,boss_constructor_state,
       owner_reference,owner_constructor_state,effect_reference,event_id,channel,timing,
       ARRAY[401544,401749]
  FROM encounter_table_listener_versions WHERE policy='wakemu-nox-owned-boundaries-v3';

INSERT INTO encounter_table_listener_callbacks (
    policy,effect_reference,owner_reference,owner_state,forbidden_state,event_id,
    channel,timing,effect_family,selector_class,selector_mask,parameter_count,
    native_parameters,criterion,area_class,children,execution_count,
    reverse_subscription,global_subscription,event_caster_code,event_target_code,
    owner_on_caster,definition_type,effect_flags
)
SELECT 'wakemu-nox-owned-boundaries-v4',effect_reference,owner_reference,owner_state,
       forbidden_state,event_id,channel,timing,effect_family,selector_class,selector_mask,
       parameter_count,native_parameters,criterion,area_class,children,execution_count,
       reverse_subscription,global_subscription,event_caster_code,event_target_code,
       owner_on_caster,definition_type,effect_flags
  FROM encounter_table_listener_callbacks
 WHERE policy='wakemu-nox-owned-boundaries-v3' AND effect_reference=401544;

INSERT INTO encounter_table_listener_callbacks (
    policy,effect_reference,owner_reference,owner_state,forbidden_state,event_id,
    channel,timing,effect_family,selector_class,selector_mask,parameter_count,
    native_parameters,criterion,area_class,children,execution_count,
    reverse_subscription,global_subscription,event_caster_code,event_target_code,
    owner_on_caster,definition_type,effect_flags
) VALUES (
    'wakemu-nox-owned-boundaries-v4',401749,5664,8979,9031,1005,60,
    'owned_boss_post_start',330,'fcE',1,0,'[]'::JSONB,'','anD',ARRAY[401750],
    -1,TRUE,FALSE,2,2,FALSE,2,'{}'::INTEGER[]
);
UPDATE encounter_table_listener_active
   SET policy='wakemu-nox-owned-boundaries-v4'
 WHERE map_id=1435 AND monster_references=ARRAY[5664]
   AND policy='wakemu-nox-owned-boundaries-v3';
