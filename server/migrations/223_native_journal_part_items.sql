-- Qualified journal assembly; objective provenance is recorded without fabricating quest progress.
CREATE TABLE native_journal_part_item_actions (
 item_ref integer PRIMARY KEY,
 action_id integer NOT NULL UNIQUE CHECK(action_id>0),
 policy text NOT NULL CHECK(policy='supported_inference_wakemu_native_journal_part'),
 source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$')
);
INSERT INTO native_journal_part_item_actions VALUES
(20423,8054,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20424,8055,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20425,8056,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20426,8057,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20427,8058,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20428,8059,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20430,8061,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20431,8062,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20433,8064,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20434,8065,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20435,8066,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20436,8067,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20437,8068,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20438,8069,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7'),
(20439,8070,'supported_inference_wakemu_native_journal_part','6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7');
CREATE TABLE item_set_assembly_receipts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 account_id bigint NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
 character_id bigint NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 source_uid bigint NOT NULL CHECK(source_uid>0),
 policy text NOT NULL,
 fact jsonb NOT NULL CHECK(jsonb_typeof(fact)='object'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX item_set_assembly_receipts_character ON item_set_assembly_receipts(character_id,id);
