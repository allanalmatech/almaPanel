# Production release checklist
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

All unchecked items block production. config/release-gates.json intentionally stays false. A local evaluation archive is not an approved release. Do not simply toggle flags to make CI green.

- [ ] Owner approves license and distribution/trademark notices.
- [ ] Every required product module implemented front-to-back; feature matrix updated with evidence.
- [ ] Clean Ubuntu 24.04 amd64 install and reboot acceptance.
- [ ] Clean Ubuntu 24.04 arm64 install and reboot acceptance.
- [ ] Hostile tenant tests: filesystem, socket, process, network and resource exhaustion.
- [ ] Live package/cgroup/disk/inode/traffic quota tests.
- [ ] Actual DNS, TLS issuance/renewal and mail send/receive tests with external infrastructure.
- [ ] Git deployment executes under tenant UID with tested release rollback.
- [ ] Database user isolation, import/export and restore verified.
- [ ] Full encrypted backup, remote retention and complete-account restoration tests.
- [ ] Upgrade, rollback, reboot and interrupted-operation recovery tests.
- [ ] Browser, responsive, keyboard and accessibility acceptance.
- [ ] MFA, root broker/worker hardening, rate limits and secrets review.
- [ ] Third-party dependency vulnerability scan and pinned build inputs/actions.
- [ ] Secret scanning, SBOM, provenance and independent security review.
- [ ] Installation documentation verified against real execution.
- [ ] Signing keys configured outside source; verification trust independently distributed.
- [ ] GitHub protected branch/environment and signed tag/release workflow.
- [ ] Install hostname DNS, trusted HTTPS and immutable versioned storage configured.
- [ ] Recovery and operator support process approved.

Required end-to-end scenarios 1–22 from the master specification remain release acceptance criteria. tests/installation/ubuntu_vm.sh exercises only an initial subset, not all 22.
