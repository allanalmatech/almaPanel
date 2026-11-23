# API reference
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

Base: `/api`. Machine-readable specification: `docs/openapi.json`. Browser cookie auth and scoped read-only bearer tokens.

POST requires `Content-Type: application/json` and exact configured `Origin`. After login every POST also requires `X-CSRF-Token` returned by login or GET /me. Store secure HttpOnly cookie; do not use bearer tokens. Login/setup are per-IP throttled. Sessions last one hour. Queued operations return HTTP 200 with `state=queued`; only a succeeded job proves completion. Job failures are persisted, never transformed into success.

Errors use `{"error":"message"}`: 400 invalid input; 401 sign-in required; 403 role/CSRF/origin/token rejection; 404 missing or unauthorized resource; 405 method rejected; 409 uniqueness/allocation/state conflict; 413 body >1,500,000 bytes; 415 wrong content type; 429 throttled; 500 internal error; 502 agent operation failure; 503 agent unavailable. HTTP GET does not mutate resources. Unsupported endpoints return 404.

## GET `/health`
Check database/API health. Permissions: **Public**.

Response shape/example (illustrative, not live measurements):
```json
{
  "status": "ok",
  "version": "0.1.0-alpha.1"
}
```

## POST `/setup`
Create first administrator. Permissions: **Public + one-time setup token**.

Request:
```json
{
  "username": "admin",
  "password": "CHOOSE-AT-LEAST-14-CHARACTERS",
  "token": "TOKEN-FROM-SERVER"
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "message": "Administrator created. Sign in."
}
```

## POST `/login`
Create secure one-hour session. Permissions: **Public, rate-limited**.

Request:
```json
{
  "username": "admin",
  "password": "YOUR-PASSWORD"
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "csrf": "TOKEN"
}
```

## GET `/me`
Read own identity and CSRF token. Permissions: **Authenticated**.

Response shape/example (illustrative, not live measurements):
```json
{
  "id": 1,
  "username": "admin",
  "role": "admin",
  "csrf": "TOKEN",
  "last_ip": "203.0.113.7"
}
```

## POST `/logout`
Revoke current session. Permissions: **Authenticated**.

Request:
```json
{}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "message": "Signed out."
}
```

## POST `/password`
Change password, revoke all sessions. Permissions: **Authenticated + current password**.

Request:
```json
{
  "current": "OLD-PASSWORD",
  "password": "NEW-LONG-PASSWORD"
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "message": "Password changed. Sign in again."
}
```

## GET `/packages`
List global/owned packages. Permissions: **Authenticated, scoped**.

Response shape/example (illustrative, not live measurements):
```json
[
  {
    "id": 1,
    "name": "Small",
    "owner_id": null,
    "max_domains": 3
  }
]
```

## POST `/packages`
Create package. Permissions: **Admin or reseller**.

Request:
```json
{
  "name": "Small",
  "max_domains": 3
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "message": "Package created. Only domain-count limits are enforced in this release."
}
```

## GET `/resellers`
List resellers. Permissions: **Admin**.

Response shape/example (illustrative, not live measurements):
```json
[]
```

## POST `/resellers`
Create reseller login/allocation. Permissions: **Admin**.

Request:
```json
{
  "username": "reseller",
  "password": "CHOOSE-LONG-PASSWORD",
  "max_accounts": 5
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "message": "Reseller created."
}
```

## GET `/accounts`
List authorized hosting accounts. Permissions: **Authenticated, scoped**.

Response shape/example (illustrative, not live measurements):
```json
[]
```

## POST `/accounts`
Queue Linux hosting account. Permissions: **Admin or reseller within allocation**.

Request:
```json
{
  "username": "customer",
  "password": "CHOOSE-LONG-PASSWORD",
  "package_id": 1
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "job_id": 1,
  "state": "queued"
}
```

## GET `/jobs`
List 100 latest authorized jobs. Permissions: **Admin all; otherwise own actor**.

Response shape/example (illustrative, not live measurements):
```json
[]
```

