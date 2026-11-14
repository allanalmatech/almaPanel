# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Render managed Nginx sites and validate certificate inputs."""
from datetime import datetime, timezone
import ipaddress
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
from urllib.parse import urlsplit

from backend.core import domain, name
from agent import metrics

ACME_ROOT = Path('/srv/almapanel/acme')
NGINX_DIR = Path('/etc/nginx/conf.d')
TLS_DIR = Path('/etc/almapanel/site-tls')
LE_DIR = Path('/etc/almapanel/acme/config/live')
CERTBOT = Path('/usr/bin/certbot')
ROOT_PART = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}(?:\.[A-Za-z0-9_-]{1,20})?\Z')
REDIRECT = re.compile(r"https?://[A-Za-z0-9._~:/?&=+%#@!(),-]{1,1500}\Z")
CERTIFICATE = re.compile(r'(?:-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\s*){1,10}\Z')
PRIVATE_KEY = re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=\r\n]+-----END (?:RSA |EC )?PRIVATE KEY-----\s*\Z')


def docroot(value):
    if value in (None, ''):
        return ''
    if (not isinstance(value, str) or len(value) > 256 or
            not all(ROOT_PART.fullmatch(part) for part in value.split('/'))):
        raise ValueError('Document root must be a safe relative folder inside public_html.')
    return value


def site_path(host):
    return NGINX_DIR / f'alma-{domain(host)}.conf'


def site_for(meta, host):
    return meta.get('sites', {}).get(host, {})


def primary(meta):
    hosts = meta.get('domains', ())
    chosen = meta.get('primary')
    if chosen in hosts and site_for(meta, chosen).get('kind', 'site') == 'site':
        return chosen
    return next((host for host in hosts if site_for(meta, host).get('kind', 'site') == 'site'), None)


def overlaps(first, second):
    return (not first or not second or first == second or
            first.startswith(second + '/') or second.startswith(first + '/'))


def settings(meta, host, request):
    kind = request.get('kind', 'site')
    root = ''
    target = ''
    if kind == 'site':
        root = docroot(request.get('root', ''))
    elif kind == 'alias':
        target = domain(request.get('target'))
        if (target == host or target not in meta['domains'] or
                site_for(meta, target).get('kind', 'site') != 'site' or site_for(meta, target).get('privacy')):
            raise ValueError('Choose an existing website in this account as the alias target.')
    elif kind == 'redirect':
        target = request.get('target')
        if not isinstance(target, str) or not REDIRECT.fullmatch(target):
            raise ValueError('Enter a valid HTTP or HTTPS redirect URL.')
        parsed = urlsplit(target)
        if not parsed.hostname or parsed.username is not None:
            raise ValueError('Redirect targets cannot contain credentials.')
        # Evaluating port also rejects invalid port syntax.
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError('Invalid redirect port.')
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            domain(parsed.hostname.lower())
        if parsed.hostname.lower() == host:
            raise ValueError('Redirect target must use a different hostname.')
    else:
        raise ValueError('Choose website, alias or redirect.')
    if kind == 'site':
        for other in meta['domains']:
            peer = site_for(meta, other)
            if other != host and peer.get('privacy') and overlaps(root, peer.get('root', '')):
                raise ValueError('This document root overlaps a password-protected website.')
    current = site_for(meta, host)
    if current.get('privacy') and (kind != 'site' or root != current.get('root', '')):
        raise ValueError('Remove directory privacy rules before changing this website’s document root or type.')
    if kind != 'site' and any(site_for(meta, other).get('target') == host
                              and site_for(meta, other).get('kind') == 'alias'
                              for other in meta['domains']):
        raise ValueError('This website still has aliases.')
    return {**current, 'kind': kind, 'root': root, 'target': target}


def certificate_paths(host, meta):
    domain(host)
    kind = site_for(meta, host).get('tls')
    if kind == 'acme':
        path = LE_DIR / host
        return path / 'fullchain.pem', path / 'privkey.pem'
    if kind == 'custom':
        path = TLS_DIR / host
        return path / 'chain.pem', path / 'key.pem'
    return None


def challenge(host):
    return (f' location ^~ /.well-known/acme-challenge/ {{\n'
            f'  root {ACME_ROOT}/{host};\n'
            '  default_type text/plain;\n'
            '  try_files $uri =404;\n'
            ' }\n')


