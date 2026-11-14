# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Bounded account file operations. The CLI runs these after dropping UID."""
import base64
from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import PurePosixPath
import re
import secrets
import shutil
import stat
import zipfile

CHUNK = 512 * 1024
MAX_BYTES = 64 * 1024 * 1024
BACKUP_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_DEPTH = 24
NOFOLLOW_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
NOFOLLOW_DIR = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY


def components(path):
    if (not isinstance(path, str) or len(path) > 2048 or
            any(ord(char) < 32 for char in path)):
        raise ValueError('Invalid file path.')
    if PurePosixPath(path).is_absolute() or any(part in ('.', '..') for part in path.split('/')):
        raise ValueError('Path must stay inside public_html.')
    parts = [part for part in path.split('/') if part]
    if len(parts) > MAX_DEPTH:
        raise ValueError('Directory nesting limit exceeded.')
    return parts


def directory(root, parts):
    fd = os.dup(root)
    try:
        for part in parts:
            next_fd = os.open(part, NOFOLLOW_DIR, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def folder(root, parts):
    fd = directory(root, parts)
    try:
        yield fd
    finally:
        os.close(fd)


def regular(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Only regular, non-hardlinked files are supported.')
    return info


def move_entry(source_fd, source, target_fd, target):
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    if rename(source_fd, os.fsencode(source), target_fd, os.fsencode(target), 1) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


class Budget:
    def __init__(self, max_bytes=MAX_BYTES):
        self.max_bytes = max_bytes
        self.count = 0
        self.size = 0

    def entry(self, depth):
        self.count += 1
        if self.count > MAX_ENTRIES or depth > MAX_DEPTH:
            raise ValueError('Folder exceeds the entry or nesting limit.')

    def add(self, data):
        self.size += len(data)
        if self.size > self.max_bytes:
            raise ValueError('Operation exceeds its unpacked content limit.')


def copy_bytes(source, target, budget):
    while data := source.read(CHUNK):
        budget.add(data)
        target.write(data)


def entries(fd):
    # scandir with an fd still requires opening children separately without following links.
    with os.scandir(fd) as listing:
        for entry in listing:
            if entry.name.startswith('.alma-'):
                continue
            yield entry.name, entry.stat(follow_symlinks=False)


def tree(root, parts, query):
    if not isinstance(query, str) or len(query) > 120:
        raise ValueError('Enter a search of at most 120 characters.')
    budget = Budget()
    matches = []
    truncated = False

    def visit(fd, prefix):
        nonlocal truncated
        for name, info in entries(fd):
            relative = [*prefix, name]
            if budget.count >= MAX_ENTRIES or len(matches) >= 250:
                truncated = True
                return
            budget.entry(0)
            is_dir = stat.S_ISDIR(info.st_mode)
            if query.casefold() in name.casefold():
                matches.append({'path': '/'.join(relative), 'directory': is_dir,
                                'symlink': stat.S_ISLNK(info.st_mode)})
            if is_dir and len(relative) < MAX_DEPTH:
                try:
                    with folder(fd, [name]) as child:
                        visit(child, relative)
                except OSError:
                    truncated = True

    with folder(root, parts) as fd:
        visit(fd, parts)
    return {'matches': matches, 'truncated': truncated}


def zip_tree(archive, fd, prefix, budget):
    for name, info in entries(fd):
        relative = [*prefix, name]
        budget.entry(len(relative))
        path = '/'.join(relative)
        if ':' in name or '\\' in name or any(ord(char) < 32 for char in name):
            raise ValueError('ZIP cannot represent one of these file names safely.')
        if stat.S_ISDIR(info.st_mode):
            archive.writestr(path + '/', b'')
            with folder(fd, [name]) as child:
                zip_tree(archive, child, relative, budget)
        elif stat.S_ISREG(info.st_mode):
            with os.fdopen(os.open(name, NOFOLLOW_FILE, dir_fd=fd), 'rb') as source:
                regular(source.fileno())
                with archive.open(path, 'w') as target:
                    copy_bytes(source, target, budget)
        else:
            raise ValueError('Archive source contains a symlink or special file.')


def archive_tree(source_root, source_parts, target_root, target_parts, *, private=False, max_bytes=MAX_BYTES):
    if not target_parts or not target_parts[-1].lower().endswith('.zip'):
        raise ValueError('Choose a new .zip destination.')
    if source_root == target_root and source_parts == target_parts[:len(source_parts)] and source_parts:
        raise ValueError('Save the ZIP outside the source folder.')
    tmp = '.alma-' + secrets.token_hex(12)
    with folder(source_root, source_parts) as source, folder(target_root, target_parts[:-1]) as target:
        fd = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640, dir_fd=target)
        try:
            with os.fdopen(fd, 'w+b') as output:
                if private:
                    os.fchmod(output.fileno(), 0o600)
                with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
                    zip_tree(archive, source, [], Budget(max_bytes))
                output.flush()
                os.fsync(output.fileno())
            move_entry(target, tmp, target, target_parts[-1])
        finally:
            try:
                os.unlink(tmp, dir_fd=target)
            except FileNotFoundError:
                pass
    return {'message': 'ZIP archive created.', 'name': target_parts[-1]}


def unpack_member(archive, info, dest, budget, seen):
    name = info.orig_filename
    if ('\\' in name or ':' in name or name.startswith('/') or
            any(ord(char) < 32 for char in name) or
            any(part in ('', '.', '..') or part.startswith('.alma-') for part in name.rstrip('/').split('/'))):
        raise ValueError('ZIP contains an unsafe path.')
    parts = components(name)
    path = tuple(parts)
    budget.entry(len(parts))
    if path in seen:
        raise ValueError('ZIP contains duplicate paths.')
    seen.add(path)
    kind = stat.S_IFMT(info.external_attr >> 16)
    if kind not in (0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG) or info.flag_bits & 1:
        raise ValueError('ZIP contains a link, special file or encrypted entry.')
    if info.file_size > budget.max_bytes - budget.size:
        raise ValueError('Unpacked ZIP exceeds its content limit.')
    fd = os.dup(dest)
    try:
        for part in parts if info.is_dir() else parts[:-1]:
            try:
                os.mkdir(part, 0o750, dir_fd=fd)
            except FileExistsError:
                pass
            next_fd = os.open(part, NOFOLLOW_DIR, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        if not info.is_dir():
            with archive.open(info) as source:
                output = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o640, dir_fd=fd)
                with os.fdopen(output, 'wb') as target:
                    copy_bytes(source, target, budget)
    finally:
        os.close(fd)


def staged_folder(root, target_parts, populate):
    if not target_parts:
        raise ValueError('Choose a new destination folder.')
    tmp = '.alma-' + secrets.token_hex(12)
    with folder(root, target_parts[:-1]) as parent:
        os.mkdir(tmp, 0o750, dir_fd=parent)
        published = False
        try:
            with folder(parent, [tmp]) as destination:
                populate(destination)
            move_entry(parent, tmp, parent, target_parts[-1])
            published = True
        finally:
            if not published:
                shutil.rmtree(tmp, dir_fd=parent)


def extract_zip(source_root, source_parts, root, target_parts, *, max_bytes=MAX_BYTES, prepare=None):
    if not source_parts:
        raise ValueError('Select a ZIP file.')

    def unpack(destination):
        with folder(source_root, source_parts[:-1]) as parent:
            fd = os.open(source_parts[-1], NOFOLLOW_FILE, dir_fd=parent)
        with os.fdopen(fd, 'rb') as archive_file:
            if regular(archive_file.fileno()).st_size > max_bytes + 2 * 1024 * 1024:
                raise ValueError('ZIP file exceeds the size limit.')
            with zipfile.ZipFile(archive_file) as archive:
                budget = Budget(max_bytes)
                seen = set()
                for item in archive.infolist():
                    unpack_member(archive, item, destination, budget, seen)
        if prepare:
            prepare(destination)

    try:
        staged_folder(root, target_parts, unpack)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError('Invalid or unsupported ZIP archive.') from exc
    return {'message': 'Files extracted to a new folder.'}


def copy_tree(root, source_parts, target_parts):
    if not source_parts or target_parts[:len(source_parts)] == source_parts:
        raise ValueError('Choose a destination outside the source folder.')
    budget = Budget()

    def traverse(source, dest, depth):
        for name, info in entries(source):
            budget.entry(depth)
            if stat.S_ISDIR(info.st_mode):
                os.mkdir(name, 0o750, dir_fd=dest)
                with folder(source, [name]) as src, folder(dest, [name]) as dst:
                    traverse(src, dst, depth + 1)
            elif stat.S_ISREG(info.st_mode):
                with os.fdopen(os.open(name, NOFOLLOW_FILE, dir_fd=source), 'rb') as reader:
                    regular(reader.fileno())
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640, dir_fd=dest)
                    with os.fdopen(fd, 'wb') as writer:
                        copy_bytes(reader, writer, budget)
            else:
                raise ValueError('Folder contains a symlink or special file.')

    with folder(root, source_parts) as source:
        staged_folder(root, target_parts, lambda dest: traverse(source, dest, 1))
    return {'message': 'Folder copied.'}


