-- Bilateral exchanges retain their identities and receipt after termination.
-- Active membership is separate, so completed trades do not occupy a player.
INSERT INTO settings(name,value) VALUES
 ('player_exchange_policy','{"version":1,"invitation_seconds":60,"maximum_offer_items":128}');

CREATE TABLE inventory_item_bindings (
 uid bigint PRIMARY KEY REFERENCES inventory_items(uid) ON DELETE CASCADE,
 bound boolean NOT NULL,
 template_reference integer NOT NULL CHECK(template_reference>0)
);

CREATE TABLE player_exchanges (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 inviter_id bigint NOT NULL,
 invitee_id bigint NOT NULL,
 inviter_account bigint NOT NULL,
 invitee_account bigint NOT NULL,
 inviter_generation text NOT NULL CHECK (length(inviter_generation)>0),
 invitee_generation text NOT NULL CHECK (length(invitee_generation)>0),
 state text NOT NULL DEFAULT 'invitation'
   CHECK(state IN ('invitation','active','committed','canceled','expired')),
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
 delivery_sequence bigint NOT NULL DEFAULT 1 CHECK(delivery_sequence>0),
 created_at timestamptz NOT NULL,
 expires_at timestamptz NOT NULL,
 FOREIGN KEY(inviter_account,inviter_id) REFERENCES characters(account_id,id),
 FOREIGN KEY(invitee_account,invitee_id) REFERENCES characters(account_id,id),
 CHECK(inviter_id!=invitee_id),
 CHECK(inviter_account!=invitee_account),
 CHECK(expires_at>created_at),
 UNIQUE(id,inviter_id),
 UNIQUE(id,invitee_id)
);
CREATE INDEX player_exchange_expiry ON player_exchanges(expires_at)
 WHERE state='invitation';

CREATE TABLE player_exchange_members (
 character_id bigint PRIMARY KEY REFERENCES characters(id),
 exchange_id bigint NOT NULL REFERENCES player_exchanges(id) ON DELETE CASCADE,
 offered_kamas bigint NOT NULL DEFAULT 0 CHECK(offered_kamas>=0),
 published_revision bigint NOT NULL DEFAULT 0 CHECK(published_revision>=0),
 confirmed_revision bigint CHECK(confirmed_revision>0),
 UNIQUE(exchange_id,character_id),
 CHECK(confirmed_revision IS NULL OR confirmed_revision=published_revision)
);

CREATE TABLE player_exchange_items (
 exchange_id bigint NOT NULL,
 character_id bigint NOT NULL,
 uid bigint NOT NULL,
 quantity smallint NOT NULL CHECK(quantity>0),
 PRIMARY KEY(exchange_id,uid),
 FOREIGN KEY(exchange_id,character_id)
   REFERENCES player_exchange_members(exchange_id,character_id) ON DELETE CASCADE
 -- No FK to inventory_items: a removed offered unit must invalidate at commit,
 -- not silently delete an offer or prevent ordinary inventory operations.
);

-- A membership must belong to this exchange's actual pair, not merely to any
-- valid character. Deferred checks permit terminal state + member deletion in
-- either order within one atomic transaction.
CREATE FUNCTION validate_player_exchange_membership() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE checked_id bigint;
BEGIN
 IF TG_TABLE_NAME='player_exchanges' THEN
   checked_id := NEW.id;
 ELSE
   checked_id := NEW.exchange_id;
 END IF;
 IF EXISTS (
   SELECT 1 FROM player_exchange_members m JOIN player_exchanges e ON e.id=m.exchange_id
   WHERE e.id=checked_id AND
    (m.character_id NOT IN(e.inviter_id,e.invitee_id)
     OR e.state NOT IN('invitation','active'))
 ) THEN
   RAISE EXCEPTION 'Invalid bilateral exchange membership'
     USING ERRCODE='23503';
 END IF;
 RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER player_exchange_member_pair
 AFTER INSERT OR UPDATE ON player_exchange_members
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
 EXECUTE FUNCTION validate_player_exchange_membership();
CREATE CONSTRAINT TRIGGER player_exchange_pair_members
 AFTER UPDATE ON player_exchanges
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
 EXECUTE FUNCTION validate_player_exchange_membership();

CREATE TABLE player_exchange_receipts (
 exchange_id bigint PRIMARY KEY REFERENCES player_exchanges(id),
 revision bigint NOT NULL CHECK(revision>0),
 committed_at timestamptz NOT NULL,
 transfers jsonb NOT NULL CHECK(jsonb_typeof(transfers)='object')
);

CREATE TABLE player_exchange_outbox (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 exchange_id bigint NOT NULL REFERENCES player_exchanges(id),
 revision bigint NOT NULL CHECK(revision>0),
 delivery_sequence bigint NOT NULL DEFAULT 1 CHECK(delivery_sequence>0),
 character_id bigint NOT NULL REFERENCES characters(id),
 generation text NOT NULL CHECK(length(generation)>0),
 event text NOT NULL CHECK(event IN ('snapshot','canceled','committed')),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL,
 delivered_at timestamptz,
 UNIQUE(exchange_id,delivery_sequence,character_id,event)
);
CREATE INDEX player_exchange_pending_delivery ON player_exchange_outbox(id)
 WHERE delivered_at IS NULL;
