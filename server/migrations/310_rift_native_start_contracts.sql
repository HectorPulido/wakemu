-- Native table 31 activators: acting non-hero pays once at combat start.
-- This recovers item admission only; it does not enable ultimate encounters.
WITH recovered(wave_id, map_id, object_id, descriptor_id, item_reference, script_reference) AS (
    VALUES ('5', 1318, 33018, 1457, 28789, 3296),
           ('8', 1324, 33024, 1458, 28790, 3299),
           ('37', 1347, 33271, 1477, 29594, 3345)
), revised AS (
    SELECT jsonb_object_agg(entry.key,
        CASE WHEN recovered.wave_id IS NOT NULL
                  AND (entry.value->>'map_id')::integer = recovered.map_id
                  AND entry.value->>'type' = 'ULTIMATE_INFINITE_WAVE'
             THEN jsonb_set(entry.value, '{native_start_contract}', jsonb_build_object(
                 'object_id', recovered.object_id,
                 'descriptor_id', recovered.descriptor_id,
                 'reference', recovered.item_reference,
                 'quantity', 1, 'consume', true, 'action', 1,
                 'criterion', 'not IsHero()',
                 'script_reference', recovered.script_reference,
                 'source', 'native_table_31'))
             ELSE entry.value END) AS value
    FROM settings s
    CROSS JOIN LATERAL jsonb_each(s.value) entry
    LEFT JOIN recovered ON recovered.wave_id = entry.key
    WHERE s.name = 'rift_catalog'
)
UPDATE settings SET value = revised.value FROM revised
WHERE settings.name = 'rift_catalog' AND revised.value IS NOT NULL;
