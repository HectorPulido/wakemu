-- Native Active and Complete are independent. Recover actual local activations
-- conservatively; visibility/catalog previews never authorize an active flag.
DO $migration$
DECLARE owner record;
        baseline jsonb;
        flags jsonb;
        periods jsonb;
        unknown_flags jsonb;
BEGIN
    FOR owner IN
        SELECT a.character_id,a.snapshot,p.state
        FROM character_achievement_authority a
        LEFT JOIN character_achievement_progress p USING(character_id)
        FOR UPDATE OF a
    LOOP
        baseline := COALESCE(owner.state,owner.snapshot);
        IF baseline ? 'active' AND owner.snapshot ? 'active' THEN
            CONTINUE;
        END IF;
        SELECT COALESCE(jsonb_agg(to_jsonb(identity) ORDER BY identity),'[]'::jsonb)
        INTO flags
        FROM (
            SELECT value::integer AS identity
            FROM jsonb_array_elements_text(baseline->'running')
            UNION
            SELECT value::integer AS identity
            FROM jsonb_array_elements_text(baseline->'completed') done(value)
            JOIN native_quest_metadata_definitions n
              ON n.definition_id=done.value::integer
             AND n.revision=(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1)
            WHERE baseline->'completion_dates' ? done.value
              AND n.data->'native'->>'native_class'='aJM'
              AND n.data->'native'->>'cjT'='0'
              AND n.data->'native'->>'cjU'='0'
            UNION
            SELECT value::integer AS identity
            FROM jsonb_array_elements_text(baseline->'completed') done(value)
            WHERE EXISTS(SELECT 1 FROM character_recurring_mission_cycles r
                         WHERE r.character_id=owner.character_id AND r.definition_id=done.value::integer)
               OR EXISTS(SELECT 1 FROM recurring_hunter_acceptances r
                         WHERE r.character_id=owner.character_id AND r.definition_id=done.value::integer AND r.expired_at_ms IS NULL)
               OR EXISTS(SELECT 1 FROM character_guild_daily_quests r
                         WHERE r.character_id=owner.character_id AND r.definition_id=done.value::integer)
        ) earned;

        SELECT COALESCE(jsonb_agg(to_jsonb(value::integer) ORDER BY value::integer),'[]'::jsonb)
        INTO unknown_flags
        FROM jsonb_array_elements_text(baseline->'completed') done(value)
        WHERE NOT flags @> jsonb_build_array(value::integer);

        SELECT COALESCE(jsonb_object_agg(n.definition_id::text,jsonb_build_object(
            'anchor_ms',(n.data->'native'->>'cjT')::bigint,
            'period_seconds',(n.data->'native'->>'cjU')::bigint,
            'accepted_at_ms',(
                SELECT max(accepted_at_ms) FROM (
                    SELECT accepted_at_ms FROM character_recurring_mission_cycles r
                    WHERE r.character_id=owner.character_id AND r.definition_id=n.definition_id
                    UNION ALL
                    SELECT accepted_at_ms FROM recurring_hunter_acceptances r
                    WHERE r.character_id=owner.character_id AND r.definition_id=n.definition_id AND r.expired_at_ms IS NULL
                    UNION ALL
                    SELECT activated_at_ms FROM character_guild_daily_quests r
                    WHERE r.character_id=owner.character_id AND r.definition_id=n.definition_id
                ) clocks
            ))),'{}'::jsonb)
        INTO periods
        FROM native_quest_metadata_definitions n
        WHERE n.revision=(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1)
          AND n.definition_id IN (SELECT value::integer FROM jsonb_array_elements_text(flags))
          AND (n.data->'native'->>'cjT')::bigint > 0;

        UPDATE character_achievement_authority
        SET snapshot=snapshot||jsonb_build_object('active',flags,'active_periods',periods,'active_unknown',unknown_flags),
            revision=revision+1,provenance='native_independent_active_backfill',
            updated_at=CURRENT_TIMESTAMP
        WHERE character_id=owner.character_id;
        UPDATE character_achievement_progress
        SET state=state||jsonb_build_object('active',flags,'active_periods',periods,'active_unknown',unknown_flags),
            revision=revision+1,updated_at=CURRENT_TIMESTAMP
        WHERE character_id=owner.character_id;
    END LOOP;
END;
$migration$;
ALTER TABLE character_achievement_authority ALTER COLUMN snapshot SET DEFAULT
    '{"running":[],"completed":[],"objectives":[],"active":[],"active_periods":{},"active_unknown":[]}'::jsonb;
