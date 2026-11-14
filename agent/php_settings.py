# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Allowlisted settings for each account's PHP-FPM pool."""
from pathlib import Path
import os

from agent import file_tools

DEFAULTS = {'memory_mib': 96, 'upload_mib': 8, 'execution_seconds': 30, 'show_errors': False}
LIMITS = {'memory_mib': (32, 192), 'upload_mib': (1, 32), 'execution_seconds': (5, 60)}


def settings(raw):
    if not isinstance(raw, dict) or set(raw) != set(DEFAULTS):
        raise ValueError('Supply all PHP settings.')
    for key, (minimum, maximum) in LIMITS.items():
        if type(raw[key]) is not int or not minimum <= raw[key] <= maximum:
            raise ValueError(f'{key} must be between {minimum} and {maximum}.')
    if type(raw['show_errors']) is not bool:
        raise ValueError('Error display must be on or off.')
    return {key: raw[key] for key in DEFAULTS}


def error_tail(root, uid):
    directory = Path(root) / 'runtime'
    dirfd = os.open(directory, file_tools.NOFOLLOW_DIR)
    try:
        try:
            fd = os.open('php-error.log', file_tools.NOFOLLOW_FILE, dir_fd=dirfd)
        except FileNotFoundError:
            return {'lines': []}
        with os.fdopen(fd, 'rb') as logfile:
            details = file_tools.regular(logfile.fileno())
            if details.st_uid != uid:
                raise ValueError('PHP error log has unexpected ownership.')
            logfile.seek(max(0, details.st_size - 65536))
            return {'lines': logfile.read(65536).decode('utf-8', errors='replace').splitlines()[-100:]}
    finally:
        os.close(dirfd)
