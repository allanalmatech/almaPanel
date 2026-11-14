# Copyright (c) 2026 Alma Tech Labs Inc. SPDX-License-Identifier: LicenseRef-AlmaTech-Pending
"""Run only after dropping supplementary groups and UID to the hosting user.
Every traversal uses directory descriptors and O_NOFOLLOW; no resolve/check/use race.
"""
import base64
import json
import os
import secrets
import stat
import sys

if __package__:
    from . import file_tools
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import file_tools

MAX_FILE = 1024*1024
components = file_tools.components
directory = file_tools.directory
regular = file_tools.regular

PRIVATE_ACTIONS = {
    'trash', 'trash_list', 'trash_restore', 'trash_purge',
} | file_tools.BACKUP_ACTIONS

def operate(root, request, private=None):
    parts = components(request.get('path', ''))
    action = request.get('action')
    if action in PRIVATE_ACTIONS:
        return file_tools.private_operation(root, private, parts, request)
    if action in ('sql_import', 'sql_export'):
        if __package__:
            from .sqltransfer import transfer
        else:
            from sqltransfer import transfer
        return transfer(root, private, request)
    if action in ('sql_download', 'sql_delete'):
        import re
        if len(parts) != 1 or not re.fullmatch(r'sql-[a-f0-9]{24}\.(sql|pgdump)', parts[0]):
            raise ValueError('Invalid SQL export name.')
        with file_tools.folder(private, ['sql']) as source:
            if action == 'sql_delete':
                os.unlink(parts[0], dir_fd=source)
                return {'message': 'Export removed from the server.'}
            return file_tools.read_chunk(source, parts, request)
    if action == 'wordpress_install':
        if __package__:
            from .wordpress import install
        else:
            from wordpress import install
        return install(root, request)
    if action in ('cron_validate', 'cron_execute'):
        return cron_script(root, parts, action)
    if action == 'git_release':
        if __package__:
            from .deployments import release
        else:
            from deployments import release
        return release(root, request)
    if action == 'folder_check':
        with file_tools.folder(root, parts):
            return {'message': 'Folder exists.'}
    if action == 'search':
        return file_tools.tree(root, parts, request.get('query', ''))
    if action == 'archive':
        return file_tools.archive_tree(root, parts, root, components(request.get('destination')))
    if action == 'extract':
        return file_tools.extract_zip(root, parts, root, components(request.get('destination')))
    if action == 'copy_tree':
        return file_tools.copy_tree(root, parts, components(request.get('destination')))
    if action == 'download':
        return file_tools.read_chunk(root, parts, request)
    if action=='list':
        fd=directory(root,parts)
        try:
            result=[]
            names=sorted(os.listdir(fd))
            if len(names)>5000:
                raise ValueError('Directory exceeds 5000-entry browsing limit.')
            for item in names:
                s=os.stat(item,dir_fd=fd,follow_symlinks=False)
                result.append({'name':item,'size':s.st_size,'mode':oct(stat.S_IMODE(s.st_mode)),
                               'uid':s.st_uid,'directory':stat.S_ISDIR(s.st_mode),'symlink':stat.S_ISLNK(s.st_mode)})
            return result
        finally: os.close(fd)
    if not parts:
        raise ValueError('Select a file or folder.')
    parent=directory(root,parts[:-1]);leaf=parts[-1]
    try:
        if action=='read':
            fd=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            with os.fdopen(fd,'rb') as f:
                if regular(f.fileno()).st_size>MAX_FILE: raise ValueError('File exceeds 1 MB.')
                data=f.read(MAX_FILE+1)
                if len(data)>MAX_FILE: raise ValueError('File exceeds 1 MB.')
                return {'content':base64.b64encode(data).decode()}
        if action=='write':
            data=base64.b64decode(request.get('content',''),validate=True)
            if len(data)>MAX_FILE: raise ValueError('File exceeds 1 MB.')
            # Atomic replacement does not follow a symlink at the destination.
            try:
                s=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
                if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1: raise ValueError('Unsafe destination.')
            except FileNotFoundError: pass
            tmp='.alma-'+secrets.token_hex(16)
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o640,dir_fd=parent)
            try:
                with os.fdopen(fd,'wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
                if request.get('create_only') is True:
                    file_tools.move_entry(parent, tmp, parent, leaf)
                else:
                    os.rename(tmp, leaf, src_dir_fd=parent, dst_dir_fd=parent)
            finally:
                try: os.unlink(tmp,dir_fd=parent)
                except FileNotFoundError: pass
            return {'message':'File saved.'}
        if action=='mkdir':
            os.mkdir(leaf,0o750,dir_fd=parent);return {'message':'Folder created.'}
        if action=='rename':
            dest=components(request.get('destination',''))
            if not dest: raise ValueError('Destination required.')
            other=directory(root,dest[:-1])
            try:
                file_tools.move_entry(parent, leaf, other, dest[-1])
            finally: os.close(other)
            return {'message':'Renamed.'}
        if action == 'chmod':
            mode = request.get('mode')
            if mode not in ('600', '640', '644', '700', '750', '755'):
                raise ValueError('Choose 600, 640, 644, 700, 750 or 755.')
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                info = os.fstat(fd)
                if info.st_uid != os.geteuid():
                    raise ValueError('Only account-owned entries can be changed.')
                if not stat.S_ISDIR(info.st_mode):
                    regular(fd)
                os.fchmod(fd, int(mode, 8))
            finally:
                os.close(fd)
            return {'message': 'Permissions updated.'}
        if action == 'copy':
            destination = components(request.get('destination', ''))
            if not destination:
                raise ValueError('Destination required.')
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, 'rb') as source:
                if regular(source.fileno()).st_size > MAX_FILE:
                    raise ValueError('File exceeds 1 MB.')
                content = source.read(MAX_FILE + 1)
                if len(content) > MAX_FILE:
                    raise ValueError('File exceeds 1 MB.')
            target = directory(root, destination[:-1])
            try:
                output = os.open(destination[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o640, dir_fd=target)
                try:
                    with os.fdopen(output, 'wb') as file:
                        file.write(content)
                        file.flush()
                        os.fsync(file.fileno())
                except OSError:
                    os.unlink(destination[-1], dir_fd=target)
                    raise
            finally:
                os.close(target)
            return {'message': 'File copied.'}
        if action=='delete':
            s=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
            if stat.S_ISDIR(s.st_mode): os.rmdir(leaf,dir_fd=parent)
            else: os.unlink(leaf,dir_fd=parent)
            return {'message':'Deleted permanently.'}
        raise ValueError('Unsupported file operation.')
    finally: os.close(parent)

def cron_script(root, parts, action):
    import resource
    import subprocess
    if not parts or not parts[-1].lower().endswith('.php'):
        raise ValueError('Choose a PHP script under public_html.')
    with file_tools.folder(root, parts[:-1]) as parent:
        fd = os.open(parts[-1], file_tools.NOFOLLOW_FILE, dir_fd=parent)
        try:
            entry = regular(fd)
            if entry.st_uid != os.geteuid() or entry.st_size > 1024 * 1024:
                raise ValueError('Use an account-owned PHP script up to 1 MiB.')
            if action == 'cron_validate':
                return {'path': '/'.join(parts)}
            # This process already runs as the tenant. Bound CPU, output writes and
            # runtime without passing PHP arguments or shell syntax from the panel.
            resource.setrlimit(resource.RLIMIT_CPU, (15, 16))
            resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
            try:
                subprocess.run(['/usr/bin/php', '-d', 'memory_limit=96M', '-f', f'/proc/self/fd/{fd}'],
                               check=True, timeout=20, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, cwd=f'/proc/self/fd/{parent}', pass_fds=(fd, parent))
            except (OSError, subprocess.SubprocessError):
                raise ValueError('Scheduled PHP script failed or reached its runtime limit.') from None
            return {'message': 'Scheduled PHP script finished.'}
        finally:
            os.close(fd)


if __name__=='__main__':
    if len(sys.argv) == 3 and sys.argv[2] in ('--site-snapshot', '--import-backup'):
        try:
            if os.geteuid() == 0:
                raise ValueError('Website snapshots require the hosting account identity.')
            root = os.open(sys.argv[1], file_tools.NOFOLLOW_DIR)
            try:
                if sys.argv[2] == '--site-snapshot':
                    file_tools.write_zip(root, sys.stdout.buffer, file_tools.BACKUP_BYTES, compress=False)
                else:
                    try:
                        os.mkdir('backups', 0o700, dir_fd=root)
                    except FileExistsError:
                        pass
                    print(file_tools.import_backup(root, sys.stdin.buffer))
            finally:
                os.close(root)
        except (OSError, ValueError) as error:
            sys.exit(str(error))
        sys.exit(0)
    try:
        root = os.open(sys.argv[1], file_tools.NOFOLLOW_DIR)
        private = None
        try:
            if len(sys.argv) > 2:
                private = os.open(sys.argv[2], file_tools.NOFOLLOW_DIR)
                for section in ('trash', 'backups', 'sql'):
                    try:
                        os.mkdir(section, 0o700, dir_fd=private)
                    except FileExistsError:
                        pass
            result = operate(root, json.loads(sys.stdin.buffer.read(1_500_001)), private)
        finally:
            if private is not None:
                os.close(private)
            os.close(root)
        print(json.dumps({'ok':True,'data':result}))
    except (OSError,ValueError,TypeError) as e:
        print(json.dumps({'ok':False,'error':str(e)}));sys.exit(1)