## GET `/audit`
List 200 latest audit events. Permissions: **Admin**.

Response shape/example (illustrative, not live measurements):
```json
[]
```

## GET `/system`
Read live Linux statistics. Permissions: **Admin**.

Response shape/example (illustrative, not live measurements):
```json
{
  "load_average": [
    0.0,
    0.0,
    0.0
  ],
  "memory_total": 0,
  "memory_available": 0,
  "disk_total": 0,
  "disk_used": 0,
  "services": {},
  "hostname": "server"
}
```

## POST `/services`
Queue allowlisted restart. Permissions: **Admin + RESTART confirmation**.

Request:
```json
{
  "service": "nginx",
  "confirm": "RESTART"
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "job_id": 2,
  "state": "queued"
}
```

## POST `/accounts/{id}/state`
Queue active/suspended state. Permissions: **Admin or owning reseller**.

Request:
```json
{
  "state": "suspended"
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "job_id": 3,
  "state": "queued"
}
```

## POST `/accounts/{id}/retry-create`

An administrator or the owning reseller can queue a new provisioning job for
a failed or interrupted account. Send `{}` with the session and CSRF token.
The response is `{"job_id":4,"state":"queued"}`. GET `/accounts` includes
`can_retry` with `1` for rows with a retryable setup state and `0` otherwise.
The API returns 409 when the account cannot be retried or has an unfinished job.
The agent checks for conflicting Linux account resources before it provisions.

## GET `/accounts/{id}/domains`
List domains. Permissions: **Authorized active account**.

Response shape/example (illustrative, not live measurements):
```json
[]
```

## POST `/accounts/{id}/domains`
Queue HTTP virtual host. Permissions: **Authorized active account within package**.

Request:
```json
{
  "domain": "example.com"
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "job_id": 4,
  "state": "queued"
}
```

## GET `/accounts/{id}/stats`
Read real account disk size. Permissions: **Authorized active account**.

Response shape/example (illustrative, not live measurements):
```json
{
  "home": "/srv/almapanel/accounts/customer",
  "disk_bytes": 0,
  "domains": 0,
  "disk_quota_bytes": null,
  "cpu_percent": null,
  "memory_bytes": null,
  "bandwidth_bytes": null,
  "quota_note": "Disk/CPU/RAM quotas are not enforced in this alpha."
}
```

## GET `/accounts/{id}/files`
List directory; optional ?path=relative/path. Permissions: **Authorized active account**.

Response shape/example (illustrative, not live measurements):
```json
[]
```

## POST `/accounts/{id}/files`
Operate on files under tenant UID. Permissions: **Authorized active account**.

Request:
```json
{
  "action": "write",
  "path": "index.html",
  "content": "SGVsbG8="
}
```
Response shape/example (illustrative, not live measurements):
```json
{
  "message": "File saved."
}
```

## File Manager operations

All paths are relative to `public_html`. The account must be active and
accessible to the signed-in user. POST requests use the session and CSRF token.
`GET files?path=folder` keeps the unpaged directory-listing response.

