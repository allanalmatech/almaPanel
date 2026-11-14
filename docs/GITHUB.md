# Uploading and maintaining the repository
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

A repository is not published until `git push` succeeds. This delivery has no configured remote, owner account credentials or GitHub repository URL. Create a **private** empty repository in your organization pending license approval.

From the source ZIP directory:
```bash
git init -b main
git add .
git commit -m "Initial almaPanel Ubuntu hosting core"
git remote add origin https://github.com/YOUR_ORG/almapanel.git
git push -u origin main
```
To preserve the provided history from the separate bundle:
```bash
git clone almapanel-0.1.0-alpha.1.git.bundle almapanel
cd almapanel
git remote remove origin
git remote add origin https://github.com/YOUR_ORG/almapanel.git
git push -u origin main
```
Set branch protection and required CI checks; enable GitHub secret scanning/dependency features available to your organization. Replace action version tags with reviewed commit SHA pins as part of release hardening. Configure Dependabot reviews. Do not put signing keys into the repository.

After all recorded release gates have objective evidence and owner approval:
```bash
make check
python3 scripts/release_gate.py
python3 scripts/package.py
git tag -s vVERSION -m "almaPanel VERSION"
git push origin vVERSION
```
Signing requires your configured signing identity. The workflow deliberately does not publish releases. Add a protected-environment publish job only after signing/provenance/storage and acceptance evidence are configured. Never bypass a failing gate just to produce a release tag.
