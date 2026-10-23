"""Retry absolute national state only after an owned revision changes."""


class SelectedNationalProgression:
    def __init__(self):
        self.published = None

    def refresh(self, store, account_id, generation, character_id, *, publish):
        with store.connection() as db:
            row = db.execute(
                "SELECT a.revision,n.nation_id FROM sessions s "
                "LEFT JOIN character_national_authority a ON a.character_id=s.character_id AND a.account_id=s.account_id "
                "LEFT JOIN character_chat_nations n ON n.character_id=s.character_id "
                "WHERE s.account_id=%s AND s.generation=%s AND s.character_id=%s AND s.expires_at>%s",
                (account_id, generation, character_id, store.now()),
            ).fetchone()
            if row is None:
                raise ValueError("National publication belongs to a replaced session")
            token = (
                account_id,
                generation,
                character_id,
                row["revision"],
                row["nation_id"],
            )
            if self.published == token:
                return False
            saved = store.character(account_id, character_id, db)
        if not store.current_character_session(account_id, generation, character_id):
            raise ValueError("National publication lease changed before delivery")
        if not publish(saved):
            return False
        self.published = token
        return True
