# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Bounded per-site request metrics and a live view of account Linux processes."""
from pathlib import Path
import json
import os
import stat

from backend.core import domain, name

LOG_DIR = Path('/var/log/almapanel-sites')
MAX_LOG_BYTES = 512 * 1024


def log_path(account, host):
    return LOG_DIR / f'{name(account)}--{domain(host)}.log'


def web_requests(account, host):
    path = log_path(account, host)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {'requests': 0, 'errors': 0, 'bytes': 0, 'latest': [], 'truncated': False}
    with os.fdopen(fd, 'rb') as logfile:
        info = os.fstat(logfile.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
            raise ValueError('Managed access log has unexpected ownership or type.')
        start = max(0, info.st_size - MAX_LOG_BYTES)
        logfile.seek(start)
        data = logfile.read(MAX_LOG_BYTES)
    lines = data.splitlines()[int(start > 0):]
    counts = {'requests': 0, 'errors': 0, 'bytes': 0}
    recent = []
    for line in reversed(lines):
        try:
            row = json.loads(line)
            status = int(row['status'])
            size = int(row['bytes'])
        except (ValueError, KeyError, TypeError):
            continue
        counts['requests'] += 1
        counts['errors'] += status >= 400
        counts['bytes'] += size
        if len(recent) < 100:
            recent.append({'time': row['time'], 'method': row['method'], 'path': row['path'][:512],
                           'status': status, 'bytes': size, 'client': row['client']})
    return {**counts, 'latest': recent, 'truncated': start > 0}


def processes(uid):
    result = []
    all_memory = 0
    count = 0
    page = os.sysconf('SC_PAGE_SIZE')
    ticks = os.sysconf('SC_CLK_TCK')
    uptime = float(Path('/proc/uptime').read_text().split()[0])
    for directory in Path('/proc').iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            # Effective UID in /proc/status avoids trusting names or command arguments.
            with (directory / 'status').open() as status:
                ids = next(line.split()[1:] for line in status if line.startswith('Uid:'))
            if int(ids[1]) != uid:
                continue
            details = (directory / 'stat').read_text()
            left, right = details.index('('), details.rindex(')')
            fields = details[right + 2:].split()  # Starts at proc stat field 3.
            lifetime = max(0.01, uptime - int(fields[19]) / ticks)
            cpu = round((int(fields[11]) + int(fields[12])) / ticks / lifetime * 100, 1)
            memory = max(0, int(fields[21])) * page
            all_memory += memory
            count += 1
            if len(result) < 100:
                result.append({'pid': int(directory.name), 'name': details[left + 1:right],
                               'cpu_lifetime_percent': cpu, 'rss': memory})
        except (OSError, ValueError, StopIteration, IndexError):
            continue
    return {'processes': result, 'process_count': count, 'process_rss': all_memory}
