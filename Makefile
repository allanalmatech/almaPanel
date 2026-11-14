# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
.PHONY: test check package release-check
test:
	python3 -m unittest discover -s tests -v
check: test
	python3 -m compileall -q backend agent worker installer scripts tests
	for script in frontend/*.js; do node --check "$$script" || exit; done
	for script in installer/*.sh; do bash -n "$$script" || exit; done
package: check
	python3 scripts/package.py
release-check:
	python3 scripts/release_gate.py
