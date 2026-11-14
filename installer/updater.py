# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Verify signed GitHub release assets and replace application code only."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from urllib.request import urlopen

ROOT = Path("/opt/almapanel")
HEALTHCHECK = Path(__file__).resolve().with_name("healthcheck.sh")
KEY = Path("/etc/almapanel/update-public.pem")
STATE = Path("/var/lib/almapanel-updater")
STATUS = Path("/var/lib/almapanel-update-status")
CHANNEL = "https://github.com/allanalmatech/almaPanel/releases/latest/download/"
ASSET = "almapanel-update.tar.gz"
DIRS = ("agent", "backend", "frontend", "worker")
UNITS = ("almapanel-agent.service", "almapanel-api.service", "almapanel-worker.service")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(alpha|beta|rc)\.(0|[1-9][0-9]*))?")


def version_key(value):
    match = VERSION.fullmatch(value)
    if not match:
        raise ValueError("Invalid release version")
    major, minor, patch, stage, number = match.groups()
    return int(major), int(minor), int(patch), {None: 3, "rc": 2, "beta": 1, "alpha": 0}[stage], int(number or 0)


def run(*args):
    subprocess.run(args, check=True, timeout=210)


def download(name, path, limit):
    with urlopen(CHANNEL + name, timeout=20) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Release asset exceeds its size limit")
    path.write_bytes(data)


def report(state, message):
    item = {"state": state, "message": message, "checked_at": int(time.time())}
    tmp = STATUS / ".status"
    tmp.write_text(json.dumps(item))
    tmp.chmod(0o644)
    tmp.replace(STATUS / "status.json")


def stage_archive(asset, dest, version):
    seen = set()
    total = 0
    with tarfile.open(asset, "r:gz") as archive:
        for item in archive:
            path = Path(item.name)
            parts = path.parts
            if (not item.isfile() or len(parts) < 2 or parts[0] != "almapanel"
                    or ".." in parts or path in seen):
                raise ValueError("Unexpected release archive entry")
            seen.add(path)
            relative = Path(*parts[1:])
            if relative.name == "VERSION" and len(relative.parts) == 1:
                pass
            elif relative.parts[0] not in DIRS or len(relative.parts) < 2:
                raise ValueError("Release contains files outside the application")
            total += item.size
            if total > 32 * 1024 * 1024 or len(seen) > 2000:
                raise ValueError("Unpacked release exceeds its limits")
            output = dest / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(item) as data, output.open("xb") as file:
                shutil.copyfileobj(data, file)
    if (dest / "VERSION").read_text().strip() != version:
        raise ValueError("Release archive version does not match the manifest")
    for component in DIRS:
        if not (dest / component).is_dir():
            raise ValueError(f"Application component missing: {component}")


def sync_code(source):
    for component in DIRS:
        run("/usr/bin/rsync", "-r", "--perms", "--chmod=D755,F644", "--delete",
            "--exclude=__pycache__", "--exclude=*.pyc",
            str(source / component) + "/", str(ROOT / component) + "/")
    tmp = ROOT / ".update-version"
    shutil.copyfile(source / "VERSION", tmp)
    tmp.chmod(0o644)
    tmp.replace(ROOT / "VERSION")


def restart_and_verify():
    run("/usr/bin/systemctl", "start", *UNITS)
    run("/usr/bin/bash", str(HEALTHCHECK))


def recover():
    backup = STATE / "rollback"
    if not (STATE / "in-progress").exists():
        return False
    if not (backup / "VERSION").is_file() or not all((backup / part).is_dir() for part in DIRS):
        raise RuntimeError("Update recovery needs the application backup in /var/lib/almapanel-updater/rollback.")
    print("Restoring the saved application files before retrying the update.", flush=True)
    run("/usr/bin/systemctl", "stop", *reversed(UNITS))
    sync_code(backup)
    restart_and_verify()
    (STATE / "in-progress").unlink()
    return True


def apply(candidate):
    backup = STATE / "rollback"
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir()
    for component in DIRS:
        shutil.copytree(ROOT / component, backup / component, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(ROOT / "VERSION", backup / "VERSION")
    (STATE / "in-progress").touch()
    os.sync()
    try:
        run("/usr/bin/systemctl", "stop", *reversed(UNITS))
        sync_code(candidate)
        restart_and_verify()
        (STATE / "in-progress").unlink()
    except Exception:
        try:
            recover()
        except Exception as error:
            raise RuntimeError("Update and recovery checks failed. Review the health check output before retrying.") from error
        raise


def check():
    if recover():
        report("rolled_back", "Recovered the previous version after an interrupted update.")
        return
    if not KEY.is_file():
        report("disabled", "A release verification key has not been enrolled.")
        return
    current = (ROOT / "VERSION").read_text().strip()
    report("checking", "Checking the signed GitHub release channel.")
    with tempfile.TemporaryDirectory(dir=STATE) as directory:
        work = Path(directory)
        manifest = work / "manifest.json"
        signature = work / "manifest.sig"
        download("manifest.json", manifest, 8192)
        download("manifest.sig", signature, 1024)
        run("/usr/bin/openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(KEY),
            "-rawin", "-in", str(manifest), "-sigfile", str(signature))
        release = json.loads(manifest.read_text())
        if release["format"] != 1 or release["database_schema"] != 1:
            raise ValueError("Release needs a manual platform or database upgrade")
        import sqlite3
        with sqlite3.connect("file:/var/lib/almapanel/panel.sqlite3?mode=ro", uri=True) as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ValueError("Installed database schema requires a manual upgrade")
        version = release["version"]
        if version_key(version) <= version_key(current):
            report("current", f"Installed version {current} is current.")
            return
        asset = work / ASSET
        download(ASSET, asset, 12 * 1024 * 1024)
        if hashlib.sha256(asset.read_bytes()).hexdigest() != release["sha256"]:
            raise ValueError("Release archive checksum did not match")
        candidate = work / "candidate"
        stage_archive(asset, candidate, version)
        report("applying", f"Installing {version}. The panel may briefly disconnect.")
        apply(candidate)
        report("updated", f"Installed {version} and passed service health checks.")


def main():
    STATE.mkdir(mode=0o700, exist_ok=True)
    STATUS.mkdir(mode=0o755, exist_ok=True)
    with (STATE / "lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            check()
        except Exception as exc:
            report("error", "Update failed. Review the updater journal on the server.")
            raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