| POST action | Request fields beside `action` | Result |
|---|---|---|
| `list_page` | `path`, optional `offset`, `include_hidden`, `folders_only` | `path`, `total`, `entries` and nullable `next_offset`. Entry fields include `name`, `size`, `mode`, `uid`, `gid`, `owner`, `group`, `modified` (Unix seconds), and type flags. |
| `search` | `path`, `query`, optional `include_hidden` | Matching paths and a `truncated` flag. |
| `read` | `path` | Base64 `content` and `revision` for a regular file up to 1 MiB. |
| `write` | `path`, base64 `content`, optional `create_only` or `expected_revision` | Save up to 1 MiB and return `message` and `revision`. `create_only` requires a new path and `expected_revision` checks an existing file. |
| `download` | `path`, `offset` (initially zero), `revision` (required for later chunks) | Base64 `content`, total byte `size`, `revision` and `done`. Ordinary downloads allow up to 256 MiB. |
| `mkdir`, `delete` | `path` | Create a folder or permanently delete one entry. Direct deletion of a folder requires it to be empty. |
| `copy`, `copy_tree`, `rename` | `path`, `destination` | Copy or move to an unused path. |
| `chmod` | `path`, `mode` as three octal digits | Change permission bits for an account-owned directory or ordinary file. |
| `archive`, `extract` | `path`, `destination` | ZIP a file or folder, or extract to a new folder. |
| `archive` with `names` | Folder `path`, `names` (1–500 entry names in that folder), `destination` | ZIP several selected entries into one archive. Each entry keeps its name, folders include their contents, and the shared 64 MiB and 5,000-entry limits apply. The destination cannot be inside a selected folder. |
| `archive_contents` | ZIP `path`, optional `query`, `offset`, `revision` | List ZIP member file paths and sizes. |
| `trash`, `trash_list` | Entry `path` for `trash` | Move an entry to private Trash, or list entry IDs and original paths. |
| `trash_restore`, `trash_purge` | Trash entry `id`, plus unused `destination` for restore | Restore or permanently remove an entry. |

### Multi-chunk upload

1. Send `{"action":"upload_start","path":"assets/photo.png","size":1310730}`.
   The response provides `upload_id`, `offset` and `chunk_bytes`.
2. Send `upload_chunk` with `upload_id`, byte `offset` and base64 `content`.
   The server returns the next offset. A retry at the same offset must match
   the bytes already stored there. Chunks are limited to 512 KiB in this build.
3. Send `upload_finish` with `upload_id` to publish the complete file, or
   `upload_cancel` to discard the stage. The server checks the original
   parent directory and refuses to replace an existing file.

A successful finish returns `message`, relative `path` and byte `size`.
The upload limit is 256 MiB. Permission errors, existing destinations and
revision conflicts return the agent error as JSON. Cross-account paths return
404 and missing or invalid CSRF credentials return 403.

## Alpha.3 hosting routes

The following paths are relative to `/api`. Mutations require the browser’s
session, correct Origin and CSRF token. `{id}` is an active hosting account the
caller may administer. Passwords, certificate private keys and supplied SQL
credentials go directly to the local agent and stay out of job payloads.

