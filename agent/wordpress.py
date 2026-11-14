# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Install a verified WordPress release as the hosting account in a new folder."""
from http.client import HTTPSConnection
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile

if __package__:
    from . import file_tools as files
else:
    import file_tools as files

VERSION = '7.1.4'
ARCHIVE_SHA256 = 'a147146c159362778ecbbbfb07bb20ddf4e85b130f971c824e656a8f938c5f87'
LIMIT = 128 * 1024 * 1024
PHP = '/usr/bin/php'

SETUP = """<?php
$input = json_decode(stream_get_contents(STDIN), true, 512, JSON_THROW_ON_ERROR);
define('WP_INSTALLING', true);
require getcwd() . '/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/upgrade.php';
if (is_blog_installed()) {
    exit(10);
}
$result = wp_install(
  $input['title'], $input['username'], $input['email'],
  false, '', $input['password']
);
exit(!empty($result['user_id']) ? 0 : 1);
"""


def fetch_release(path):
    digest = hashlib.sha256()
    total = 0
    connection = HTTPSConnection('wordpress.org', timeout=15)
    try:
        connection.request('GET', f'/wordpress-{VERSION}.zip', headers={'User-Agent': 'almaPanel'})
        with connection.getresponse() as response, path.open('wb') as output:
            if response.status != 200:
                raise ValueError('WordPress release is unavailable.')
            while data := response.read(files.CHUNK):
                total += len(data)
                if total > 48 * 1024 * 1024:
                    raise ValueError('WordPress download exceeded the size limit.')
                digest.update(data)
                output.write(data)
    except OSError:
        raise ValueError('Could not download WordPress from wordpress.org.') from None
    finally:
        connection.close()

    if digest.hexdigest() != ARCHIVE_SHA256:
        raise ValueError('WordPress archive failed checksum verification.')


def install(root, request):
    destination = files.components(request.get('destination'))
    if not destination:
        raise ValueError('Choose a new WordPress folder.')
    db = request['database']
    if not re.fullmatch(r'ap[a-f0-9]{24}', db):
        raise ValueError('Invalid WordPress database name.')
    url = request['url']
    if not re.fullmatch(r'https://[a-z0-9.-]+', url):
        raise ValueError('WordPress requires an HTTPS site hostname.')
    if not re.fullmatch(r'[A-Za-z0-9_~-]{16,96}', request['db_password']):
        raise ValueError('Invalid database password format.')
    with tempfile.TemporaryDirectory(prefix='.alma-wp-') as folder:
        archive = Path(folder) / 'wordpress.zip'
        fetch_release(archive)
        # The pinned archive includes one wordpress/ wrapper. Move its contents
        # into the staged directory before it is published.
        def prepare(stage):
            with files.folder(stage, ['wordpress']) as wrapper:
                for name, _ in files.entries(wrapper):
                    files.move_entry(wrapper, name, stage, name)
            os.rmdir('wordpress', dir_fd=stage)
            with files.folder(stage, ['wp-content']) as content:
                for name in ('plugins', 'themes', 'uploads'):
                    try:
                        os.mkdir(name, 0o750, dir_fd=content)
                    except FileExistsError:
                        pass
            fd = os.open('wp-config.php', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=stage)
            with os.fdopen(fd, 'w') as config:
                values = {'DB_NAME': db, 'DB_USER': db, 'DB_PASSWORD': request['db_password'], 'DB_HOST': 'localhost',
                          'DB_CHARSET': 'utf8mb4', 'DB_COLLATE': '', 'WP_HOME': url, 'WP_SITEURL': url}
                config.write('<?php\n')
                for key, value in values.items():
                    config.write(f"define('{key}', '{value}');\n")
                for key in ('AUTH_KEY', 'SECURE_AUTH_KEY', 'LOGGED_IN_KEY', 'NONCE_KEY',
                            'AUTH_SALT', 'SECURE_AUTH_SALT', 'LOGGED_IN_SALT', 'NONCE_SALT'):
                    config.write(f"define('{key}', '{secrets.token_urlsafe(48)}');\n")
                config.write("define('DISALLOW_FILE_EDIT', true);\n")
                config.write("$table_prefix = 'wp_';\n")
                config.write("if (!defined('ABSPATH')) { define('ABSPATH', __DIR__ . '/'); }\nrequire_once ABSPATH . 'wp-settings.php';\n")
            script = Path(folder) / 'install.php'
            script.write_text(SETUP)
            env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/nonexistent'}
            result = subprocess.run([PHP, str(script)], cwd=f'/proc/self/fd/{stage}',
                                    pass_fds=(stage,), input=json.dumps(request['admin']), text=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=35, env=env)
            if result.returncode:
                raise ValueError('WordPress initialization failed. Use an empty database and check PHP MySQL support.')

        source = os.open(folder, files.NOFOLLOW_DIR)
        try:
            files.extract_zip(source, ['wordpress.zip'], root, destination, max_bytes=LIMIT, prepare=prepare)
        finally:
            os.close(source)
    return {'message': 'WordPress installed in a new folder. Set the domain’s document root to this folder.',
            'version': VERSION, 'document_root': '/'.join(destination)}
