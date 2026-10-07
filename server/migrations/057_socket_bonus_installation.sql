-- Native 13269 carries changed slot -> (bonus reference, shard amount).
-- Installation consumption/refund and charge policy are local experiment rules.
INSERT INTO settings(name,value) VALUES (
 'socket_bonus_installation_policy',
 '{"version":1,"source":"local_policy_native_bonus_installation","enabled":true,"cost_kamas":0,"request_dedupe_ms":3000,"refund_on_decrease":false}'::jsonb
) ON CONFLICT(name) DO NOTHING;

CREATE TABLE inventory_socket_bonus_installation_receipts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL,
 uid bigint NOT NULL CHECK(uid>0),
 request_hash bytea NOT NULL CHECK(octet_length(request_hash)=32),
 policy_version integer NOT NULL CHECK(policy_version>0),
 result_state bytea NOT NULL CHECK(octet_length(result_state) BETWEEN 1 AND 65536),
 consumed jsonb NOT NULL CHECK(jsonb_typeof(consumed)='array'),
 cost_kamas bigint NOT NULL CHECK(cost_kamas>=0),
 applied_at timestamptz NOT NULL,
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id)
);
CREATE INDEX inventory_socket_bonus_installation_retry
 ON inventory_socket_bonus_installation_receipts(character_id,uid,request_hash,applied_at DESC);
