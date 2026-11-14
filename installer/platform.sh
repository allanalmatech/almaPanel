#!/usr/bin/env bash
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
# Fixed platform profiles shared by installation and maintenance commands.
source /etc/os-release
case "$ID:$VERSION_ID" in
 ubuntu:24.04)
  PHP_UNIT=php8.3-fpm
  PHP_BIN=/usr/sbin/php-fpm8.3
  PHP_POOL=/etc/php/8.3/fpm/pool.d
  PHP_RUN=/run/php
  WEB_USER=www-data
  PANEL_PY=/usr/bin/python3
  ;;
 amzn:2023)
  PHP_UNIT=php-fpm
  PHP_BIN=/usr/sbin/php-fpm
  PHP_POOL=/etc/php-fpm.d
  PHP_RUN=/run/php-fpm
  WEB_USER=nginx
  PANEL_PY=/opt/almapanel/venv/bin/python
  ;;
 *)
  echo "Unsupported OS: ${PRETTY_NAME:-unknown}. Use Ubuntu 24.04 or Amazon Linux 2023." >&2
  return 1
  ;;
esac
