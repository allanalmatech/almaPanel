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
import zlib

CHUNK = 512 * 1024
MAX_BYTES = 64 * 1024 * 1024
BACKUP_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_DEPTH = 24
BACKUP_PAGE_SIZE = 75
BACKUP_NAME = re.compile(r'(?:website|scheduled)-[a-f0-9]{16}\.zip\Z')
BACKUP_ACTIONS = {
    'backup_create', 'backup_scheduled', 'backups', 'backup_read', 'backup_restore',
    'backup_delete', 'backup_contents', 'backup_verify', 'backup_restore_file',
}
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
        if target is not None:
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
        if len(path) > 2048 or ':' in name or '\\' in name or any(ord(char) < 32 for char in name):
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


def write_zip(source, output, max_bytes, *, compress=True):
    mode = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    with zipfile.ZipFile(output, 'w', compression=mode, compresslevel=3) as archive:
        zip_tree(archive, source, [], Budget(max_bytes))
    output.flush()
    os.fsync(output.fileno())
    if output.tell() > max_bytes + 2 * 1024 * 1024:
        raise ValueError('ZIP exceeds its final archive size limit.')


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
                write_zip(source, output, max_bytes)
            move_entry(target, tmp, target, target_parts[-1])
        finally:
            try:
                os.unlink(tmp, dir_fd=target)
            except FileNotFoundError:
                pass
    return {'message': 'ZIP archive created.', 'name': target_parts[-1]}


def member_path(info):
    name = info.orig_filename
    if ('\\' in name or ':' in name or name.startswith('/') or
            any(ord(char) < 32 for char in name) or
            any(part in ('', '.', '..') or part.startswith('.alma-') for part in
                name.removesuffix('/').split('/'))):
        raise ValueError('ZIP contains an unsafe path.')
    kind = stat.S_IFMT(info.external_attr >> 16)
    if kind not in (0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG) or info.flag_bits & 1:
        raise ValueError('ZIP contains a link, special file or encrypted entry.')
    if info.is_dir() and info.file_size:
        raise ValueError('ZIP directory entries must be empty.')
    return tuple(components(name))


def copy_member(archive, item, target, budget):
    if item.file_size > budget.max_bytes - budget.size:
        raise ValueError('Unpacked ZIP exceeds its content limit.')
    expected = budget.size + item.file_size
    with archive.open(item) as source:
        copy_bytes(source, target, budget)
    if budget.size != expected:
        raise ValueError('ZIP entry does not match its recorded size.')


def unpack_member(archive, info, dest, budget, seen):
    parts = member_path(info)
    budget.entry(len(parts))
    if parts in seen:
        raise ValueError('ZIP contains duplicate paths.')
    seen.add(parts)
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
            output = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o640, dir_fd=fd)
            with os.fdopen(output, 'wb') as target:
                copy_member(archive, info, target, budget)
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


@contextmanager
def open_zip(root, parts, max_bytes):
    if not parts:
        raise ValueError('Select a ZIP file.')
    with folder(root, parts[:-1]) as parent:
        fd = os.open(parts[-1], NOFOLLOW_FILE, dir_fd=parent)
    with os.fdopen(fd, 'rb') as file:
        original = regular(file.fileno())
        if original.st_size > max_bytes + 2 * 1024 * 1024:
            raise ValueError('ZIP file exceeds the size limit.')
        try:
            with zipfile.ZipFile(file) as archive:
                yield archive, file, original
        except (zipfile.BadZipFile, EOFError, RuntimeError, NotImplementedError, zlib.error) as exc:
            raise ValueError('Invalid, damaged or unsupported ZIP archive.') from exc


def extract_zip(source_root, source_parts, root, target_parts, *, max_bytes=MAX_BYTES, prepare=None):

    def unpack(destination):
        with open_zip(source_root, source_parts, max_bytes) as (archive, _, _):
            budget = Budget(max_bytes)
            seen = set()
            for item in archive.infolist():
                unpack_member(archive, item, destination, budget, seen)
        if prepare:
            prepare(destination)

    staged_folder(root, target_parts, unpack)
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


def revision_of(info):
    return f'{info.st_ino}:{info.st_size}:{info.st_mtime_ns}:{info.st_ctime_ns}'


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
        revision = revision_of(info)
        if offset and request.get('revision') != revision:
            raise ValueError('File changed during download.')
        source.seek(offset)
        data = source.read(CHUNK)
        return {'content': base64.b64encode(data).decode(), 'size': info.st_size,
                'revision': revision, 'done': offset + len(data) >= info.st_size}


def backup_index(archive):
    items = archive.infolist()
    if len(items) > MAX_ENTRIES or sum(item.file_size for item in items) > BACKUP_BYTES:
        raise ValueError('Backup exceeds its unpacked content or entry limit.')
    members = {}
    for item in items:
        if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ValueError('The website backup uses an unsupported ZIP compression method.')
        parts = member_path(item)
        if parts in members:
            raise ValueError('ZIP contains duplicate paths.')
        members[parts] = item
    files = {path: item for path, item in members.items() if not item.is_dir()}
    if any(path[:depth] in files for path in members for depth in range(1, len(path))):
        raise ValueError('ZIP contains a file where a folder is required.')
    return files


