-- Durable account-scoped social state. These rows are local emulator policy;
-- native account IDs and the contact-list carrier are protocol-derived.
CREATE TABLE account_social_preferences (
    account_id bigint PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    do_not_disturb boolean NOT NULL DEFAULT false
);

CREATE TABLE account_social_contacts (
    owner_account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    contact_account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    relation text NOT NULL CHECK (relation IN ('friend', 'ignore')),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (owner_account_id, contact_account_id),
    CHECK (owner_account_id <> contact_account_id)
);
CREATE INDEX account_social_contacts_by_contact
    ON account_social_contacts(contact_account_id, relation, owner_account_id);
