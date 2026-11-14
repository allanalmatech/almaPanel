#!/usr/bin/env python3
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Deterministic source distribution (stdlib; no frontend transpiler)."""
import gzip
import hashlib
import io
import os
from pathlib import Path
import tarfile
root=Path(__file__).resolve().parents[1]
version=(root/'VERSION').read_text().strip()
out=root/'dist';out.mkdir(exist_ok=True)
path=out/f'almapanel-{version}.tar.gz'
with path.open('wb') as f, gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as gz, tarfile.open(fileobj=gz,mode='w') as tar:
 for p in sorted(root.rglob('*')):
  rel=p.relative_to(root)
  if any(x in ('.git','dist','__pycache__','.pytest_cache','.venv','node_modules') for x in rel.parts) or p.suffix=='.pyc' or p.name=='.coverage': continue
  if not p.is_file(): continue
  info=tarfile.TarInfo('almapanel/'+str(rel));data=p.read_bytes()
  info.size=len(data);info.uid=info.gid=0;info.uname=info.gname='root';info.mtime=0
  info.mode=0o755 if p.suffix=='.sh' else 0o644
  tar.addfile(info,io.BytesIO(data))
digest=hashlib.sha256(path.read_bytes()).hexdigest()
(out/'SHA256SUMS').write_text(digest+'  '+path.name+'\n')
print(path)
print(digest)
