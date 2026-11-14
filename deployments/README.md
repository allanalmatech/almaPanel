# Deployment infrastructure
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

`ec2-evaluation.yaml` creates a minimal Ubuntu evaluation instance/security group when explicitly deployed by the owner. It has no automatic user-data code execution and no embedded credentials. Supply VPC, public subnet, administrator /32 IP, Ubuntu 24.04 amd64 AMI and key-pair name. Review cost settings first. It has not been deployed or CloudFormation-validated by AWS in this environment.

`installer-host.nginx.conf` is an owner-reviewed static HTTPS host template for `install.almatechconsults.com`. DNS A/AAAA, a real certificate and renewal, storage permissions and release promotion are external tasks. Directory auto-indexing is off. Do not publish alpha artifacts as production.

After all gates pass: produce deterministic archive/checksums; sign a release manifest with an owner-controlled key; independently publish verification trust; copy approved versioned artifacts to `/var/www/almapanel-installer/releases/VERSION/`; publish the reviewed bootstrap; atomically switch stable version metadata. Retain old releases and revoke compromised artifacts. Protect write access and prefer immutable versioned storage. The current bootstrap demands an independently obtained archive SHA256 and cannot provide signature trust until owner signing is configured.

No infrastructure, hostname, GitHub repository or endpoint was created by this delivery. An operator must validate the template and resource permissions before deployment.
