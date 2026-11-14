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

## File operation variants
All paths are relative to public_html. `GET files?path=folder` lists up to 5000 entries. POST actions:
- `{"action":"read","path":"file"}` returns `{ "content": "BASE64" }`.
- `{"action":"write","path":"file","content":"BASE64"}` atomically creates/replaces an ordinary file, up to 1 MiB decoded bytes.
- `{"action":"mkdir","path":"folder"}` creates a directory.
- `{"action":"rename","path":"old","destination":"new"}` refuses existing destination.
- `{"action":"delete","path":"entry"}` permanently deletes an entry; directories must be empty.
- `{"action":"list","path":"folder"}` lists entry name/size/mode/UID/directory/symlink metadata.

There are no archive, chmod, recursive delete, arbitrary-root-path, exec, SQL or shell endpoints.

## Permission editing
POST /accounts/{id}/files also accepts action chmod, relative path and mode.
Allowed modes are 600, 640, 644, 700, 750 and 755. Existing account authorization
and CSRF checks apply. The tenant helper rejects symlinks, non-owned entries
and hardlinked regular files. Changing permissions can remove Nginx access.

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
| `/accounts/{id}/files` | GET, POST | File Manager with search, copy, move, archive/extract, Trash and website backup operations. |
| `/accounts/{id}/backup-schedule` | GET, POST | Website snapshots with interval 0, 24 or 168 hours and retain 1–10. |
| `/accounts/{id}/databases` | GET, POST | List databases and engines, or create, inspect size, reset password, import, export, download, delete export or delete a database. |
| `/accounts/{id}/tls` | GET, POST | List certificate status and document roots, or issue, upload or toggle HTTPS redirect. |
| `/accounts/{id}/dns?domain=…` | GET, POST | Administrator-only forward DNS. Save replaces the typed record list. |
| `/accounts/{id}/site-security?domain=…` | GET, POST | List site protections or set/remove a directory password or save an IP blocklist. |
| `/accounts/{id}/metrics?domain=…` | GET | Show per-site access sample, or account processes when no domain is provided. |
| `/accounts/{id}/php` | GET, POST | Read and set pool parameters. GET with `?view=log` returns the error tail. |
| `/accounts/{id}/git` | POST | Queue public HTTPS source staging to a new folder. |
| `/accounts/{id}/wordpress` | POST | Install into an HTTPS website using an empty account database. |
| `/accounts/{id}/cron` | GET, POST | List, create or delete scheduled account PHP scripts. |

API tokens use `Authorization: Bearer <token>`. They permit GET on account
inventory, domain lists, stats and metrics. Use a session for every operation
with side effects. See [docs/HOSTING.md](docs/HOSTING.md) for host prerequisites.

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
