#!/usr/bin/env python3
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Basic accidental-secret guard. Not a replacement for provider secret scanning."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
patterns=[re.compile(r'AKIA[0-9A-Z]{16}'),re.compile(r'gh[pousr]_[A-Za-z0-9]{36,}'),
          re.compile('-----BEGIN '+r'(?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
found=[]
for p in root.rglob('*'):
 if not p.is_file() or any(x in ('.git','dist','__pycache__','.venv') for x in p.relative_to(root).parts):continue
 if p.suffix in ('.pyc','.png','.bundle') or p.name=='.coverage':continue
 try:text=p.read_text()
 except UnicodeDecodeError:continue
 if any(pattern.search(text) for pattern in patterns):found.append(str(p.relative_to(root)))
if found:raise SystemExit('Possible secret material in: '+', '.join(found))
print('Basic secret-pattern scan passed (not exhaustive).')
