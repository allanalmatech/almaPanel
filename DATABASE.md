# Panel database
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

SQLite 3, foreign keys enabled, WAL journaling, ten-second busy timeout. Schema is `database/migrations/001_initial.sql`; `PRAGMA user_version=1`. SQL uses parameter binding. Connection context managers commit/rollback and always close. No production demo seed or hardcoded customer records.

| Table | Purpose | Relationships / invariants |
|---|---|---|
| users | Login hash, role, owner, enabled state, reseller cap | Username unique; owner_id -> users; roles constrained |
| sessions | SHA256 session ID, CSRF secret, expiry | user_id -> users; token primary key; expiry index |
| packages | Named domain-count allowance | owner_id -> users; NULL means administrator package; 1–100 domains |
| accounts | Hosting state and package assignment | Unique name/user_id; owner_id, package_id foreign keys; owner index |
| domains | Globally unique domain and provisioning status | account_id -> accounts |
| jobs | Operation, JSON arguments, state and result | actor_id/account_id foreign keys; state/id index |
| audit | Actor, action, target, originating IP, timestamp | Actor intentionally nullable for failed login |
| attempts | Login attempt counters and reset time | Keyed by remote IP; 15-minute windows |

No raw passwords stored. Password encodings use a random 16-byte salt and scrypt (N=16384, r=8, p=1). Sessions last one hour. Expired session rows are removed during login; rate-limit rows are expired during auth attempts. Audit/jobs do not yet have automated retention; operator must define/export a policy before production. Audit is not tamper-proof against a compromised control-plane UID.

A root-only JSON registry records actual Linux provisioning intents/state and domain ownership. It is not writable by the API and is not served as browser content. A consistency checker and reconciler are still required for automated recovery after split OS/DB failures.

Migration strategy: add numbered migrations with transaction/backup requirements and schema checks; do not edit 001 for an already deployed stable release. No automatic version-to-version upgrade is enabled in this alpha. Database snapshots use SQLite's online backup interface while panel services are stopped; restore requires the same schema/version and unchanged root registry. See DEPLOYMENT.md.
