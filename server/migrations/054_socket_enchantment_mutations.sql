-- Versioned local economic/operation policy for native enchantment actions.
-- Values are experiment policy, not a claim about the upstream server.
INSERT INTO settings(name,value) VALUES (
 'socket_enchantment_policy',
 '{"version":1,"source":"local_policy_native_enchantment_request","enabled_operations":["add_charges","add_slot","change_slot_color","increase_count","change_colors","change_order","apply_sublimation","remove_sublimation"],"operation_kamas":{"add_charges":0,"add_slot":0,"change_slot_color":0,"increase_count":0,"change_colors":0,"change_order":0,"apply_sublimation":0,"remove_sublimation":0},"charge_gain_per_sacrifice":1,"charge_cap":255,"charge_costs":{"increase_count":1,"change_colors":1,"change_order":1},"same_reference_sacrifice":true,"sublimation_refund_bp":0,"sublimation_rules":{},"request_dedupe_ms":3000}'::jsonb
) ON CONFLICT(name) DO NOTHING;

-- Native request bodies have no request nonce. Sacrifice actions are
-- permanently deduplicated by their consumed ingredient UID; requests without
-- an ingredient use a short configurable retry window, after which an
-- identical workshop action is accepted as a new user action.
CREATE TABLE inventory_socket_enchantment_receipts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL,
 uid bigint NOT NULL CHECK(uid>0),
 operation text NOT NULL CHECK(operation IN (
   'add_charges','add_slot','change_slot_color','increase_count',
   'change_colors','change_order','apply_sublimation','remove_sublimation')),
 request_hash bytea NOT NULL CHECK(octet_length(request_hash)=32),
 prior_state_hash bytea NOT NULL CHECK(octet_length(prior_state_hash)=32),
 policy_version integer NOT NULL CHECK(policy_version>0),
 policy_hash bytea NOT NULL CHECK(octet_length(policy_hash)=32),
 result_state bytea NOT NULL CHECK(octet_length(result_state) BETWEEN 1 AND 65536),
 consumed_uid bigint,
 cost_kamas bigint NOT NULL CHECK(cost_kamas>=0),
 applied_at timestamptz NOT NULL,
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id),
 CHECK(consumed_uid IS NULL OR consumed_uid>0)
);
CREATE INDEX inventory_socket_enchantment_request_retry
 ON inventory_socket_enchantment_receipts(character_id,uid,operation,request_hash,applied_at DESC);
