# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Optional live SMTP, LMTP and IMAP checks called by live_vm.py."""
from email.message import EmailMessage
import imaplib
import secrets
import smtplib
import ssl
import time


def accept(call, account_url, certificate):
    endpoint = account_url + '/mail'
    domain = 'acceptance.example.com'
    mailbox = 'test@' + domain
    alias = 'forwarder@' + domain
    password = secrets.token_urlsafe(28)
    assert call(endpoint)['available']
    call(endpoint, {'action': 'domain', 'domain': domain, 'enabled': True})
    call(endpoint, {'action': 'create', 'address': mailbox, 'password': password, 'quota_mib': 1})
    call(endpoint, {'action': 'forward', 'address': alias, 'target': mailbox})
    assert 'hash' not in call(endpoint)['mailboxes'][0]

    context = ssl.create_default_context(cafile=certificate)
    # The test certificate is pinned above. Its test hostname has no public DNS.
    context.check_hostname = False
    with smtplib.SMTP('127.0.0.1', 25, timeout=10) as smtp:
        smtp.ehlo()
        assert not smtp.has_extn('auth')
        for recipient in ('recipient@example.net', 'unknown@' + domain):
            assert smtp.mail('source@example.net')[0] == 250
            assert smtp.rcpt(recipient)[0] >= 500, recipient
            smtp.rset()
    with smtplib.SMTP('127.0.0.1', 587, timeout=10) as smtp:
        smtp.ehlo()
        assert not smtp.has_extn('auth')
        smtp.starttls(context=context)
        smtp.ehlo()
        assert smtp.mail(mailbox)[0] in (250, 530)
        assert smtp.rcpt(alias)[0] >= 500, 'Submission allowed unauthenticated delivery.'
        smtp.rset()
        smtp.login(mailbox, password)
        smtp.mail('different@' + domain)
        assert smtp.rcpt(alias)[0] >= 500, 'Submission allowed another envelope sender.'
        smtp.rset()
        message = EmailMessage()
        message['From'] = mailbox
        message['To'] = alias
        message['Subject'] = 'almaPanel acceptance'
        message.set_content('Local test through Postfix and Dovecot.')
        assert smtp.send_message(message) == {}
    with imaplib.IMAP4_SSL('127.0.0.1', ssl_context=context, timeout=10) as imap:
        assert imap.login(mailbox, password)[0] == 'OK'
        for _ in range(20):
            _, count = imap.select('INBOX', readonly=True)
            if int(count[0]):
                break
            time.sleep(1)
        else:
            raise AssertionError('Forwarded test mail did not reach the mailbox.')
        message = b'MIME-Version: 1.0\r\nSubject: quota test\r\n\r\n' + (b'x' * 950 + b'\r\n') * 1250
        try:
            status, _ = imap.append('INBOX', None, None, message)
        except imaplib.IMAP4.error as error:
            assert 'OVERQUOTA' in str(error).upper(), error
        else:
            assert status == 'NO', 'An over-quota append succeeded.'
    call(endpoint, {'action': 'retire', 'address': mailbox, 'confirm': mailbox})
    with imaplib.IMAP4_SSL('127.0.0.1', ssl_context=context, timeout=10) as imap:
        try:
            imap.login(mailbox, password)
        except imaplib.IMAP4.error:
            pass
        else:
            raise AssertionError('Archived mailbox can still authenticate.')
    print('Live mail passed TLS, relay denial, sender ownership, forwarding, quota and archive checks.')
