#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
# Public bootstrap TEMPLATE: release channel must be published by the owner.
set -Eeuo pipefail
umask 077
VERSION=${ALMAPANEL_VERSION:-0.1.0-alpha.1}
[[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$ ]] || exit 2
# This independently obtained digest is mandatory until owner-controlled signing is configured.
EXPECTED=${ALMAPANEL_SHA256:-}
[[ $EXPECTED =~ ^[0-9a-f]{64}$ ]] || { echo 'Set ALMAPANEL_SHA256 to the owner-published artifact digest obtained over a trusted channel. Release endpoint is not yet published.' >&2; exit 2; }
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
BASE=https://install.almatechconsults.com/releases
curl --proto '=https' --tlsv1.2 --retry 3 --fail --show-error --location "$BASE/$VERSION/almapanel-$VERSION.tar.gz" -o "$TMP/release.tgz"
printf '%s  %s\n' "$EXPECTED" "$TMP/release.tgz" | sha256sum -c -
# Reject symlinks, hardlinks, device files and traversal before extraction.
python3 - "$TMP/release.tgz" "$TMP" <<'PYS'
import sys,tarfile
from pathlib import PurePosixPath
with tarfile.open(sys.argv[1]) as tar:
 for m in tar.getmembers():
  p=PurePosixPath(m.name)
  if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!='almapanel' or not (m.isfile() or m.isdir()):
   raise SystemExit('Unsafe release archive')
 tar.extractall(sys.argv[2],filter='data')
PYS
bash "$TMP/almapanel/installer/install.sh" "$@"
