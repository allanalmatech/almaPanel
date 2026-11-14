#!/usr/bin/env python3
# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]
gates=json.loads((p/'config/release-gates.json').read_text())
missing=[name for name,value in gates.items() if value is not True]
if missing: raise SystemExit('RELEASE BLOCKED: '+', '.join(missing))
print('All recorded release gates approved. Verify evidence before publication.')
