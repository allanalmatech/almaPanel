# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Backup exports for zones managed by the authoritative DNS adapter."""
import hashlib
import json
from pathlib import Path

from agent import dns
from backend.core import domain, name

LIMIT = 100_000


def zone_path(entry):
    # Keeping the domain as a directory supports the full allowed domain length.
    return Path('dns') / entry['account'] / entry['domain'] / 'records.json'


def capture(stage, inventory, accounts, progress):
    zones = [(account, host, zone) for account in accounts
             for host, zone in sorted(inventory[account].get('zones', {}).items())]
    snapshots = []
    for index, (account, host, zone) in enumerate(zones):
        name(account)
        if progress:
            progress('running', 'Preparing managed DNS zones.', completed=index, total=len(zones))
        domain(host)
        if host not in inventory[account]['domains']:
            raise ValueError(f'The managed DNS zone {host} is outside its hosting account.')
        serial = dns.integer(zone.get('serial'), 1, 2**32 - 1)
        records = dns.records(zone.get('records'), host)
        export = {'format': 1, 'domain': host, 'serial': serial, 'records': records}
        payload = (json.dumps(export, indent=2) + '\n').encode()
        if len(payload) > LIMIT:
            raise ValueError(f'The DNS export for {host} exceeds its size limit.')
        entry = {'account': account, 'domain': host, 'serial': serial, 'records': len(records),
                 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        path = stage / zone_path(entry)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open('xb') as output:
            output.write(payload)
        snapshots.append(entry)
    return snapshots


def verify_export(path, entry):
    data = json.loads(path.read_text())
    if (not isinstance(data, dict) or data.get('format') != 1 or data.get('domain') != entry['domain']
            or data.get('serial') != entry['serial']):
        raise ValueError('Restored DNS export does not match the selected zone.')
    records = dns.records(data.get('records'), entry['domain'])
    if len(records) != entry['records']:
        raise ValueError('The restored DNS export has an unexpected record count.')
