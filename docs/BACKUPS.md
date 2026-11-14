# Website backup and recovery
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
and check its latest progress or failure. Repository configuration and restore
remain administrator CLI operations.
To schedule one run daily around 03:15 server time, run
`sudo bash installer/enable-offsite-backup.sh --daily` after a tested run.
Inspect the schedule with `systemctl list-timers almapanel-offsite-backup.timer`
and results with `sudo journalctl -u almapanel-offsite-backup.service`.

The job archives active and suspended accounts’ `public_html` trees under their
Linux identities. Budget space for temporary root-only ZIPs. The limit is
128 MiB of unpacked content and 5,000 entries per website, up to 100 hosting
accounts. Symlinks and special files cause that website snapshot to fail.
The website snapshot is file-level and can reflect ongoing writes. SQL,
Maildir, DNS and control-plane state are separate recovery work.

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

The policy is scoped to this host’s website snapshot path and does not run
repository-wide pruning. Plan restic prune and any immutable storage policy
separately. Keep deletion privileges out of routine backup jobs where your
storage policy permits it.

References [restic repositories](https://restic.readthedocs.io/en/v0.16.4/030_preparing_a_new_repo.html) and [retention](https://restic.readthedocs.io/en/v0.16.4/060_forget.html).
