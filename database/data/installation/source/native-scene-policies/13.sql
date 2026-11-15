-- PRIVATE typed data proposal; no gameplay JSON rule publication.
-- Apply only with schema348 and the matching reviewed scene implementation.
DO $scene_seed$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('native_scene_policy:'||'wakemu.configured_native_13.paid_start.v1',0));
    IF EXISTS (SELECT 1 FROM native_scene_policies WHERE policy_id='wakemu.configured_native_13.paid_start.v1') THEN
        IF NOT EXISTS (SELECT 1 FROM native_scene_policies WHERE policy_id='wakemu.configured_native_13.paid_start.v1' AND policy_sha256='e71215f15a1690bc1f3df34e3a5fb1742f436cb7066ce39bb81c6539ec00b6c1' AND published) THEN
            RAISE EXCEPTION 'Existing native scene identity differs from reviewed immutable seed';
        END IF;
        RETURN;
    END IF;
    INSERT INTO "native_scene_policies" ("policy_id","authority","map_id","definition_id","template_id","source_id","wire_action","descriptor_id","catalog_revision","maximum_members","native_descriptor","native_effects","policy_sha256","native_group_id","native_action_id","native_script_reference","native_criterion","price_item_id","price_quantity","profile_mode","environment_enabled","competitive_ceiling","compiled_plan_sha256") VALUES ('wakemu.configured_native_13.paid_start.v1','explicit_reconstructed_source_bound_native_scene_v1',483,13,16,33318,0,1483,'b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450',3,'{"descriptor_id": 1483, "groups": [{"id": 1841, "clx": 431, "cod": 29714, "coe": 1, "cof": true, "cnd": 0, "cog": 0, "actions": [{"wire_action": 0, "criterion": "not IsHero()", "raw_cob": 1.0, "effects": [{"criterion": "not IsHero()", "parameters": [], "type": 1, "reference": 3359}], "id": 1892}]}]}'::jsonb,'[{"criterion": "not IsHero()", "parameters": [], "type": 1, "reference": 3359}]'::jsonb,'e71215f15a1690bc1f3df34e3a5fb1742f436cb7066ce39bb81c6539ec00b6c1',1841,1892,3359,'not IsHero()',29714,1,'configured_roster',false,95,'90557c627f5b07c27d3562fd6d0797b9057791b214d26909a44ba8d0745ab284');
    INSERT INTO "native_scene_policy_objects" ("policy_id","object_role","ordinal","object_id","native_type","x","y","z","payload_hex") VALUES ('wakemu.configured_native_13.paid_start.v1','evidence',1,33318,'GenericActivableInteractiveElement', -60, -76,0,'02000000000b010000000d00000101e3ffffffc4ffffffb4000000010101030001000000043134383300000000000101');
    INSERT INTO "native_scene_policy_approaches" ("policy_id","ordinal","x","y","z") VALUES ('wakemu.configured_native_13.paid_start.v1',1, -60, -77,0);
    INSERT INTO "native_scene_policy_approaches" ("policy_id","ordinal","x","y","z") VALUES ('wakemu.configured_native_13.paid_start.v1',2, -61, -76,0);
    INSERT INTO "native_scene_policy_approaches" ("policy_id","ordinal","x","y","z") VALUES ('wakemu.configured_native_13.paid_start.v1',3, -59, -76,0);
    INSERT INTO "native_scene_policy_approaches" ("policy_id","ordinal","x","y","z") VALUES ('wakemu.configured_native_13.paid_start.v1',4, -60, -75,0);
    INSERT INTO "native_scene_admission_policies" ("policy_id","admission_policy_id","admission_sha256","route_key","authority","entry_map_id","entry_object_id","destination_id","minimum_configuration_version","provenance") VALUES ('wakemu.configured_native_13.paid_start.v1','wakemu.configured_native_13.admission.v1','668dc0b3539de5d409c8c8e3e6232b610dd5101e95c1ee27ce25303d68a6708b','native_dungeon_13','reconstructed_wakemu_native_scene_v1',337,18969,1167,1,'Original free outer teleporter1167/template16, three-player format and forced competitive ceiling95. Native item29714x1 is charged by inside GenericActivable33318/descriptor1483 to the activating nonhero participant; never at this outer transition. Original localized no.incantation.for.trool binds this ticket to boss arrival.');
    UPDATE native_scene_policies SET published=true WHERE policy_id='wakemu.configured_native_13.paid_start.v1';
END $scene_seed$;
