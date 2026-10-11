-- These were explicitly local trial placements, not recovered native spawns.
-- Preserve their rows/provenance for review and preserve captured native actors.
UPDATE world_dialogue_npcs
SET enabled = false
WHERE actor_id IN (
    -2251799813685248,
    -2251799813685249,
    -2251799813685250,
    -2251799813685251
)
AND provenance LIKE 'Local Wakemu initial placement near default character start;%';