def render(base, php_run, account, host, meta, suspended=False):
    name(account)
    domain(host)
    site = site_for(meta, host)
    paths = certificate_paths(host, meta)
    kind = site.get('kind', 'site')
    if suspended:
        content = ' location / { return 503; }\n'
    elif kind == 'redirect':
        redirect = settings(meta, host, site)['target']
        content = f' location / {{ return 302 "{redirect}"; }}\n'
    else:
        parent = site_for(meta, site['target']) if kind == 'alias' else site
        relative = docroot(parent.get('root'))
        root = base / account / 'public_html'
        if relative:
            root /= relative
        content = (
            f' root {root};\n'
            ' index index.php index.html;\n'
            f" client_max_body_size {(meta.get('php') or {}).get('upload_mib', 8) + 1}m;\n"
            ' disable_symlinks on;\n'
            + (' location / { try_files $uri $uri/ /index.php?$args; }\n'
             if parent.get('application', {}).get('type') == 'wordpress' else
             ' location / { try_files $uri $uri/ =404; }\n')
            + ' location ~ /\\. { deny all; }\n'
            ' location ~* \\.(?:bak|old|orig|sql|pgdump|log|ini)$ { deny all; }\n'
            ' location ~* \\.p(?:html|har|hp[0-9]+)$ { deny all; }\n'
            ' location ~ \\.php$ {\n'
            '  try_files $uri =404;\n'
            '  include fastcgi_params;\n'
            '  fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;\n'
            f'  fastcgi_pass unix:{php_run}/alma-{account}.sock;\n'
            ' }\n'
            ' location ~* \\.php$ { return 404; }\n'
        )
    http = content
    if paths and site.get('force_https') and not suspended:
        http = f' location / {{ return 301 https://{host}$request_uri; }}\n'
    from hashlib import sha256
    identifier = sha256(host.encode()).hexdigest()[:24]
    from agent.site_security import render as render_security
    maps, controls = render_security(host, site, identifier) if not suspended and kind == 'site' else ('', '')
    log_format = 'alma_' + identifier
    access = f' access_log {metrics.log_path(account, host)} {log_format};\n'
    format_line = (f"log_format {log_format} escape=json "
                   "'{\"time\":\"$time_iso8601\",\"method\":\"$request_method\","
                   "\"path\":\"$uri\",\"status\":\"$status\",\"bytes\":\"$body_bytes_sent\","
                   "\"client\":\"$remote_addr\"}';\n")
    if site.get('privacy') and not suspended and kind == 'site':
        # No Basic credentials are requested on plaintext HTTP.
        http = f' location / {{ return 301 https://{host}$request_uri; }}\n'
    http_controls = '\n'.join(line for line in controls.splitlines() if line.strip().startswith('deny ')) + '\n'
    result = maps + format_line + f'server {{\n listen 80;\n server_name {host};\n{access}{http_controls}{challenge(host)}{http}}}\n'
    if paths:
        cert, key = paths
        result += (f'server {{\n listen 443 ssl;\n server_name {host};\n{access}{controls}'
                   f' ssl_certificate {cert};\n ssl_certificate_key {key};\n'
                   ' ssl_protocols TLSv1.2 TLSv1.3;\n' + content + '}\n')
    return result


def certificate_status(host, meta, run):
    paths = certificate_paths(host, meta)
    if not paths:
        return {'state': 'none'}
    try:
        expiry = run(['/usr/bin/openssl', 'x509', '-in', str(paths[0]), '-noout', '-enddate'])
        expires = ssl.cert_time_to_seconds(expiry.strip().split('=', 1)[1])
        days = int((expires - datetime.now(timezone.utc).timestamp()) // 86400)
        return {'state': 'expired' if days < 0 else ('expiring' if days < 21 else 'active'),
                'days_remaining': days, 'expires': int(expires)}
    except (OSError, ValueError, IndexError, RuntimeError, subprocess.SubprocessError):
        return {'state': 'unreadable'}


def validate_certificate(host, certificate, key, run):
    domain(host)
    if (not isinstance(certificate, str) or not isinstance(key, str) or
            len(certificate) > 60000 or len(key) > 12000 or
            not CERTIFICATE.fullmatch(certificate) or not PRIVATE_KEY.fullmatch(key)):
        raise ValueError('Supply a PEM certificate chain and unencrypted PEM private key.')
    with tempfile.TemporaryDirectory(prefix='alma-tls-') as storage:
        chain = Path(storage) / 'chain.pem'
        private = Path(storage) / 'key.pem'
        chain.write_text(certificate)
        private.write_text(key)
        report = run(['/usr/bin/openssl', 'x509', '-in', str(chain), '-noout', '-checkhost', host])
        if 'does match certificate' not in report:
            raise ValueError('The certificate does not cover this hostname.')
        run(['/usr/bin/openssl', 'x509', '-in', str(chain), '-checkend', '0', '-noout'])
        public = run(['/usr/bin/openssl', 'x509', '-in', str(chain), '-pubkey', '-noout'])
        actual = run(['/usr/bin/openssl', 'pkey', '-in', str(private), '-passin', 'pass:', '-pubout'])
        if public != actual:
            raise ValueError('The certificate and private key do not match.')


def acme_argv(host, email):
    domain(host)
    if (not isinstance(email, str) or len(email) > 254 or
            not re.fullmatch(r'[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', email)):
        raise ValueError('Enter a valid ACME contact email address.')
    return [str(CERTBOT), 'certonly', '--config-dir', '/etc/almapanel/acme/config',
            '--work-dir', '/var/lib/almapanel-agent/acme-work',
            '--logs-dir', '/var/log/almapanel/acme', '--webroot',
            '--webroot-path', str(ACME_ROOT / host), '--cert-name', host,
            '--domain', host, '--email', email, '--non-interactive', '--agree-tos',
            '--keep-until-expiring', '--no-directory-hooks']
