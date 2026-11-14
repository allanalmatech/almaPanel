#!/usr/bin/env python3
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Build the application-only update archive and its unsigned manifest."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

root = Path(__file__).resolve().parents[1]
out = root / "dist"
out.mkdir(exist_ok=True)
archive = out / "almapanel-update.tar.gz"

with tarfile.open(archive, "w:gz") as output:
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "VERSION", "agent", "backend", "frontend", "worker"], cwd=root
    )
    for name in paths.decode().split("\0"):
        if not name:
            continue
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"Unexpected update input: {name}")
        output.add(path, arcname=f"almapanel/{name}", recursive=False)

manifest = {
    "format": 1,
    "database_schema": 1,
    "version": (root / "VERSION").read_text().strip(),
    "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
