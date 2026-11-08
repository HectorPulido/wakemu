-- Bounded delivery of useful purchase errors through the native World chat.
CREATE TABLE shop_purchase_feedback (
    account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    character_id bigint NOT NULL,
    generation text NOT NULL,
    request_key text NOT NULL,
    revision bigint NOT NULL DEFAULT 1,
    expires_at timestamptz NOT NULL,
    delivered_at timestamptz,
    FOREIGN KEY(account_id,character_id) REFERENCES characters(account_id,id) ON DELETE CASCADE
);
