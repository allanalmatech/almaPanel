# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Bounded, retryable upload staging under the Linux hosting account identity."""
import base64
import fcntl
import json
import os
import re
import secrets
import shutil
import stat
import time

if __package__:
    from . import file_tools as fs
else:
    import file_tools as fs

ACTIONS = {'upload_start', 'upload_chunk', 'upload_finish', 'upload_cancel'}
TOKEN = re.compile(r'[0-9a-f]{32}\Z')
EXPIRES = 3600
MAX_PENDING = 4
MAX_RESERVED = 512 * 1024**2
MAX_RECEIPTS = 16
CREATE = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW


def metadata(stage):
    with os.fdopen(os.open('upload.json', fs.NOFOLLOW_FILE, dir_fd=stage), 'rb') as stream:
        if fs.regular(stream.fileno()).st_size > 24000:
            raise ValueError('Invalid upload state.')
        fields = json.loads(stream.read(24001))
    if (not isinstance(fields, dict) or type(fields.get('size')) is not int
            or not 0 <= fields['size'] <= fs.TRANSFER_BYTES or not fs.components(fields.get('path'))):
        raise ValueError('Invalid upload state.')
    return fields


def save(stage, fields):
    temporary = '.alma-' + secrets.token_hex(12)
    try:
        with os.fdopen(os.open(temporary, CREATE, 0o600, dir_fd=stage), 'w') as stream:
            json.dump(fields, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, 'upload.json', src_dir_fd=stage, dst_dir_fd=stage)
        os.fsync(stage)
    finally:
        fs.unlink_if_present(stage, temporary)


def reap(staging):
    now = time.time()
    pending = []
    receipts = []
    for index, (token, entry) in enumerate(fs.entries(staging)):
        if index >= fs.MAX_ENTRIES:
            raise ValueError('Upload staging contains too many entries.')
        if not TOKEN.fullmatch(token) or not stat.S_ISDIR(entry.st_mode):
            continue
        try:
            with fs.folder(staging, [token]) as stage:
                if entry.st_mtime < now - EXPIRES:
                    raise ValueError('Upload expired.')
                fields = metadata(stage)
                if fs.stat_entry(stage, 'data') is None:
                    receipts.append((entry.st_mtime, token))
                else:
                    pending.append(fields['size'])
        except (KeyError, OSError, ValueError, TypeError):
            shutil.rmtree(token, dir_fd=staging)
    for _, token in sorted(receipts, reverse=True)[MAX_RECEIPTS:]:
        shutil.rmtree(token, dir_fd=staging)
    return pending


def start(root, staging, parts, size):
    if not parts or type(size) is not int or not 0 <= size <= fs.TRANSFER_BYTES:
        raise ValueError('Choose a new file path and a size up to 256 MiB.')
    with fs.folder(root, parts[:-1]) as parent:
        if fs.stat_entry(parent, parts[-1]) is not None:
            raise ValueError('Destination already exists.')
        info = os.fstat(parent)
        available = os.fstatvfs(parent)
        if size > available.f_bavail * available.f_frsize:
            raise ValueError('The destination filesystem has insufficient available space.')
    pending = reap(staging)
    if len(pending) >= MAX_PENDING or sum(pending) + size > MAX_RESERVED:
        raise ValueError('Too many pending uploads. Cancel an upload or wait for it to expire.')
    token = secrets.token_hex(16)
    os.mkdir(token, 0o700, dir_fd=staging)
    try:
        with fs.folder(staging, [token]) as stage:
            os.close(os.open('data', CREATE, 0o600, dir_fd=stage))
            save(stage, {'path': '/'.join(parts), 'size': size, 'parent': [info.st_dev, info.st_ino]})
    except BaseException:
        shutil.rmtree(token, dir_fd=staging)
        raise
    return {'upload_id': token, 'offset': 0, 'chunk_bytes': fs.CHUNK}