def read_chunk(root, parts, request, *, max_bytes=MAX_BYTES):
    offset = request.get('offset', 0)
    if not parts or type(offset) is not int or not 0 <= offset <= max_bytes + 2 * 1024 * 1024:
        raise ValueError('Invalid download offset.')
    with folder(root, parts[:-1]) as parent:
        fd = os.open(parts[-1], NOFOLLOW_FILE, dir_fd=parent)
    with os.fdopen(fd, 'rb') as source:
        info = regular(source.fileno())
        if info.st_size > max_bytes + 2 * 1024 * 1024:
            raise ValueError('File exceeds the download limit.')
        revision = f'{info.st_ino}:{info.st_size}:{info.st_mtime_ns}:{info.st_ctime_ns}'
        if offset and request.get('revision') != revision:
            raise ValueError('File changed during download.')
        source.seek(offset)
        data = source.read(CHUNK)
        return {'content': base64.b64encode(data).decode(), 'size': info.st_size,
                'revision': revision, 'done': offset + len(data) >= info.st_size}


def private_operation(root, private, parts, request):
    if private is None:
        raise ValueError('Account private storage is unavailable.')
    action = request['action']
    if action in ('backup_create', 'backup_scheduled'):
        with folder(private, ['backups']) as backups:
            scheduled = action == 'backup_scheduled'
            retain = request.get('retain')
            if scheduled and (type(retain) is not int or not 1 <= retain <= 10):
                raise ValueError('Invalid backup retention.')
            prefix = 'scheduled-' if scheduled else 'website-'
            name = f'{prefix}{secrets.token_hex(8)}.zip'
            result = archive_tree(root, [], backups, [name], private=True, max_bytes=BACKUP_BYTES)
            if scheduled:
                previous = sorted(
                    ((info.st_mtime_ns, item) for item, info in entries(backups) if
                     re.fullmatch(r'scheduled-[a-f0-9]{16}\.zip', item) and
                     stat.S_ISREG(info.st_mode) and item != name), reverse=True)
                for _, item in previous[retain - 1:]:
                    os.unlink(item, dir_fd=backups)
            return result
    if action in ('backups', 'backup_read', 'backup_restore', 'backup_delete'):
        with folder(private, ['backups']) as backups:
            if action == 'backups':
                result = []
                for name, info in entries(backups):
                    if re.fullmatch(r'(?:website|scheduled)-[a-f0-9]{16}\.zip', name) and stat.S_ISREG(info.st_mode):
                        result.append({'name': name, 'size': info.st_size, 'created': int(info.st_mtime)})
                        if len(result) > 250:
                            raise ValueError('Backup listing exceeds the 250-entry limit.')
                return sorted(result, key=lambda entry: entry['created'], reverse=True)
            if len(parts) != 1 or not re.fullmatch(r'(?:website|scheduled)-[a-f0-9]{16}\.zip', parts[0]):
                raise ValueError('Invalid backup name.')
            if action == 'backup_read':
                return read_chunk(backups, parts, request, max_bytes=BACKUP_BYTES)
            if action == 'backup_delete':
                os.unlink(parts[0], dir_fd=backups)
                return {'message': 'Backup deleted.'}
            return extract_zip(backups, parts, root, components(request.get('destination')),
                               max_bytes=BACKUP_BYTES)
    with folder(private, ['trash']) as trash:
        if action == 'trash':
            if not parts:
                raise ValueError('Select an entry to move to Trash.')
            entry_id = secrets.token_hex(12)
            os.mkdir(entry_id, 0o700, dir_fd=trash)
            try:
                with folder(trash, [entry_id]) as entry:
                    with os.fdopen(os.open('info', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=entry), 'w') as meta:
                        json.dump({'path': '/'.join(parts)}, meta)
                    with folder(root, parts[:-1]) as parent:
                        move_entry(parent, parts[-1], entry, 'entry')
            except OSError:
                shutil.rmtree(entry_id, dir_fd=trash)
                raise
            return {'message': 'Moved to Trash.'}
        if action == 'trash_list':
            result = []
            for entry_id, info in entries(trash):
                if not re.fullmatch(r'[a-f0-9]{24}', entry_id) or not stat.S_ISDIR(info.st_mode):
                    continue
                try:
                    with folder(trash, [entry_id]) as entry:
                        os.stat('entry', dir_fd=entry, follow_symlinks=False)
                        fd = os.open('info', NOFOLLOW_FILE, dir_fd=entry)
                        with os.fdopen(fd, 'r') as meta:
                            regular(meta.fileno())
                            path = json.loads(meta.read(15000))['path']
                            if components(path):
                                result.append({'id': entry_id, 'path': path})
                except (OSError, ValueError, TypeError, KeyError):
                    continue
                if len(result) > 250:
                    raise ValueError('Trash listing exceeds the 250-entry limit.')
            return result
        entry_id = request.get('id')
        if not isinstance(entry_id, str) or not re.fullmatch(r'[a-f0-9]{24}', entry_id):
            raise ValueError('Invalid Trash entry.')
        if action == 'trash_restore':
            target = components(request.get('destination'))
            if not target:
                raise ValueError('Choose a restore destination.')
            with folder(trash, [entry_id]) as entry, folder(root, target[:-1]) as parent:
                move_entry(entry, 'entry', parent, target[-1])
        shutil.rmtree(entry_id, dir_fd=trash)
        return {'message': 'Entry restored.' if action == 'trash_restore' else 'Trash entry deleted.'}
