-- Duel identity is the nominated actor, not a distinct account requirement.
DO $$
DECLARE
    rule record;
BEGIN
    FOR rule IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'friendly_duel_invitations'::regclass AND contype = 'c'
          AND pg_get_constraintdef(oid) = 'CHECK ((challenger_account_id <> target_account_id))'
    LOOP
        EXECUTE format('ALTER TABLE friendly_duel_invitations DROP CONSTRAINT %I', rule.conname);
    END LOOP;
END $$;
