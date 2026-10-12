-- Hector-authorized local Gobball shepherd completion reward, including prior completions.
-- Reward policy is separate from immutable objective signatures.
INSERT INTO settings(name,value) VALUES ('custom_task_completion_reward_policies',
'[{"key":"gobball-shepherd-v1","task_key":"gobball-seeds-20","enabled":true,"kamas":1000000,"item_references":[2021,2025,2026,5309,5310],"item_quantity":1,"description":"Reward: 1,000,000 kamas and one random piece of Gobball equipment. Delivered automatically after completion."}]'::jsonb);
CREATE TABLE character_custom_task_policy_rewards (
    character_id bigint NOT NULL,
    task_key text NOT NULL,
    policy_key text NOT NULL CHECK (length(policy_key) BETWEEN 1 AND 128),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    materialized_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (character_id, task_key, policy_key),
    FOREIGN KEY (character_id,task_key)
        REFERENCES character_custom_task_progress(character_id,task_key) ON DELETE CASCADE
);
