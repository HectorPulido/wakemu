# Account bans readiness audit

Permanent and timed sanctions already share the durable account guard with password authentication, token issuance/redemption and game session creation. Banning atomically deletes all token kinds and the account's session lease, then audits the change. Unbanning or expiry permits fresh authentication; deleted tokens and generations are never resurrected. World idle health observes the missing lease and disconnects the account connection, including its active heroes. The dashboard uses English labels/errors, mandatory reasons, optional timezone-qualified expiry, authenticated POST routes and CSRF checks.

## Concurrency correction

The original account guard used `SELECT ... FOR UPDATE` before revoking the session. Active gameplay locks its session first and may insert an account-owned row, acquiring PostgreSQL `KEY SHARE` for the account foreign key. `FOR UPDATE` blocks that FK lock while the sanction waits for the gameplay session, creating a lock cycle.

`account_bans.require_access`, `ban_account` and `unban_account` now use `FOR NO KEY UPDATE`. These guards still serialize with each other and account updates, but coexist with FK key-share checks. An operation already holding its lease finishes before the ban's lease deletion commits; later operations fail against the deleted lease. The guard never changes an account key, so the stronger lock was unnecessary.

The added regression holds a real session row lock, waits until the ban owns its account guard and is about to delete that session, then inserts an account-owned profession row. That insert must complete before releasing the session; afterward the ban must complete and new game-token issuance must fail. A transaction-local lock timeout bounds failure under the old lock. Validation is delegated to Luna; source compilation passed.

No client, world dispatcher, combat or spell files changed. No service operation was performed for this correction. Migration119 and existing deployment evidence belong to the original feature; this new lock correction is source-only until a subsequent coordinated build.

## Deployment handoff

Follow `WORLD_COORDINATION.md`: obtain a complete stable-source acknowledgement, validate the complete current shared server and acquire the deployment lock. Then rebuild the full current `world` and `admin` images and recreate those existing services. Do not apply a source overlay over an older World image. The original bans feature requires migration119; the lock correction requires no new migration.

```sh
docker compose build world admin
docker compose up -d --no-deps world admin
docker compose ps world admin
curl --fail http://127.0.0.1:18084/health
```

The dashboard remains localhost-bound at `http://127.0.0.1:18084`. Verify the actual built/deployed source fingerprints contain the new account guard.

## Complete manual acceptance

Use a disposable player account and the existing separate administration credentials. Do not publish credentials or tokens in reports.

1. Log the player into the game and activate its heroes if configured. Open the administration dashboard, Accounts, search the exact disposable username and choose View account.
2. Enter reason `Manual account ban acceptance`; leave Ban until empty; choose Ban account. Expect `Account banned.`, Banned in the account list, and recorded operator/reason in Change history. The active game connection must close on its next session-health check; the hero account must not retain an independent active lease.
3. Try logging the player in again and reusing its old remember/API/game credentials. Access must fail. Another unbanned account must continue working.
4. Reopen View account, enter reason `Manual appeal acceptance`, choose Unban account. Expect `Account access restored.` and a fresh player login to work. Previously revoked tokens must still fail.
5. Ban the disposable account again with a reason and a local expiry two minutes ahead. Expect its converted timestamp/status in the editor. Before expiry, login fails; after expiry, a fresh login works. Old tokens remain invalid. The audit retains both sanction changes.
6. Submit without a reason or with a past expiry. Expect an English validation error and no additional session/token revocation. Finish with the disposable account unbanned and log out of the dashboard.

Existing real HTTP/TLS evidence is recorded in the main issue table. This audit does not replace authenticated graphical acceptance or assert that the newly changed lock mode is already deployed.

## Final automatic verification

Independent bans/auth/admin gate passed32/32, including both deterministic concurrency cases, with unchanged source and1–129 migration fingerprints. Evidence: `.runtime/local/verification-fast-20261011/account-bans/tests.log` and `fingerprints.json`. The correction is not deployed.