| Route | Method | Behavior |
|---|---|---|
| `/profile` | GET, POST | Read or save display name and contact email. |
| `/mfa` | GET, POST | Get status or begin, confirm or disable TOTP. Recovery codes are shown on confirmation only. |
| `/tokens` | GET, POST | List, create or revoke read-only bearer tokens. The token value is shown once. |
| `/accounts/{id}/domains` | GET, POST | List or create, edit, remove, select primary, generate DNS proof or verify it. Web changes are queued. |
| `/accounts/{id}/files` | GET, POST | File Manager with search, copy, move, archive/extract, Trash, website backup browse, integrity checks and restore. |
| `/accounts/{id}/backup-schedule` | GET, POST | Website snapshots with interval 0, 24 or 168 hours and retain 1–10. |
| `/accounts/{id}/databases` | GET, POST | List databases and engines, or create, inspect size, reset password, import, export, download, delete export or delete a database. |
| `/accounts/{id}/tls` | GET, POST | List certificate status and document roots, or issue, upload or toggle HTTPS redirect. |
| `/accounts/{id}/dns?domain=…` | GET, POST | Administrator-only forward DNS. Save replaces the typed record list. |
| `/accounts/{id}/mail?tool=…` | GET | `rules` (defaults, filters and autoresponders), `usage` (mailbox bytes), `track&query=` (72 hours of deliveries for the account's domains) or `deliverability&domain=` (MX, SPF and DMARC checks). |
| `/accounts/{id}/mail` actions `default`, `autoresponder`, `filters` | POST | `default`: `domain`, `target` (null rejects unknown addresses). `autoresponder`: `address`, `settings` (`subject`, `body`, `interval_days`, `start`, `end`) or null. `filters`: `scope` (mailbox or `account`) and `rules` (up to 25; `field`, `match`, `value`, `action` move/forward/discard, `target`). |
| `/accounts/{id}/site-options?domain=…` | GET, POST | Read website options, or `set` one `section`: `indexes` (folder list), `error_pages` (HTTP code to page path), `hotlink` (`enabled`, `allow_direct`, `allowed`, `extensions`, `redirect`), `mime` (extension to media type) or `optimize` (`compress`). Script extensions are refused. |
| `/accounts/{id}/site-security?domain=…` | GET, POST | List site protections or set/remove a directory password or save an IP blocklist. |
| `/accounts/{id}/metrics?domain=…` | GET | Show per-site access sample, or account processes when no domain is provided. |
| `/accounts/{id}/php` | GET, POST | Read and set pool parameters. GET with `?view=log` returns the error tail. |
| `/accounts/{id}/git` | POST | Queue public HTTPS source staging to a new folder. |
| `/accounts/{id}/wordpress` | POST | Install into an HTTPS website using an empty account database. |
| `/accounts/{id}/cron` | GET, POST | List, create or delete scheduled account PHP scripts. |

API tokens use `Authorization: Bearer <token>`. They permit GET on account
inventory, domain lists, stats and metrics. Use a session for every operation
with side effects. See [docs/HOSTING.md](docs/HOSTING.md) for host prerequisites.

### Selective website restore

Use POST with the session, CSRF token and the scoped account ID.

| Action | Request fields | Success fields |
| --- | --- | --- |
| `backup_contents` | Archive `path`, optional `query`, `offset` and `revision` | `entries` with file `path` and byte `size`, plus `total`, `next_offset` and `revision` |
| `backup_verify` | Archive `path`, optional `revision` | `message`, `files`, `bytes` |
| `backup_restore_file` | Archive `path`, source `member`, new `destination` under public_html and matching `revision` | `message` and restored `path` |

Use the revision from `backup_contents` when paging and restoring. The agent
reports stale or damaged archives and destination conflicts as 502 responses.
An account outside the caller’s scope returns 404.

### Off-site backup status

An administrator session can GET `/offsite-backups` for the latest recorded
website, database and managed DNS progress, outcome and update time. POST requests a background run
through the installed backup service. POST requires the panel Origin and CSRF
token. The response confirms submission of the request. Use GET to read the
backup outcome.

## SFTP, DNS Track and Notifications

- `GET /accounts/{id}/sftp` returns the listener state, username, port and
  registered public key fingerprints. POST accepts `action=add` with
  `public_key` and `label` or `action=remove` with `fingerprint`.
- `GET /dns-lookup?domain=example.com&type=A` returns answer records from
  the server’s public DNS resolver. The session is rate limited.
- `GET /notifications` lists up to 40 completed, failed or interrupted
  jobs in the caller’s role scope. POST accepts the job `id` to dismiss.

## Email Accounts

An active hosting account and a scoped panel session are required. POST
also requires the panel Origin and CSRF token.

- `GET /accounts/{id}/mail` returns the service availability, mail hostname,
  listener mode, enabled domains, mailbox metadata and forwarders.
- `POST /accounts/{id}/mail` accepts these actions.

| Action | Required fields |
| --- | --- |
| `domain` | `domain` and boolean `enabled`. The domain must belong to the account. Account users and resellers must verify ownership before enabling routing. |
| `create` | `address`, `password`, and integer `quota_mib` between 1 and 512. |
| `password`, `restore` | `address` and a new `password`. |
| `quota` | `address` and `quota_mib`. |
| `state` | `address` and boolean `enabled`. |
| `retire` | `address` and matching `confirm`. |
| `forward` | Source `address` and destination `target`. |
| `unforward` | Source `address`. |

The agent applies settings synchronously. Success returns `{"message":"Mail configuration saved."}`.
Unauthenticated calls get 401. An account or domain outside the caller's
scope returns 404. A suspended account or missing domain proof returns 409.
Agent-side validation and service errors return 502.
