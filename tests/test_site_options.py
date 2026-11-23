# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Website options: validation, rendering order, and real Nginx behavior when Nginx is installed."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from agent import metrics, site_options, sites


def site_meta(options=None, application=None):
    site = {'kind': 'site', 'root': '', 'options': options or {}}
    if application:
        site['application'] = {'type': application}
    return {'domains': ['shop.example.com'], 'sites': {'shop.example.com': site}}


class Validation(unittest.TestCase):
    def test_indexes(self):
        self.assertEqual(site_options.indexes(['/downloads', '/', '/downloads']), ['/', '/downloads'])
        for bad in (['downloads'], ['/../etc'], ['/a b'], ['//x'], ['/x;y'], '/x', ['/x'] * 21):
            with self.subTest(bad=str(bad)[:30]), self.assertRaises(ValueError):
                site_options.indexes(bad)

    def test_error_pages(self):
        self.assertEqual(site_options.error_pages({'404': '/errors/404.html', '500': ''}), {'404': '/errors/404.html'})
        for bad in ({'418': '/x.html'}, {'404': 'x.html'}, {'404': '/x.txt'}, {'404': '/../x.html'},
                    {'404': '/x.html;'}, {'404': 7}, []):
            with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                site_options.error_pages(bad)

    def test_hotlink(self):
        result = site_options.hotlink({'enabled': True, 'allowed': ['CDN.example.org', '*.partner.example'],
                                       'extensions': ['.JPG', 'png'], 'allow_direct': False})
        self.assertEqual(result['allowed'], ['*.partner.example', 'cdn.example.org'])
        self.assertEqual(result['extensions'], ['jpg', 'png'])
        for bad in ({'enabled': 'yes'}, {'enabled': True, 'extensions': ['php']}, {'enabled': True, 'extensions': ['phtml']},
                    {'enabled': True, 'extensions': ['jp g']}, {'enabled': True, 'extensions': []},
                    {'enabled': True, 'allowed': ['bad host']}, {'enabled': True, 'allowed': ['x.com;']},
                    {'enabled': True, 'redirect': 'javascript:alert(1)'},
                    {'enabled': True, 'redirect': 'https://user:pw@example.com/'},
                    {'enabled': True, 'redirect': 'https://example.com/"; return 200'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                site_options.hotlink(bad)

    def test_mime(self):
        self.assertEqual(site_options.mime({'.FOO': 'Application/X-Foo'}), {'foo': 'application/x-foo'})
        for bad in ({'php': 'text/plain'}, {'foo': 'text'}, {'foo': 'text/plain;'}, {'fo o': 'text/plain'},
                    {'foo': 'text/plain }'}, {str(n): 'text/plain' for n in range(51)}):
            with self.subTest(bad=str(bad)[:40]), self.assertRaises(ValueError):
                site_options.mime(bad)

    def test_unknown_section(self):
        with self.assertRaises(ValueError):
            site_options.validate('autoindex_everything', True)


class Rendering(unittest.TestCase):
    def render(self, options, application=None):
        meta = site_meta(options, application)
        return sites.render(Path('/srv/almapanel/accounts'), '/run/php', 'shop', 'shop.example.com', meta)

    def test_no_options_keeps_existing_configuration(self):
        config = self.render({})
        self.assertIn(' location / { try_files $uri $uri/ =404; }\n', config)
        for directive in ('autoindex', 'error_page', 'valid_referers', 'types {'):
            self.assertNotIn(directive, config)

    def test_hotlink_rule_follows_deny_rules_and_precedes_php(self):
        config = self.render({'hotlink': {'enabled': True, 'allowed': [], 'extensions': ['jpg'], 'allow_direct': True}})
        hotlink = config.index('valid_referers none blocked server_names;')
        self.assertLess(config.index('location ~ /\\. { deny all; }'), hotlink)
        self.assertLess(config.index('location ~* \\.p(?:html|har|hp[0-9]+)$ { deny all; }'), hotlink)
        self.assertLess(hotlink, config.index('location ~ \\.php$ {'))

    def test_wordpress_index_folders_keep_permalink_fallback(self):
        config = self.render({'indexes': ['/media']}, application='wordpress')
        self.assertIn(' location /media/ {\n  autoindex on;', config)
        self.assertIn('try_files $uri $uri/ /index.php?$args;', config)
        self.assertNotIn('location ^~ /media', config)


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


@unittest.skipUnless(shutil.which('nginx') and os.geteuid() == 0, 'Requires Nginx and root to run a real server.')
class RealNginx(unittest.TestCase):
    """Serve a rendered site with Nginx and check behavior over HTTP."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.web = self.base / 'accounts' / 'shop' / 'public_html'
        (self.web / 'downloads').mkdir(parents=True)
        (self.web / 'private').mkdir()
        (self.web / 'errors').mkdir()
        (self.web / 'downloads' / 'guide.txt').write_text('guide')
        (self.web / 'downloads' / '.env').write_text('SECRET=1')
        (self.web / 'downloads' / 'run.php').write_text('<?php echo "secret source";')
        (self.web / 'private' / 'notes.txt').write_text('notes')
        (self.web / 'photo.jpg').write_bytes(b'\xff\xd8\xff')
        (self.web / '.hidden.jpg').write_bytes(b'\xff\xd8\xff')
        (self.web / 'data.foo').write_text('foo')
        (self.web / 'errors' / '404.html').write_text('<h1>Custom missing page</h1>')
        for path in (self.base, self.base / 'accounts', self.base / 'accounts' / 'shop'):
            path.chmod(0o755)

    def serve(self, options):
        port = free_port()
        meta = site_meta(options)
        with patch.object(metrics, 'LOG_DIR', self.base / 'logs'), patch.object(sites, 'ACME_ROOT', self.base / 'acme'):
            (self.base / 'logs').mkdir(exist_ok=True)
            config = sites.render(self.base / 'accounts', str(self.base / 'php'), 'shop', 'shop.example.com', meta)
        config = config.replace(' listen 80;\n', f' listen 127.0.0.1:{port};\n')
        prefix = self.base / 'nginx'
        prefix.mkdir(exist_ok=True)
        shutil.copy('/etc/nginx/fastcgi_params', prefix / 'fastcgi_params')
        temp = ' '.join(f'{name}_temp_path {prefix}/{name};' for name in ('client_body', 'proxy', 'fastcgi', 'uwsgi', 'scgi'))
        (prefix / 'nginx.conf').write_text(
            f'pid {prefix}/nginx.pid;\nerror_log {prefix}/error.log;\nevents {{}}\n'
            f'http {{\n include /etc/nginx/mime.types;\n default_type application/octet-stream;\n {temp}\n{config}}}\n')
        argv = ['nginx', '-p', str(prefix), '-c', str(prefix / 'nginx.conf')]
        check = subprocess.run([*argv, '-t'], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        subprocess.run(argv, check=True)
        self.addCleanup(subprocess.run, [*argv, '-s', 'stop'], capture_output=True)
        for _ in range(50):
            if (prefix / 'nginx.pid').exists():
                break
            time.sleep(0.05)
        self.port = port

    def get(self, path, referer=None):
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', headers={'Host': 'shop.example.com'})
        if referer:
            request.add_header('Referer', referer)
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(request, timeout=5) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def test_options_over_http(self):
        self.serve({
            'indexes': ['/downloads'],
            'error_pages': {'404': '/errors/404.html'},
            'hotlink': {'enabled': True, 'allowed': ['partner.example'], 'extensions': ['jpg'], 'allow_direct': True},
            'mime': {'foo': 'application/x-foo'},
        })
        status, _, body = self.get('/downloads/')
        self.assertEqual(status, 200)
        self.assertIn(b'guide.txt', body)
        self.assertNotIn(b'.env', body)
        self.assertEqual(self.get('/downloads/.env')[0], 403)
        # PHP under a listed folder still goes to the PHP handler (no socket here), never served as text.
        status, _, body = self.get('/downloads/run.php')
        self.assertNotEqual(status, 200)
        self.assertNotIn(b'secret source', body)
        self.assertEqual(self.get('/private/')[0], 403)  # Listing only where enabled.
        status, headers, body = self.get('/no-such-page')
        self.assertEqual(status, 404)
        self.assertIn(b'Custom missing page', body)
        self.assertTrue(headers['Content-Type'].startswith('text/html'))
        self.assertEqual(self.get('/data.foo')[1]['Content-Type'], 'application/x-foo')
        self.assertTrue(self.get('/downloads/guide.txt')[1]['Content-Type'].startswith('text/plain'))
        self.assertEqual(self.get('/photo.jpg')[0], 200)
        self.assertEqual(self.get('/photo.jpg', 'https://shop.example.com/page')[0], 200)
        self.assertEqual(self.get('/photo.jpg', 'https://partner.example/post')[0], 200)
        self.assertEqual(self.get('/photo.jpg', 'https://elsewhere.example/steal')[0], 403)
        self.assertEqual(self.get('/.hidden.jpg')[0], 403)  # Hidden files stay denied.

    def test_compression(self):
        (self.web / 'style.css').write_text('body { color: #123456; }\n' * 40)
        self.serve({'optimize': {'compress': True}})
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}/style.css',
                                         headers={'Host': 'shop.example.com', 'Accept-Encoding': 'gzip'})
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers['Content-Encoding'], 'gzip')
            self.assertLess(len(response.read()), 1000)
        with self.assertRaises(ValueError):
            site_options.optimize({'compress': 'yes'})

    def test_hotlink_redirect_and_direct_requests(self):
        self.serve({'hotlink': {'enabled': True, 'allowed': [], 'extensions': ['jpg'], 'allow_direct': False,
                                'redirect': 'https://shop.example.com/no-hotlinking.html'}})
        status, headers, _ = self.get('/photo.jpg', 'https://elsewhere.example/')
        self.assertEqual(status, 302)
        self.assertEqual(headers['Location'], 'https://shop.example.com/no-hotlinking.html')
        self.assertEqual(self.get('/photo.jpg')[0], 302)  # Direct requests refused when not allowed.


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None
