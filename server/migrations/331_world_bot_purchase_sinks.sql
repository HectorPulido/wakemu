-- Opt-in headless buyers consume purchased goods and recover their own spending.
-- The exchange receipt, seller payment, sink and outbox share one transaction.
-- Definitions are replayable after an explicitly recorded online activation;
-- creating them never opts in a bot or changes an existing audit receipt.
CREATE TABLE IF NOT EXISTS world_bot_purchase_sinks (
    bot_id text PRIMARY KEY REFERENCES world_bots(bot_id),
    enabled boolean NOT NULL DEFAULT false,
    configured_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS world_bot_purchase_sink_receipts (
    exchange_id bigint NOT NULL REFERENCES player_exchange_receipts(exchange_id),
    bot_id text NOT NULL REFERENCES world_bots(bot_id),
    account_id bigint NOT NULL REFERENCES accounts(id),
    character_id bigint NOT NULL REFERENCES characters(id),
    receipt_revision bigint NOT NULL CHECK (receipt_revision > 0),
    refunded_kamas bigint NOT NULL CHECK (refunded_kamas >= 0),
    wallet_before bigint NOT NULL CHECK (wallet_before >= 0),
    wallet_after bigint NOT NULL CHECK (wallet_after >= wallet_before),
    removed_items jsonb NOT NULL CHECK (jsonb_typeof(removed_items) = 'array'),
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (exchange_id, bot_id),
    FOREIGN KEY (account_id, character_id) REFERENCES characters(account_id, id),
    CHECK (wallet_after::numeric - wallet_before::numeric = refunded_kamas::numeric)
);

-- Inventory capacity comes from the bot's real equipped native bags.
-- Enabling this policy never changes a container or grants synthetic slots.
DROP TRIGGER IF EXISTS configure_world_bot_purchase_sink ON world_bot_purchase_sinks;
DROP FUNCTION IF EXISTS configure_world_bot_purchase_sink();

CREATE OR REPLACE FUNCTION apply_world_bot_purchase_sink(
    p_exchange_id bigint, p_bot_id text
) RETURNS jsonb
LANGUAGE plpgsql AS $$
DECLARE
    trade player_exchanges%ROWTYPE;
    receipt player_exchange_receipts%ROWTYPE;
    buyer world_bots%ROWTYPE;
    previous world_bot_purchase_sink_receipts%ROWTYPE;
    unit inventory_items%ROWTYPE;
    incoming record;
    metadata_table text;
    metadata_key text;
    metadata_row jsonb;
    metadata_snapshot jsonb;
    removed jsonb := '[]'::jsonb;
    other_character bigint;
    bot_paid bigint;
    other_paid bigint;
    refund numeric;
    balance bigint;
    result jsonb;
BEGIN
    -- The exchange row serializes both live commit and explicit backfill/retry.
    SELECT * INTO STRICT trade FROM player_exchanges
      WHERE id = p_exchange_id FOR UPDATE;
    SELECT * INTO previous FROM world_bot_purchase_sink_receipts
      WHERE exchange_id = p_exchange_id AND bot_id = p_bot_id;
    IF FOUND THEN
        RETURN to_jsonb(previous);
    END IF;
    SELECT b.* INTO buyer FROM world_bots b
      JOIN world_bot_purchase_sinks s USING (bot_id)
      WHERE b.bot_id = p_bot_id AND s.enabled;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    IF trade.state <> 'committed' THEN
        RAISE EXCEPTION 'Buyer sink requires a committed exchange';
    END IF;
    IF NOT ((trade.inviter_id = buyer.character_id
             AND trade.inviter_account = buyer.account_id)
         OR (trade.invitee_id = buyer.character_id
             AND trade.invitee_account = buyer.account_id)) THEN
        RAISE EXCEPTION 'Buyer sink exchange ownership mismatch';
    END IF;
    other_character := CASE WHEN trade.inviter_id = buyer.character_id
                            THEN trade.invitee_id ELSE trade.inviter_id END;
    SELECT * INTO STRICT receipt FROM player_exchange_receipts
      WHERE exchange_id = p_exchange_id;
    IF receipt.revision <> trade.revision
       OR jsonb_typeof(receipt.transfers->'items') IS DISTINCT FROM 'array'
       OR jsonb_typeof(receipt.transfers->'offered_kamas') IS DISTINCT FROM 'object'
       OR (receipt.transfers->'offered_kamas'->>buyer.character_id::text) IS NULL
       OR (receipt.transfers->'offered_kamas'->>other_character::text) IS NULL THEN
        RAISE EXCEPTION 'Malformed buyer purchase receipt';
    END IF;
    bot_paid := (receipt.transfers->'offered_kamas'->>buyer.character_id::text)::bigint;
    other_paid := (receipt.transfers->'offered_kamas'->>other_character::text)::bigint;
    IF bot_paid < 0 OR other_paid < 0 THEN
        RAISE EXCEPTION 'Invalid buyer purchase currency';
    END IF;
    -- Cash gifts, reverse sales and barter are not purchases by this buyer.
    IF bot_paid = 0 OR other_paid <> 0
       OR jsonb_array_length(receipt.transfers->'items') = 0 THEN
        RETURN NULL;
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(receipt.transfers->'items') movement
        WHERE (movement->>'character_id')::bigint <> buyer.character_id
    ) THEN
        RETURN NULL;
    END IF;
    refund := bot_paid::numeric - other_paid::numeric;
    SELECT kamas INTO STRICT balance FROM account_wallets
      WHERE account_id = buyer.account_id FOR UPDATE;
    IF balance::numeric + refund >= 9223372036854775808::numeric THEN
        RAISE EXCEPTION 'Buyer purchase refund exceeds currency limit';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(receipt.transfers->'items') movement
        WHERE jsonb_typeof(movement) <> 'object'
           OR (movement->>'received_uid') IS NULL
           OR (movement->>'quantity') IS NULL
           OR (movement->>'character_id') IS NULL
           OR (movement->>'received_uid')::bigint <= 0
           OR (movement->>'quantity')::bigint NOT BETWEEN 1 AND 32767
    ) THEN
        RAISE EXCEPTION 'Invalid buyer purchase item movement';
    END IF;
    FOR incoming IN
        SELECT (movement->>'received_uid')::bigint AS uid,
               sum((movement->>'quantity')::bigint) AS quantity
        FROM jsonb_array_elements(receipt.transfers->'items') movement
        GROUP BY (movement->>'received_uid')::bigint
        ORDER BY (movement->>'received_uid')::bigint
    LOOP
        SELECT * INTO unit FROM inventory_items
          WHERE uid = incoming.uid FOR UPDATE;
        IF NOT FOUND OR unit.character_id <> buyer.character_id
           OR unit.quantity::numeric < incoming.quantity THEN
            RAISE EXCEPTION 'Purchased buyer unit is missing, foreign or insufficient';
        END IF;
        metadata_snapshot := '{}'::jsonb;
        -- Match the complete per-UID custody contract before any FK cascades.
        FOREACH metadata_table IN ARRAY ARRAY[
            'inventory_item_elements', 'inventory_item_shards',
            'inventory_mounts', 'inventory_pets', 'inventory_item_bindings',
            'inventory_item_recycling_state', 'inventory_item_appearances',
            'inventory_item_companions', 'random_item_use_counters'
        ] LOOP
            metadata_key := CASE WHEN metadata_table = 'random_item_use_counters'
                                 THEN 'source_uid' ELSE 'uid' END;
            metadata_row := NULL;
            EXECUTE format('SELECT to_jsonb(t) FROM %I t WHERE %I = $1 FOR UPDATE',
                           metadata_table, metadata_key)
              INTO metadata_row USING unit.uid;
            IF metadata_row IS NOT NULL THEN
                metadata_snapshot := metadata_snapshot
                  || jsonb_build_object(metadata_table, metadata_row);
            END IF;
        END LOOP;
        removed := removed || jsonb_build_array(jsonb_build_object(
            'received_uid', unit.uid,
            'removed_quantity', incoming.quantity,
            'remaining_quantity', unit.quantity::numeric - incoming.quantity,
            'inventory_before', to_jsonb(unit),
            'custody_metadata', metadata_snapshot
        ));
        IF unit.quantity::numeric = incoming.quantity THEN
            DELETE FROM inventory_items WHERE uid = unit.uid;
        ELSE
            UPDATE inventory_items
              SET quantity = (unit.quantity::numeric - incoming.quantity)::smallint
              WHERE uid = unit.uid;
        END IF;
    END LOOP;
    -- Only the opted-in bot's authoritative wallet receives its exact spending.
    UPDATE account_wallets SET kamas = (balance::numeric + refund)::bigint
      WHERE account_id = buyer.account_id;
    INSERT INTO world_bot_purchase_sink_receipts(
        exchange_id, bot_id, account_id, character_id, receipt_revision,
        refunded_kamas, wallet_before, wallet_after, removed_items
    ) VALUES (
        p_exchange_id, p_bot_id, buyer.account_id, buyer.character_id,
        receipt.revision, refund::bigint, balance,
        (balance::numeric + refund)::bigint, removed
    ) RETURNING to_jsonb(world_bot_purchase_sink_receipts.*) INTO result;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION consume_world_bot_committed_purchase() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    bot_identity text;
BEGIN
    FOR bot_identity IN
        SELECT b.bot_id FROM world_bots b
          JOIN world_bot_purchase_sinks s USING (bot_id)
          WHERE s.enabled AND b.character_id IN (NEW.inviter_id, NEW.invitee_id)
          ORDER BY b.bot_id
    LOOP
        PERFORM apply_world_bot_purchase_sink(NEW.id, bot_identity);
    END LOOP;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS consume_world_bot_committed_purchase ON player_exchanges;
CREATE TRIGGER consume_world_bot_committed_purchase
AFTER UPDATE OF state ON player_exchanges
FOR EACH ROW WHEN (OLD.state IS DISTINCT FROM NEW.state AND NEW.state = 'committed')
EXECUTE FUNCTION consume_world_bot_committed_purchase();
