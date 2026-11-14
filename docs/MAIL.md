# Email hosting
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

almaPanel provisions virtual mailboxes and forwarders with Postfix and
Dovecot. Enable it on a clean Amazon Linux 2023 or Ubuntu 24.04 evaluation
host that already runs almaPanel. Start with a separate test domain.

## Set up the service

Choose a dedicated hostname such as `mail.example.com`. Obtain a TLS
certificate that covers it and keep the private key on the server. The
following paths assume Certbot issued the certificate. Change them if
you obtained it another way.

```bash
sudo bash installer/enable-mail.sh mail.example.com \
  /etc/letsencrypt/live/mail.example.com/fullchain.pem \
  /etc/letsencrypt/live/mail.example.com/privkey.pem
```

The script verifies the certificate name, expiration and key pair, configures
Postfix and Dovecot, and checks both processes and their listeners. It refuses
existing mail configurations when setting up the service for the first time.
If a setup attempt fails, inspect the service journal and rerun the command
with the same hostname. On the first run, all three listeners bind to
127.0.0.1. Append `--public` to listen on external IPv4 interfaces or
`--loopback` to switch back to local testing.

The service handles IPv4. At your DNS provider, point the mail hostname's
A record to the instance’s stable public IPv4 address and point each enabled
domain’s MX record to that hostname. Configure reverse DNS with the address
provider if you send mail to public recipients. Allow TCP 25 for receiving
server-to-server mail. Allow TCP 587 and 993 from your users' networks and
keep the panel’s SSH access rules. Manage the AWS security groups and host
firewall separately.

On EC2, public outbound TCP 25 requires AWS approval for direct delivery.
This adapter sends directly through Postfix. An authenticated relay needs
separate configuration and verification. Configure SPF, DKIM signing and
DMARC before evaluating public delivery. Automatic DKIM and DMARC management,
spam filtering, webmail and public delivery acceptance are open items.

## Use Email Accounts

1. Choose an active hosting account and add its domain under **Domains**.
   Account users and resellers need the DNS TXT ownership proof used for site TLS.
2. Open **Email Accounts** and enable local mail for the domain. Check the
   domain’s MX record before switching production DNS.
3. Create a mailbox with a unique password and a quota from 1 to 512 MiB.
   Use an address in an enabled domain to create a forwarder. The destination
   must be a lowercase email address. The panel validates managed alias chains.
4. In your mail app, sign in with the full email address and mailbox password.
   Set the incoming server to IMAP over TLS on port 993. Set the outgoing
   server to authenticated SMTP submission with STARTTLS on port 587.
5. Send to and receive from an independent test mailbox.

Port 25 rejects unauthenticated relaying. Authenticated submission checks
the envelope sender against the mailbox address. Message header enforcement
and signing are separate. Forwarders follow normal SMTP delivery and relay
connectivity requirements. External forwarding may fail DMARC at the
destination without a forwarding-aware mail policy.
Website applications should use authenticated SMTP submission. The system
`sendmail` entry point is restricted to root.

Disabling a mailbox prevents new authentication and delivery. Archiving
also discards the password hash. Restore sets a new password and uses the
same data directory. Existing IMAP sessions may remain open. Archived
addresses count towards the 20-mailbox hosting account limit and stay reserved
for restoration. If a domain is reassigned to a different hosting account,
its previous mail stays in the former account's storage directory. Re-enable
the domain before restoring a mailbox.

## Certificate renewal, storage and testing

Rerun the setup command with the current certificate chain and key and the
same hostname after renewal. Omitting the listener flag reuses the saved
mode. This updates the copies used by both services and restarts them.
Test renewal manually before adding a deploy hook.

Mailbox data live under `/var/vmail/<account>/<domain>/<local-part>/Maildir`.
The mail services use a dedicated OS identity shared between virtual
mailboxes. Authentication and delivery use the account-specific directory
registered by the root agent. Tenant web accounts have no direct access to
that directory. Website and panel snapshots do not contain Maildir data.
The root registry and the Dovecot passwd file contain password hashes.
Store backups of this state as credentials and verify mail recovery separately.

```bash
sudo journalctl -u postfix -u dovecot --since today
sudo postfix check
sudo postqueue -p
```

On a disposable Amazon Linux 2023 systemd VM, run
`sudo env ALMA_DISPOSABLE_VM=YES ALMA_TEST_MAIL=YES bash tests/installation/amazon_vm.sh`.
It uses a local certificate and loopback SMTP and IMAP to exercise delivery
and access checks. Public delivery, reboot and distro acceptance remain open.

See [AWS port 25 restrictions](https://repost.aws/knowledge-center/ec2-port-25-throttle).
