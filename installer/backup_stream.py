# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Run and bound the two binary streams used during off-site backup and recovery."""
import os
import selectors
import subprocess
import time


def stream(argv, output, *, limit, timeout, failure, **process_options):
    deadline = time.monotonic() + timeout
    with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, **process_options) as child:
        try:
            with selectors.SelectSelector() as ready:
                ready.register(child.stdout, selectors.EVENT_READ)
                size = 0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not ready.select(min(30, remaining)):
                        raise ValueError('Timed out while reading backup data.')
                    data = os.read(child.stdout.fileno(), 512 * 1024)
                    if not data:
                        break
                    size += len(data)
                    if size > limit:
                        raise ValueError('The backup exceeds its size limit.')
                    output.write(data)
            if child.wait(timeout=30) or size == 0:
                raise ValueError(failure)
            output.flush()
            os.fsync(output.fileno())
        finally:
            # Kill a stalled child before the context manager waits for it.
            if child.poll() is None:
                child.kill()
    return size