def append(stage, size, fields):
    offset = fields.get('offset')
    encoded = fields.get('content')
    if (type(offset) is not int or not 0 <= offset < size or not isinstance(encoded, str)
            or len(encoded) > 4 * ((fs.CHUNK + 2) // 3)):
        raise ValueError('Invalid upload chunk.')
    payload = base64.b64decode(encoded, validate=True)
    ending = offset + len(payload)
    if not 0 < len(payload) <= fs.CHUNK or ending > size:
        raise ValueError('Upload chunk exceeds its declared length.')
    fd = os.open('data', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=stage)
    try:
        written = fs.regular(fd).st_size
        if not offset <= written <= size:
            raise ValueError('Upload chunks must arrive in order.')
        # A browser can repeat a chunk after a lost reply, including one with
        # a prefix already written before the process stopped.
        overlap = min(written - offset, len(payload))
        if os.pread(fd, overlap, offset) != payload[:overlap]:
            raise ValueError('Upload chunk differs from data already received.')
        remainder = memoryview(payload)[overlap:]
        position = offset + overlap
        while remainder:
            amount = os.pwrite(fd, remainder, position)
            if not amount:
                raise OSError('Upload write did not make progress.')
            position += amount
            remainder = remainder[amount:]
        os.utime(stage, None)
    finally:
        os.close(fd)
    return {'offset': max(written, ending)}


def identity(info):
    if info is None or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        return None
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def finish(root, stage, state):
    parts = fs.components(state['path'])
    leaf = parts[-1]
    with fs.folder(root, parts[:-1]) as parent:
        info = os.fstat(parent)
        if state.get('parent') != [info.st_dev, info.st_ino]:
            raise ValueError('The destination folder changed during the upload.')
        existing = fs.stat_entry(parent, leaf)
        if existing is not None:
            if not state.get('published') or state['published'] != identity(existing):
                raise ValueError('Destination already exists.')
        else:
            with os.fdopen(os.open('data', fs.NOFOLLOW_FILE, dir_fd=stage), 'rb') as staged:
                original = fs.regular(staged.fileno())
                if original.st_size != state['size']:
                    raise ValueError('Upload is incomplete.')
                with fs.staged_output(parent) as (temporary, output):
                    fs.copy_bytes(staged, output, fs.Budget(state['size']))
                    output.flush()
                    os.fsync(output.fileno())
                    if fs.revision_of(fs.regular(staged.fileno())) != fs.revision_of(original):
                        raise ValueError('Staged file changed during upload.')
                    # Persist the intended file identity before publication so
                    # repeating a finished request can recognize its own file.
                    state['published'] = identity(os.fstat(output.fileno()))
                    save(stage, state)
                    fs.move_entry(parent, temporary, parent, leaf)
                    os.fsync(parent)
        fs.unlink_if_present(stage, 'data')
        os.utime(stage, None)
    return {'message': 'File uploaded.', 'path': state['path'], 'size': state['size']}


def operate(root, private, parts, request):
    if private is None:
        raise ValueError('Private upload storage is unavailable.')
    try:
        os.mkdir('uploads', 0o700, dir_fd=private)
    except FileExistsError:
        pass
    with fs.folder(private, ['uploads']) as staging:
        try:
            fcntl.flock(staging, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another upload stage operation is running. Try again.') from None
        action = request['action']
        if action == 'upload_start':
            return start(root, staging, parts, request.get('size'))
        token = request.get('upload_id')
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise ValueError('Invalid upload reference.')
        try:
            stage = fs.directory(staging, [token])
        except FileNotFoundError:
            if action == 'upload_cancel':
                return {'message': 'Upload canceled.'}
            raise ValueError('Upload expired or is unavailable. Start it again.') from None
        try:
            if action == 'upload_cancel':
                shutil.rmtree(token, dir_fd=staging)
                return {'message': 'Upload canceled.'}
            if time.time() - os.fstat(stage).st_mtime > EXPIRES:
                shutil.rmtree(token, dir_fd=staging)
                raise ValueError('Upload expired. Start it again.')
            state = metadata(stage)
            if action == 'upload_chunk':
                if fs.stat_entry(stage, 'data') is None:
                    raise ValueError('Upload has already finished.')
                return append(stage, state['size'], request)
            return finish(root, stage, state)
        finally:
            os.close(stage)
