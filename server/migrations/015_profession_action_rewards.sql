-- Explicit emulator balance, not a claim about official Wakfu rewards.
-- Only successful planting currently consumes this policy; failed/cancelled
-- actions never invoke the credit transaction.
INSERT INTO settings(name,value) VALUES
    ('profession_action_rewards', '{"version":1,"planting_xp":10,"harvest_xp":50,"recipe_slot_xp":100}'::jsonb);
