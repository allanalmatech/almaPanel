#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
source /etc/os-release
case "$ID:$VERSION_ID" in
 ubuntu:24.04) apt-get install -y dnsutils ;;
 amzn:2023) dnf install -y bind-utils ;;
 *) echo 'Unsupported operating system.' >&2; exit 1 ;;
esac
command -v dig
