INSERT INTO settings(name,value) VALUES ('chat_channel_policy',
 '{"version":1,"language_mask":6,"community":4,"maximum_bytes":2048,"minimum_interval_ms":200}'::jsonb);

CREATE TABLE account_chat_preferences (
 account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
 language_mask smallint NOT NULL CHECK(language_mask BETWEEN 1 AND 15),
 community smallint NOT NULL CHECK(community BETWEEN 1 AND 4)
);
