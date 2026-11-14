# Signed updates

From the trusted checkout on the server, run `sudo bash installer/enable-updates.sh`
once. It installs the dashboard controls under **Server information → Software
updates**. The upgrade keeps the existing database, TLS certificate and customer
files. It briefly stops the panel processes.

The release publisher generates an Ed25519 signing key once on a trusted
publishing machine. Keep the private key outside this repository and off the
hosting server.

```bash
openssl genpkey -algorithm ED25519 -out almapanel-release-private.pem
chmod 600 almapanel-release-private.pem
openssl pkey -in almapanel-release-private.pem -pubout -out almapanel-release-public.pem
```

Transfer the public key to the hosting server through a trusted channel. Then
enroll it and turn on the timer:

```bash
sudo install -o root -g root -m 644 almapanel-release-public.pem /etc/almapanel/update-public.pem
sudo systemctl enable --now almapanel-update.timer
```

For each compatible release, increment VERSION, review and test the checkout,
then build and sign it using the same signing key:

```bash
python3 scripts/build_update.py
openssl pkeyutl -sign -rawin -inkey /secure/path/almapanel-release-private.pem \
  -in dist/manifest.json -out dist/manifest.sig
```

Attach all three files to the GitHub Release set as the repository's latest
release: `almapanel-update.tar.gz`, `manifest.json` and `manifest.sig`. GitHub's
latest-download URL must resolve to that release. A commit, tag or draft alone
does not qualify. Installations check every 15 minutes with up to one minute of
jitter. Administrators can also request an immediate check.

This channel updates only application code with database schema version 1 and
the existing service layout. Updates to the OS, dependencies, installer, trust
key, or database schema require a separate reviewed upgrade. Sign only releases
that preserve these contracts. On startup or health check failure, the updater
restores the previous application files. After a power interruption, the next
check attempts recovery. Review failures with
`sudo journalctl -u almapanel-update.service -n 50 --no-pager`.
