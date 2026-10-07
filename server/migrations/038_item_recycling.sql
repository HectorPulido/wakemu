INSERT INTO settings(name,value) VALUES
 ('recycling_policy','{"version":1,"rounding_mode":"stochastic_round","aggregation_mode":"sum_per_product_then_round","disabled_item_refs":[]}');

-- Preserve explicit server observations without pretending they are present in
-- ProtoItem. Missing unidentified state derives from the native template; an
-- absent socket UID map renders as no installed socket UID. Explicit occupied
-- socket state still blocks recycling conservatively.
CREATE TABLE inventory_item_recycling_state (
 uid bigint PRIMARY KEY REFERENCES inventory_items(uid) ON DELETE CASCADE,
 unidentified boolean,
 socketed boolean,
 CHECK(unidentified IS NOT NULL OR socketed IS NOT NULL)
);

-- A retry of the same selected UID set returns this committed outcome without
-- another random draw, deletion or product grant. Receipts survive UID cascade.
CREATE TABLE item_recycling_receipts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id),
 character_id bigint NOT NULL,
 request_hash bytea NOT NULL CHECK(octet_length(request_hash)=32),
 request_uids jsonb NOT NULL CHECK(jsonb_typeof(request_uids)='array'),
 recovered_resources integer NOT NULL CHECK(recovered_resources BETWEEN 0 AND 2147483647),
 destroyed_items integer NOT NULL CHECK(destroyed_items BETWEEN 0 AND 2147483647),
 products jsonb NOT NULL CHECK(jsonb_typeof(products)='object'),
 rounding_draws jsonb NOT NULL CHECK(jsonb_typeof(rounding_draws)='object'),
 applied_at timestamptz NOT NULL,
 FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id),
 UNIQUE(account_id,character_id,request_hash)
);
