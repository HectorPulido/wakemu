-- External objective evaluator; World remains the sole reward grant authority.
CREATE TABLE objectives_definitions (
 key text PRIMARY KEY, definition jsonb NOT NULL, revision integer NOT NULL DEFAULT 1,
 updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE objectives_events (
 id bigserial PRIMARY KEY, account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 event_key text NOT NULL, payload jsonb NOT NULL, signature text NOT NULL,
 definitions jsonb NOT NULL DEFAULT '[]'::jsonb,
 occurred_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 processed_at timestamptz, attempts integer NOT NULL DEFAULT 0, error text,
 UNIQUE(character_id,event_key)
);
CREATE INDEX objectives_events_pending ON objectives_events(id) WHERE processed_at IS NULL AND attempts<5;
CREATE TABLE objectives_progress (
 character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 definition_key text NOT NULL REFERENCES objectives_definitions(key), period_key text NOT NULL,
 definition_revision integer NOT NULL, counters jsonb NOT NULL DEFAULT '{}',
 completed_at timestamptz, updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(character_id,definition_key,period_key)
);
CREATE TABLE objectives_rewards (
 character_id bigint NOT NULL, definition_key text NOT NULL, period_key text NOT NULL,
 reward_index integer NOT NULL CHECK(reward_index>=0), payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP, delivered_at timestamptz,
 PRIMARY KEY(character_id,definition_key,period_key,reward_index),
 FOREIGN KEY(character_id,definition_key,period_key) REFERENCES objectives_progress ON DELETE CASCADE
);
CREATE INDEX objectives_rewards_pending ON objectives_rewards(character_id,created_at) WHERE delivered_at IS NULL;

-- Convert configured legacy objectives and policy rewards without losing receipts.
INSERT INTO objectives_definitions(key,definition)
SELECT rule->>'key',jsonb_build_object(
 'key',rule->>'key','title',rule->>'title','description',rule->>'description',
 'kind','task','enabled',rule->'enabled','prerequisite_keys','[]'::jsonb,
 'schedule','{"type":"once","timezone":"UTC"}'::jsonb,
 'objectives',jsonb_build_array(jsonb_build_object('key','count','event',rule->'predicate'->>'kind',
   'filters',(rule->'predicate')-'kind','target',rule->'target')),
 'rewards',COALESCE(rule->'rewards','[]'::jsonb)||COALESCE((
 SELECT jsonb_agg(reward ORDER BY policy_order,reward_order) FROM (
 SELECT policy_order,reward_order,reward
 FROM settings s2 CROSS JOIN LATERAL jsonb_array_elements(s2.value) WITH ORDINALITY AS policies(policy,policy_order)
 CROSS JOIN LATERAL (VALUES
 (0,jsonb_build_object('kind','kamas','amount',policy->'kamas')),
 (1,jsonb_build_object('kind','random_item','references',policy->'item_references','quantity',policy->'item_quantity'))
 ) AS entries(reward_order,reward)
 WHERE s2.name='custom_task_completion_reward_policies' AND policy->>'task_key'=rule->>'key' AND (policy->>'enabled')::boolean
 ) rewards),'[]'::jsonb))
FROM settings s CROSS JOIN LATERAL jsonb_array_elements(s.value) rule
WHERE s.name='custom_task_definitions';

INSERT INTO objectives_progress(character_id,definition_key,period_key,definition_revision,counters,completed_at,updated_at)
SELECT p.character_id,p.task_key,'once',1,jsonb_build_object('count',p.count),p.completed_at,p.updated_at
FROM character_custom_task_progress p JOIN objectives_definitions d ON d.key=p.task_key;
INSERT INTO objectives_events(account_id,character_id,event_key,payload,signature,occurred_at,processed_at)
SELECT c.account_id,e.character_id,e.event_key,e.payload,e.signature,e.created_at,e.created_at
FROM character_custom_task_events e JOIN characters c ON c.id=e.character_id;
INSERT INTO objectives_rewards(character_id,definition_key,period_key,reward_index,payload,created_at,delivered_at)
SELECT r.character_id,r.task_key,'once',r.reward_index,r.payload,r.created_at,r.delivered_at
FROM character_custom_task_reward_outbox r JOIN objectives_definitions d ON d.key=r.task_key;

CREATE TABLE objectives_definition_audit (
 id bigserial PRIMARY KEY,definition_key text NOT NULL,revision integer NOT NULL,
 operator text NOT NULL,definition jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE objectives_event_retries (
 id bigserial PRIMARY KEY,event_id bigint NOT NULL REFERENCES objectives_events(id),
 operator text NOT NULL,previous_attempts integer NOT NULL,
 created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