def verify_backup(archive, files):
    budget = Budget(BACKUP_BYTES)
    for item in files.values():
        copy_member(archive, item, None, budget)
    return budget.size


def import_backup(private, source):
    with folder(private, ['backups']) as backups:
        name = 'website-' + secrets.token_hex(8) + '.zip'
        temporary = '.alma-' + secrets.token_hex(12)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=backups)
        try:
            with os.fdopen(fd, 'wb') as output:
                copy_bytes(source, output, Budget(BACKUP_BYTES + 2 * 1024 * 1024))
                output.flush()
                os.fsync(output.fileno())
            with open_zip(backups, [temporary], BACKUP_BYTES) as (archive, source_file, original):
                verify_backup(archive, backup_index(archive))
                if revision_of(regular(source_file.fileno())) != revision_of(original):
                    raise ValueError('The staging archive changed during verification.')
            move_entry(backups, temporary, backups, name)
        finally:
            try:
                os.unlink(temporary, dir_fd=backups)
            except FileNotFoundError:
                pass
    return name


def backup_contents(files, request, revision):
    query = request.get('query', '')
    offset = request.get('offset', 0)
    if not isinstance(query, str) or len(query) > 120 or type(offset) is not int or not 0 <= offset <= MAX_ENTRIES:
        raise ValueError('Invalid backup search or page.')
    needle = query.casefold()
    paths = [('/'.join(parts), item.file_size) for parts, item in sorted(files.items())]
    matches = [(path, size) for path, size in paths if needle in path.casefold()]
    end = offset + BACKUP_PAGE_SIZE
    return {'entries': [{'path': path, 'size': size} for path, size in matches[offset:end]],
            'total': len(matches), 'next_offset': end if end < len(matches) else None, 'revision': revision}


def restore_backup_file(root, destination, archive, item, check_revision):
    if not destination or any(part.startswith('.alma-') for part in destination):
        raise ValueError('Choose a new file path inside public_html.')
    tmp = '.alma-' + secrets.token_hex(12)
    with folder(root, destination[:-1]) as parent:
        output = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640, dir_fd=parent)
        try:
            with os.fdopen(output, 'wb') as target:
                copy_member(archive, item, target, Budget(BACKUP_BYTES))
                target.flush()
                os.fsync(target.fileno())
            check_revision()
            move_entry(parent, tmp, parent, destination[-1])
        finally:
            try:
                os.unlink(tmp, dir_fd=parent)
            except FileNotFoundError:
                pass
    return {'message': 'File restored.', 'path': '/'.join(destination)}


def inspect_backup(backups, parts, root, request):
    with open_zip(backups, parts, BACKUP_BYTES) as (archive, source, original):
        revision = revision_of(original)

        def check_revision():
            if revision != revision_of(regular(source.fileno())):
                raise ValueError('Backup changed during the operation. Reopen it and try again.')

        action = request['action']
        if action == 'backup_restore_file' or request.get('revision'):
            if request.get('revision') != revision:
                raise ValueError('Backup changed. Reopen it to select a file or continue browsing.')
        files = backup_index(archive)
        if action == 'backup_contents':
            result = backup_contents(files, request, revision)
            check_revision()
            return result
        if action == 'backup_verify':
            size = verify_backup(archive, files)
            check_revision()
            return {'message': 'ZIP integrity check passed.', 'files': len(files), 'bytes': size}
        member = components(request.get('member'))
        item = files.get(tuple(member))
        if not item:
            raise ValueError('That regular file is not in this backup.')
        return restore_backup_file(root, components(request.get('destination')), archive, item, check_revision)


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
                     item.startswith('scheduled-') and BACKUP_NAME.fullmatch(item) and
                     stat.S_ISREG(info.st_mode) and item != name), reverse=True)
                for _, item in previous[retain - 1:]:
                    os.unlink(item, dir_fd=backups)
            return result
    if action in BACKUP_ACTIONS:
        with folder(private, ['backups']) as backups:
            if action == 'backups':
                result = []
                for name, info in entries(backups):
                    if BACKUP_NAME.fullmatch(name) and stat.S_ISREG(info.st_mode):
                        result.append({'name': name, 'size': info.st_size, 'created': int(info.st_mtime)})
                        if len(result) > 250:
                            raise ValueError('Backup listing exceeds the 250-entry limit.')
                return sorted(result, key=lambda entry: entry['created'], reverse=True)
            if len(parts) != 1 or not BACKUP_NAME.fullmatch(parts[0]):
                raise ValueError('Invalid backup name.')
            if action == 'backup_read':
                return read_chunk(backups, parts, request, max_bytes=BACKUP_BYTES)
            if action == 'backup_delete':
                os.unlink(parts[0], dir_fd=backups)
                return {'message': 'Backup deleted.'}
            if action == 'backup_restore':
                return extract_zip(backups, parts, root, components(request.get('destination')),
                                   max_bytes=BACKUP_BYTES)
            return inspect_backup(backups, parts, root, request)
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
