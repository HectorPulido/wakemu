-- Account progress is authoritative for every objective and recurrence.
-- Preserve native delivery history and immutable source-time content versions.
SELECT pg_advisory_xact_lock(747117401);
SELECT pg_advisory_xact_lock(747117402);
ALTER TABLE objectives_account_progress ADD COLUMN period_key text NOT NULL DEFAULT 'once';
ALTER TABLE objectives_account_progress DROP CONSTRAINT objectives_account_progress_pkey;
ALTER TABLE objectives_account_progress ADD PRIMARY KEY(account_id,definition_key,period_key);

CREATE TABLE objectives_account_migration_audit (
 id bigserial PRIMARY KEY,
 account_id bigint NOT NULL,
 definition_key text NOT NULL,
 period_key text NOT NULL,
 category text NOT NULL,
 snapshot jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO objectives_account_migration_audit(account_id,definition_key,period_key,category,snapshot)
SELECT c.account_id,p.definition_key,p.period_key,'character_progress',to_jsonb(p)
FROM objectives_progress p JOIN characters c ON c.id=p.character_id;

INSERT INTO objectives_definition_audit(definition_key,revision,operator,definition)
SELECT key,revision,'migration182: account ownership',definition FROM objectives_definitions
WHERE COALESCE(definition->>'scope','character')<>'account';
UPDATE objectives_definitions SET definition=jsonb_set(definition,'{scope}','"account"'::jsonb),
 revision=revision+1,updated_at=CURRENT_TIMESTAMP
WHERE COALESCE(definition->>'scope','character')<>'account';

-- A maximum keeps the best earned counter without multiplying the same fight
-- retrospectively by its participating heroes. Completed history always wins.
CREATE TEMP TABLE account_progress_import ON COMMIT DROP AS
WITH histories AS (
 SELECT c.account_id,p.definition_key,p.period_key,p.counters,p.completed_at,
        p.character_id AS reward_character_id,p.updated_at
 FROM objectives_progress p JOIN characters c ON c.id=p.character_id
 UNION ALL
 SELECT account_id,definition_key,period_key,counters,completed_at,reward_character_id,updated_at
 FROM objectives_account_progress
), counter_maxima AS (
 SELECT account_id,definition_key,period_key,j.key,max(j.value::bigint) AS value
 FROM histories CROSS JOIN LATERAL jsonb_each_text(counters) j
 GROUP BY account_id,definition_key,period_key,j.key
), counters AS (
 SELECT account_id,definition_key,period_key,jsonb_object_agg(key,value) AS counters
 FROM counter_maxima GROUP BY account_id,definition_key,period_key
), summaries AS (
 SELECT account_id,definition_key,period_key,min(completed_at) AS completed_at,max(updated_at) AS updated_at
 FROM histories GROUP BY account_id,definition_key,period_key
), beneficiaries AS (
 SELECT DISTINCT ON(h.account_id,h.definition_key,h.period_key)
 h.account_id,h.definition_key,h.period_key,h.reward_character_id
 FROM histories h
 WHERE h.completed_at IS NOT NULL AND h.reward_character_id IS NOT NULL
 ORDER BY h.account_id,h.definition_key,h.period_key,
 EXISTS(SELECT 1 FROM objectives_rewards r WHERE r.character_id=h.reward_character_id
 AND r.definition_key=h.definition_key AND r.period_key=h.period_key AND r.delivered_at IS NOT NULL) DESC,
 h.completed_at,h.reward_character_id
)
SELECT s.account_id,s.definition_key,s.period_key,d.revision AS definition_revision,
 COALESCE(c.counters,'{}'::jsonb) AS counters,s.completed_at,s.updated_at,b.reward_character_id
FROM summaries s JOIN objectives_definitions d ON d.key=s.definition_key
LEFT JOIN counters c USING(account_id,definition_key,period_key)
LEFT JOIN beneficiaries b USING(account_id,definition_key,period_key);
INSERT INTO objectives_account_progress(account_id,definition_key,period_key,definition_revision,counters,completed_at,updated_at,reward_character_id)
SELECT account_id,definition_key,period_key,definition_revision,counters,completed_at,updated_at,reward_character_id
FROM account_progress_import
ON CONFLICT(account_id,definition_key,period_key) DO UPDATE SET
 definition_revision=EXCLUDED.definition_revision,counters=EXCLUDED.counters,
 completed_at=EXCLUDED.completed_at,updated_at=EXCLUDED.updated_at,reward_character_id=EXCLUDED.reward_character_id;

-- Already delivered objects/kamas are never removed. Surplus undelivered
-- per-character sets are retained in audit, but cannot be delivered a second time.
INSERT INTO objectives_account_migration_audit(account_id,definition_key,period_key,category,snapshot)
SELECT c.account_id,r.definition_key,r.period_key,'suppressed_duplicate_pending_reward',to_jsonb(r)
FROM objectives_rewards r JOIN characters c ON c.id=r.character_id
JOIN account_progress_import a ON a.account_id=c.account_id AND a.definition_key=r.definition_key AND a.period_key=r.period_key
WHERE r.delivered_at IS NULL AND (r.character_id IS DISTINCT FROM a.reward_character_id OR EXISTS(
 SELECT 1 FROM objectives_rewards paid JOIN characters pc ON pc.id=paid.character_id
 WHERE pc.account_id=c.account_id AND paid.definition_key=r.definition_key AND paid.period_key=r.period_key
 AND paid.reward_index=r.reward_index AND paid.delivered_at IS NOT NULL));
DELETE FROM objectives_rewards r USING characters c,account_progress_import a
WHERE c.id=r.character_id AND a.account_id=c.account_id AND a.definition_key=r.definition_key
AND a.period_key=r.period_key AND r.delivered_at IS NULL AND (r.character_id IS DISTINCT FROM a.reward_character_id OR EXISTS(
 SELECT 1 FROM objectives_rewards paid JOIN characters pc ON pc.id=paid.character_id
 WHERE pc.account_id=c.account_id AND paid.definition_key=r.definition_key AND paid.period_key=r.period_key
 AND paid.reward_index=r.reward_index AND paid.delivered_at IS NOT NULL));
-- Do not invent new awards for a completed historical row with no pending receipt.
UPDATE objectives_progress SET rewards_reserved=true WHERE completed_at IS NOT NULL;

-- Existing successful facts must not be re-credited through a different hero.
INSERT INTO objectives_account_sources(account_id,source_key,event_id)
SELECT DISTINCT ON(account_id,source_key) account_id,source_key,id FROM (
 SELECT account_id,id,CASE WHEN payload ? 'fight_id'
 THEN (payload->>'kind')||':fight:'||(payload->>'fight_id')
 ELSE (payload->>'kind')||':'||event_key END AS source_key
 FROM objectives_events WHERE processed_at IS NOT NULL
) facts ORDER BY account_id,source_key,id
ON CONFLICT DO NOTHING;
SELECT pg_notify('wakemu_objectives_updates','0');
