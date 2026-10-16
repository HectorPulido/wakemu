"""Operator-only GameDock bridge verifies native credentials without logging in."""
import re
from . import player_auth


def launch(store, credentials):
    if type(credentials) is not dict or set(credentials) != {'username','password'}:
        raise ValueError('Expected native account credentials')
    username, password = credentials['username'], credentials['password']
    if (type(username) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{3,32}', username)
            or type(password) is not str or not 8 <= len(password) <= 256):
        raise ValueError('Invalid native account credentials')
    # Store.authenticate checks the password and access policy only. In particular,
    # it never calls begin_session, issues game tokens or replaces a World lease.
    try:
        account = store.authenticate(username, password)
    except ValueError:
        raise player_auth.Unauthorized('Native account verification failed') from None
    with store.connection() as db:
        identity = player_auth.resolve_account(db, {'account_id': account['id']})
        token = player_auth.issue_embed(db, account['id'], identity['character_id'])
    return {'token': token, 'valid_days': 30}
