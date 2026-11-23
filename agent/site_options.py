# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Per-website Nginx options: directory indexes, error pages, hotlink protection and MIME types.

Every value is validated here and rendered from fixed templates; nothing a tenant
types reaches the Nginx configuration without matching a strict pattern.
"""
import re
from urllib.parse import urlsplit

from backend.core import Problem, domain
from agent import sites

MIME_TYPES = '/etc/nginx/mime.types'
MAX_INDEXES = 20
MAX_HOTLINK_HOSTS = 20
MAX_MIME = 50
ERROR_CODES = ('400', '401', '403', '404', '500', '502', '503', '504')
EXTENSION = re.compile(r'[a-z0-9]{1,16}\Z')
MEDIA_TYPE = re.compile(r'[a-z0-9][a-z0-9!#$&^_.+-]{0,62}/[a-z0-9][a-z0-9!#$&^_.+-]{0,126}\Z')
ERROR_PAGE = re.compile(r'\.(?:html?|shtml|php)\Z')
# Scripts must always reach the PHP handler or its deny rules, never a static rule.
SCRIPT_EXTENSIONS = re.compile(r'(?:php[0-9]*|phtml|phar|pht|cgi|pl|py|sh)\Z')
DEFAULT_HOTLINK = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'mp4', 'webm', 'mp3']
SECTIONS = ('indexes', 'error_pages', 'hotlink', 'mime', 'optimize')
COMPRESSED_TYPES = ('text/plain text/css text/xml text/javascript application/javascript application/json '
                    'application/xml application/rss+xml application/atom+xml image/svg+xml font/ttf font/otf')


def directory(value):
    """A URL directory inside the website: '/' or '/folder/sub'."""
    if value == '/':
        return '/'
    if not isinstance(value, str) or not value.startswith('/'):
        raise ValueError('Use / for the whole website or a folder such as /downloads.')
    relative = sites.docroot(value[1:].rstrip('/'))  # Exactly one leading slash.
    if not relative:
        raise ValueError('Choose a folder path.')
    return '/' + relative


def indexes(values):
    if not isinstance(values, list) or len(values) > MAX_INDEXES:
        raise ValueError(f'List up to {MAX_INDEXES} folders.')
    return sorted({directory(value) for value in values})


def error_pages(values):
    if not isinstance(values, dict) or any(code not in ERROR_CODES for code in values):
        raise ValueError('Choose error codes from ' + ', '.join(ERROR_CODES) + '.')
    result = {}
    for code, page in values.items():
        if page in ('', None):
            continue
        if not isinstance(page, str) or not page.startswith('/'):
            raise ValueError('Error pages are paths inside the website, such as /errors/404.html.')
        relative = sites.docroot(page[1:])
        if not relative or not ERROR_PAGE.search(relative):
            raise ValueError('Use an .html, .htm, .shtml or .php error page.')
        result[code] = '/' + relative
    return dict(sorted(result.items()))


def hotlink_host(value):
    if not isinstance(value, str):
        raise ValueError('Enter allowed websites as host names.')
    host = value.strip().lower()
    wildcard = host.startswith('*.')
    try:
        domain(host[2:] if wildcard else host)
    except Problem:
        raise ValueError('Allowed websites must be host names such as example.com or *.example.com.') from None
    return host


def hotlink(values):
    if not isinstance(values, dict):
        raise ValueError('Invalid hotlink settings.')
    enabled = values.get('enabled')
    allow_direct = values.get('allow_direct', True)
    if type(enabled) is not bool or type(allow_direct) is not bool:
        raise ValueError('Invalid hotlink settings.')
    hosts = values.get('allowed', [])
    extensions = values.get('extensions', DEFAULT_HOTLINK)
    if not isinstance(hosts, list) or len(hosts) > MAX_HOTLINK_HOSTS:
        raise ValueError(f'List up to {MAX_HOTLINK_HOSTS} allowed websites.')
    if not isinstance(extensions, list) or not 1 <= len(extensions) <= 30:
        raise ValueError('Protect between 1 and 30 file extensions.')
    clean = []
    for extension in extensions:
        if not isinstance(extension, str):
            raise ValueError('Use extensions such as jpg or mp4.')
        extension = extension.strip().lower().lstrip('.')
        if not EXTENSION.fullmatch(extension):
            raise ValueError('Use extensions of 1–16 lowercase letters or digits, such as jpg or mp4.')
        if SCRIPT_EXTENSIONS.fullmatch(extension):
            raise ValueError('Script extensions such as .php cannot be hotlink protected.')
        clean.append(extension)
    redirect = values.get('redirect', '') or ''
    if redirect:
        if not isinstance(redirect, str) or not sites.REDIRECT.fullmatch(redirect):
            raise ValueError('Enter a valid HTTP or HTTPS redirect URL, or leave it empty to refuse with 403.')
        parsed = urlsplit(redirect)
        if not parsed.hostname or parsed.username is not None:
            raise ValueError('Redirect targets cannot contain credentials.')
    return {'enabled': enabled, 'allow_direct': allow_direct,
            'allowed': sorted({hotlink_host(host) for host in hosts}),
            'extensions': sorted(set(clean)), 'redirect': redirect}


def mime(values):
    if not isinstance(values, dict) or len(values) > MAX_MIME:
        raise ValueError(f'Add up to {MAX_MIME} MIME types.')
    result = {}
    for extension, media in values.items():
        if not isinstance(extension, str) or not isinstance(media, str):
            raise ValueError('Use an extension and a media type such as application/json.')
        extension = extension.strip().lower().lstrip('.')
        media = media.strip().lower()
        if not EXTENSION.fullmatch(extension):
            raise ValueError('Use extensions of 1–16 lowercase letters or digits.')
        if SCRIPT_EXTENSIONS.fullmatch(extension):
            raise ValueError('Script extensions such as .php cannot be given a MIME type.')
        if not MEDIA_TYPE.fullmatch(media):
            raise ValueError('Use a media type such as application/json.')
        result[extension] = media
    return dict(sorted(result.items()))


def optimize(values):
    if not isinstance(values, dict) or type(values.get('compress')) is not bool:
        raise ValueError('Choose whether to compress text content.')
    return {'compress': values['compress']}


def validate(section, values):
    if section == 'indexes':
        return indexes(values)
    if section == 'error_pages':
        return error_pages(values)
    if section == 'hotlink':
        return hotlink(values)
    if section == 'mime':
        return mime(values)
    if section == 'optimize':
        return optimize(values)
    raise ValueError('Choose indexes, error pages, hotlink protection or MIME types.')


def current(site):
    options = site.get('options', {})
    return {'indexes': options.get('indexes', []), 'error_pages': options.get('error_pages', {}),
            'hotlink': options.get('hotlink', {'enabled': False, 'allow_direct': True, 'allowed': [],
                                               'extensions': DEFAULT_HOTLINK, 'redirect': ''}),
            'mime': options.get('mime', {}), 'optimize': options.get('optimize', {'compress': False})}


def render(site, fallback):
    """Return (server directives, locations placed before the PHP handler)."""
    options = current(site)
    server = ''
    if options['mime']:
        types = ''.join(f'  {media} {extension};\n' for extension, media in options['mime'].items())
        server += f' include {MIME_TYPES};\n types {{\n{types} }}\n'
    if options['optimize'].get('compress'):
        # HTML is always compressed when gzip is on; these add the other text formats.
        server += f' gzip on;\n gzip_vary on;\n gzip_min_length 256;\n gzip_types {COMPRESSED_TYPES};\n'
    for code, page in options['error_pages'].items():
        server += f' error_page {code} {page};\n'
    locations = ''
    listing = ' autoindex on;\n autoindex_exact_size off;\n autoindex_localtime on;\n'
    for path in indexes(options['indexes']):
        if path == '/':
            server += listing
        else:
            # A plain prefix location: the server's deny and PHP regex locations still apply.
            locations += (f' location {path}/ {{\n  autoindex on;\n  autoindex_exact_size off;\n'
                          f'  autoindex_localtime on;\n  try_files {fallback};\n }}\n')
    rule = options['hotlink']
    if rule.get('enabled'):
        rule = hotlink(rule)
        accepted = (['none'] if rule['allow_direct'] else []) + ['blocked', 'server_names'] + rule['allowed']
        refuse = f'return 302 "{rule["redirect"]}";' if rule['redirect'] else 'return 403;'
        pattern = '|'.join(rule['extensions'])
        locations += (f' location ~* \\.(?:{pattern})$ {{\n  valid_referers {" ".join(accepted)};\n'
                      f'  if ($invalid_referer) {{ {refuse} }}\n  try_files $uri =404;\n }}\n')
    return server, locations
