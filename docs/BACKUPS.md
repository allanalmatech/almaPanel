# Off-site backup and recovery
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

## Restore from the panel

Under **Website Backups**, choose **Browse files**, search the archive and
verify it if needed. To recover one file, choose **Restore file** and enter
an unused path in an existing folder under `public_html`. To extract the
whole archive, use **Restore into folder** and give it a new folder name.
Review recovered files before publishing them from a website document root.

Verification reads each regular file and checks its recorded ZIP integrity
and size. Selective restoration verifies the chosen file before publishing
it to the requested path. Existing files and symlinked directories are
protected by the same account boundaries used by File Manager.

## Set up encrypted off-site storage

From the installed source checkout, run:

```bash
sudo bash installer/enable-offsite-backup.sh
sudoedit /etc/almapanel/offsite-backup/repository.json
```

The setup uses the configured OS repository if it provides restic. If restic
is unavailable, install a maintained upstream binary for your architecture
after verifying its published checksum and signature. Put the verified binary
at `/usr/local/bin/restic`, owned by root and mode 0755, and rerun setup.
The service accepts restic 0.16-compatible commands.

The configuration directory must be root-owned and mode 0700. Give the
following file mode 0600 and use a unique, stable `host` label for the server.
Keep a copy of that label and the repository password in your recovery records.

```json
{
  "repository": "s3:https://s3.eu-north-1.amazonaws.com/YOUR-BUCKET/almapanel",
  "host": "alma-host-01"
}
```

Use an existing dedicated bucket or prefix with scoped permissions. Supply
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in a root-owned 0600 JSON
file named `s3.json` in the same directory. Optional fields include
`AWS_SESSION_TOKEN`, `AWS_REGION` and `AWS_DEFAULT_REGION`. This workflow
uses credentials held by the administrator on the shared hosting server.
Keep them out of shell arguments and source control.

For SFTP, set `repository` to `sftp://backupuser@backup.example.com/remote/path`
and place the dedicated private key in `sftp-key` and its verified remote
host entry in `known_hosts`. Both files must be root-owned and mode 0600.
The SSH transport uses batch mode and checks the pinned host key.
For local testing set `repository` to an existing root-owned 0700 directory
outside the hosting and staging trees.

Create the encryption password file once and keep a separate secure copy.

```bash
sudo bash -c 'set -o noclobber; umask 077; openssl rand -hex 32 > /etc/almapanel/offsite-backup/password'
sudo bash /opt/almapanel/installer/backup.sh --offsite init
sudo bash /opt/almapanel/installer/backup.sh --offsite snapshot
sudo bash /opt/almapanel/installer/backup.sh --offsite check --read-data
sudo bash /opt/almapanel/installer/backup.sh --offsite list
```

Use `init` only for a new repository. Use `check` for a previously initialized
repository. Restic stores encrypted snapshots and deduplicates data across them.
Open **Off-site Backups** from the administrator dashboard to start a snapshot
and check its latest progress or failure. The snapshot covers website files
and the managed databases that an administrator has enrolled. Configure the
repository, enroll databases, and recover archives from the server CLI.
To schedule one run daily around 03:15 server time, run
`sudo bash installer/enable-offsite-backup.sh --daily` after a tested run.
Inspect the schedule with `systemctl list-timers almapanel-offsite-backup.timer`
and results with `sudo journalctl -u almapanel-offsite-backup.service`.

The job archives active and suspended accounts’ `public_html` trees under their
Linux identities. Budget space for temporary root-only ZIPs. The limit is
128 MiB of unpacked content and 5,000 entries per website, up to 100 hosting
accounts. Symlinks and special files cause that website snapshot to fail.
Website snapshots are file-level and can reflect ongoing writes. Each enrolled
database is captured separately during the same backup run. Applications that
need a consistent point across files and several databases should pause writes
while the run completes. Maildir, DNS and control-plane backups remain separate.

## Enroll managed databases

Use the same account name and database label shown in **Databases**. The
command prompts for the current database owner password and verifies it
before adding the database to the next run.

```bash
sudo bash /opt/almapanel/installer/backup.sh --offsite database-include CUSTOMER DATABASE_LABEL
sudo bash /opt/almapanel/installer/backup.sh --offsite snapshot
sudo bash /opt/almapanel/installer/backup.sh --offsite list
```

Websites continue to be included by default. Enroll each SQL database you
want backed up. Re-enroll after changing the database password. Run
`database-exclude CUSTOMER DATABASE_LABEL` before deleting a managed
database. Historical encrypted dumps remain until their snapshots expire.
If an enrolled dump fails, the run fails before uploading the snapshot.

The server keeps enrolled credentials in a root-owned mode-0600 file at
`/var/lib/almapanel-offsite/database-logins.json`. The service runs dump
clients under the hosting account's Linux UID and supplies only that
database's login to the client. The encrypted backup manifest records
database names, dump sizes and checksums.

Capture is limited to 128 MiB per dump. MariaDB capture supports InnoDB
tables. Views, triggers, routines, events, sequences and other storage
engines cause the run to fail with a scope error. PostgreSQL uses custom
logical archives. Object ownership and grants follow the destination's
managed login. A restore can require compatible extensions and server
versions.

## Recover a database

List the databases in the selected snapshot. Use `restore-db` by itself
to download a verified dump into a root-only staging directory.

```bash
sudo bash /opt/almapanel/installer/backup.sh --offsite database-list FULL_SNAPSHOT_ID
sudo bash /opt/almapanel/installer/backup.sh --offsite restore-db FULL_SNAPSHOT_ID CUSTOMER DATABASE_LABEL
```

For an import, first create a separate, empty database in the same hosting
account with the same SQL engine. Provide its label and enter its password
when prompted.

```bash
sudo bash /opt/almapanel/installer/backup.sh --offsite restore-db FULL_SNAPSHOT_ID CUSTOMER DATABASE_LABEL --import-to NEW_LABEL
```

Keep applications disconnected from the empty destination until the import
finishes. PostgreSQL imports are transactional. MariaDB DDL can persist
after an import failure. If that happens, inspect the staged dump and create
another empty destination before retrial. Check restored rows before
pointing application traffic at the new database.

## Recover one website from off-site storage

Retrieve the full ID from `list`. The `restore` command writes one ZIP under
`/var/lib/almapanel-offsite/restore-*/`. To put it in an existing active
account’s private Website Backups, add `--import-to DESTINATION_ACCOUNT`.
Use the original host label when recovering from a replacement server.

```bash
sudo bash /opt/almapanel/installer/backup.sh --offsite restore FULL_SNAPSHOT_ID SOURCE_ACCOUNT --import-to DESTINATION_ACCOUNT
```

The import verifies the recovered ZIP and places it in the destination
account’s private backup list. In the panel, browse or restore from that
archive. Each successful CLI recovery leaves a root-only staged ZIP for
inspection. Remove staged copies according to your own disk retention policy.

Preview which snapshots a retention change would remove before applying it.

```bash
sudo bash /opt/almapanel/installer/backup.sh --offsite retention --keep-last 14
sudo bash /opt/almapanel/installer/backup.sh --offsite retention --keep-last 14 --apply
```

The policy applies to this host’s snapshots, including any database dumps
stored in them. Plan repository-wide pruning and any immutable storage policy
separately. Keep deletion privileges out of routine backup jobs where your
storage policy permits it.

References [restic repositories](https://restic.readthedocs.io/en/v0.16.4/030_preparing_a_new_repo.html) and [retention](https://restic.readthedocs.io/en/v0.16.4/060_forget.html).
