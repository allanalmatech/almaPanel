-- Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin','reseller','user')), owner_id INTEGER REFERENCES users(id),
 enabled INTEGER NOT NULL DEFAULT 1, created INTEGER NOT NULL,
 last_ip TEXT, max_accounts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
 csrf TEXT NOT NULL,expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS packages (id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,
 owner_id INTEGER REFERENCES users(id), max_domains INTEGER NOT NULL CHECK(max_domains BETWEEN 1 AND 100));
CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
 name TEXT NOT NULL UNIQUE,owner_id INTEGER NOT NULL REFERENCES users(id),
 package_id INTEGER NOT NULL REFERENCES packages(id),state TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS domains (id INTEGER PRIMARY KEY,account_id INTEGER NOT NULL REFERENCES accounts(id),
 name TEXT NOT NULL UNIQUE,state TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY,actor_id INTEGER NOT NULL REFERENCES users(id),
 account_id INTEGER REFERENCES accounts(id),operation TEXT NOT NULL,payload TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'queued',result TEXT,created INTEGER NOT NULL,finished INTEGER);
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY,actor_id INTEGER,action TEXT NOT NULL,
 target TEXT NOT NULL,ip TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY,count INTEGER NOT NULL,reset INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_job_state ON jobs(state,id);
CREATE INDEX IF NOT EXISTS idx_accounts_owner ON accounts(owner_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires);
PRAGMA user_version=1;
