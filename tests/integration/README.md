# tests/integration
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

Current consolidated tests are in tests/test_core.py. API integration uses real SQLite and WSGI, filesystem tests use actual temporary Linux files. Root service calls are mocked only for state-machine/rollback tests; they are not Linux service acceptance. See TESTING.md and tests/installation/ubuntu_vm.sh.
